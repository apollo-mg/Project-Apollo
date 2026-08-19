"""Cross-backend VBR test. Same fork commit, same model, same items; backend is the variable.

WHY D=128 AND NOT THE 27B:
  RESULT_D128.md measured Qwen3.8-27B (D=256) on sm_60 with STOCK q8_0 KV -> collapse 3/3.
  Bug A eats any quantized-KV result at D=256 on Pascal, VBR included. At D=128 the same
  receipt measured q8_0 and q4_0 clean 3/3, so a collapse there is attributable to the codec.

VALIDITY GATE (the trap this script exists to avoid):
  A codec that silently falls back to f16 produces a CLEAN arm -- which is exactly the
  result we are hoping to see for CUDA. Indistinguishable from "VBR works" unless the
  allocation is checked. Expected KV @16384 ctx for Llama-3.2-3B (28L, 8 kv-heads, D=128):
      f16   1792 MiB      q8_0   952 MiB      vbr (turbo3_tcq, 3.25bpv)  364 MiB
  Arms whose KV allocation matches f16 are reported INVALID, not clean.
"""
import json, urllib.request, subprocess, time, os, sys, glob, re

BIN   = os.environ["VBR_BIN"]
MODEL = os.environ["VBR_MODEL"]
LABEL = os.environ.get("VBR_LABEL", "unknown")
OUT   = os.environ.get("VBR_OUT", "/tmp/vbr_backend")
CTX   = int(os.environ.get("VBR_CTX", "16384"))
ARMS  = os.environ.get("VBR_ARMS", "f16,q8_0,vbr").split(",")
os.makedirs(OUT, exist_ok=True)

# Exclusive lock: this runner pkills llama-server on every arm start, so two concurrent
# runners silently destroy each other's servers mid-sequence. Refuse rather than race.
LOCK = os.path.join(OUT, ".runner.lock")
if os.path.exists(LOCK):
    try:
        other = int(open(LOCK).read().strip())
        os.kill(other, 0)
        sys.exit(f"REFUSING: runner pid {other} is already active (lock {LOCK}). "
                 f"Wait for it or remove the lock if stale.")
    except (ValueError, ProcessLookupError, PermissionError):
        pass  # stale lock, take it
open(LOCK, "w").write(str(os.getpid()))
import atexit
atexit.register(lambda: os.path.exists(LOCK) and os.remove(LOCK))

TMPL = "{}\n\nThink briefly if you need to, then end your reply with exactly one line:\nExact Answer: <your answer>"
CAN  = "What is 17 multiplied by 23? Reply with just the number."
ITEMS = [("T2-01","A tank fills at 4 L/min and drains at 1.5 L/min. It starts at 20 L and holds 200 L. How many minutes until it is full?","72"),
         ("T2-02","A shirt costs 40 dollars after a 20 percent discount. What was the original price in dollars?","50"),
         ("T2-03","If today is Wednesday, what day of the week will it be in 100 days?","Friday"),
         ("T2-04","What is the output of this Python: print(len([x for x in range(20) if x % 3 == 0]))","7"),
         ("T2-05","Solve for x: 3x + 7 = 2x + 15. Give only the value of x.","8"),
         ("T2-06","A bag has 3 red and 5 blue marbles. Two are drawn without replacement. What is the probability both are red? Give the answer as a fraction in lowest terms.","3/28"),
         ("T2-07","How many bytes are in 2.5 kibibytes?","2560"),
         ("T2-08","Put these in ascending order and give only the second smallest: 0.5, 1/3, 0.45, 2/5","2/5"),
         ("T2-09","A train travels 240 km in 3 hours. At the same speed, how many kilometres does it travel in 50 minutes?","66.67"),
         ("T2-10","What is the smallest prime number greater than 90?","97")]

def vram_used_mib():
    """Ground truth, never the runtime. sysfs on amdgpu, nvidia-smi on NVIDIA."""
    p = sorted(glob.glob("/sys/class/drm/card*/device/mem_info_vram_used"))
    if p:
        return max(int(open(f).read().strip()) for f in p) // (1024*1024)
    try:
        r = subprocess.run(["nvidia-smi","--query-gpu=memory.used","--format=csv,noheader,nounits","-i","0"],
                           capture_output=True, text=True, timeout=20)
        return int(r.stdout.strip().splitlines()[0])
    except Exception:
        return -1

