"""Is it a PREFILL length threshold?

Scenario B collapsed on the first request with all-'!' from token 1 — so generation never
worked at all for that prompt, while a shorter prompt generating 2560 tokens was clean.
The three prompts tested differ mostly in length. Sweep prompt length directly.

Fresh server per length. n_predict small — we only need to see whether output is garbage.
"""
import json, urllib.request, subprocess, time, os

BIN   = "/mnt/TG_2TB/Projects/Apollo/engines/buun-llama-cpp/build_rocm/bin"
MODEL = "/home/mark/Downloads/Qwen3.8-27B-AD-IQ2_S.gguf"
KV    = os.environ.get("PF_KV","turbo4")
OUT   = "/mnt/TG_2TB/Projects/Apollo/data/receipts/vbr-backend/raw"
FILLER = "The quick brown fox jumps over the lazy dog. "

def start(log):
    subprocess.run(["pkill","-x","llama-server"], capture_output=True); time.sleep(8)
    env=dict(os.environ, LD_LIBRARY_PATH=BIN)
    subprocess.Popen([f"{BIN}/llama-server","-m",MODEL,"-ngl","99","-c","4096",
                      "-ctk",KV,"-ctv",KV,"-fa","on","--kv-unified",
                      "--jinja","--host","127.0.0.1","--port","8080"],
                     stdout=open(log,"w"), stderr=subprocess.STDOUT, env=env, start_new_session=True)
    for _ in range(150):
        try: urllib.request.urlopen("http://127.0.0.1:8080/health",timeout=2); return True
        except Exception: time.sleep(2)
    return False

def tok(s):
    req=urllib.request.Request("http://127.0.0.1:8080/tokenize",
        data=json.dumps({"content":s}).encode(),headers={"Content-Type":"application/json"})
    return len(json.loads(urllib.request.urlopen(req,timeout=60).read())["tokens"])

def ask(p,n=128):
    body={"messages":[{"role":"user","content":p}],"temperature":0,"top_k":1,"n_predict":n}
    req=urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",
        data=json.dumps(body).encode(),headers={"Content-Type":"application/json"})
    d=json.loads(urllib.request.urlopen(req,timeout=900).read())
    m=d["choices"][0]["message"]
    t=(m.get("content") or "")+(m.get("reasoning_content") or "")
    return t, t.count("!")/max(len(t),1)

print(f"### prefill-length sweep · KV={KV} · fresh server per length", flush=True)
for reps in (1, 2, 3, 4, 6, 8, 12, 16, 24, 32):
    p = "Answer briefly. " + FILLER*reps + "What is 2 plus 2?"
    if not start(f"{OUT}/pf_{KV}_{reps}.log"):
        print(f"  reps={reps:<3} server failed to start", flush=True); continue
    try: nt = tok(p)
    except Exception: nt = -1
    t,b = ask(p)
    print(f"  reps={reps:<3} prompt_tokens~{nt:<5} chars={len(t):<5} !frac={b:.2f}  "
          f"{'COLLAPSED' if b>0.5 else 'ok'}", flush=True)
    if b > 0.5: break
subprocess.run(["pkill","-x","llama-server"], capture_output=True)
print("\n### done", flush=True)