def start(kv, log):
    subprocess.run(["pkill","-x","llama-server"], capture_output=True); time.sleep(8)
    base = vram_used_mib()
    env = dict(os.environ, LD_LIBRARY_PATH=BIN)
    extra = os.environ.get("VBR_EXTRA","").split()
    # "K:V" selects an asymmetric pair; a bare name is symmetric.
    ck, cv = (kv.split(":", 1) + [kv])[:2] if ":" in kv else (kv, kv)
    subprocess.Popen([f"{BIN}/llama-server","-m",MODEL,"-ngl","99","-c",str(CTX),
                      "-ctk",ck,"-ctv",cv,"-fa",os.environ.get("VBR_FA","on"),"--kv-unified",
                      "--jinja","--host","127.0.0.1","--port","8080"] + extra,
                     stdout=open(log,"w"), stderr=subprocess.STDOUT, env=env, start_new_session=True)
    for _ in range(150):
        try:
            urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=2)
            time.sleep(3)
            return base, vram_used_mib()
        except Exception:
            time.sleep(2)
    return base, None

def ask(c, n):
    body = {"messages":[{"role":"user","content":c}],"temperature":0,"top_k":1,"n_predict":n}
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
    d = json.loads(urllib.request.urlopen(req, timeout=900).read())
    m = d["choices"][0]["message"]
    return (m.get("content") or "") + (m.get("reasoning_content") or ""), d["choices"][0].get("finish_reason")

def canary(tag):
    b,_ = ask(CAN, 256); bf = b.count("!")/max(len(b),1)
    ok = bf < 0.5 and "391" in b
    kind = "ok" if ok else ("COLLAPSED" if bf > 0.5 else "wrong-answer")
    print(f"  CANARY {tag:<7} {kind}  (!frac={bf:.2f}, chars={len(b)})", flush=True)
    return ok, bf

print(f"### {LABEL} | bin={BIN} | ctx={CTX} | arms={ARMS}", flush=True)
summary = {}
for kv in ARMS:
    print(f"\n{'='*70}\n=== KV = {kv}   [{LABEL}]\n{'='*70}", flush=True)
    log = f"{OUT}/srv_{LABEL}_{kv}.log"
    base, after = start(kv, log)
    if after is None:
        print("  server failed to start", flush=True)
        tail = subprocess.run(["tail","-5",log], capture_output=True, text=True).stdout
        print("  " + tail.replace("\n","\n  "), flush=True)
        summary[kv] = {"status":"no-start"}; continue
    alloc = after - base
    # independent check: what the server itself says it built
    txt = open(log, errors="replace").read()
    kvline = [l for l in txt.splitlines() if re.search(r"KV self size|kv_unified|type_k|type_v", l)]
    print(f"  VRAM  base={base} after={after}  ALLOC={alloc} MiB", flush=True)
    for l in kvline[:3]:
        print(f"  LOG   {l.strip()[:120]}", flush=True)
    cb, cb_bang = canary("before")
    if not cb and cb_bang > 0.5:
        print("  server born COLLAPSED (! spam) — items skipped", flush=True)
        summary[kv] = {"status":"born-collapsed","alloc":alloc}; continue
    if not cb:
        print("  canary wrong-but-coherent — DEGRADED, running items anyway", flush=True)
    dead_at = None; ok_n = 0
    for tag,q,gold in ITEMS:
        b,f = ask(TMPL.format(q), 3072); bf = b.count("!")/max(len(b),1)
        hit = gold.lower().replace(" ","") in b.lower().replace(" ","").replace(",","")
        if hit: ok_n += 1
        print(f"  {tag}  chars={len(b):<6} fin={f:<7} !frac={bf:.2f}  "
              f"{'COLLAPSED' if bf>0.5 else ('has-answer' if hit else 'no-answer')}", flush=True)
        if bf > 0.5 and dead_at is None: dead_at = tag
    ca, _ = canary("after")
    print(f"  --> first collapse: {dead_at or 'NONE — arm survived'}   correct={ok_n}/10", flush=True)
    summary[kv] = {"status":"ran","alloc":alloc,"first_collapse":dead_at,"correct":ok_n,"canary_after":ca}

subprocess.run(["pkill","-x","llama-server"], capture_output=True)
print(f"\n### SUMMARY {LABEL}\n{json.dumps(summary, indent=2)}", flush=True)
json.dump(summary, open(f"{OUT}/summary_{LABEL}.json","w"), indent=2)
