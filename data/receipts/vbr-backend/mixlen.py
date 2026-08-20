"""Short generation followed by a long one — the exact fixture pattern, minimised.

Length alone: clean to 3072 (one request/server). Request count alone: clean to 5 (all short).
Untested: a SHORT request followed by a LONG one, which is what the fixture does
(canary n=256, then T2-01 n=3072).
"""
import json, urllib.request, subprocess, time, os

BIN   = "/mnt/TG_2TB/Projects/Apollo/engines/buun-llama-cpp/build_rocm/bin"
MODEL = "/home/mark/Downloads/Qwen3.8-27B-AD-IQ2_S.gguf"
KV    = os.environ.get("ML_KV","turbo4")
OUT   = "/mnt/TG_2TB/Projects/Apollo/data/receipts/vbr-backend/raw"
CAN   = "What is 17 multiplied by 23? Reply with just the number."
TMPL  = ("A tank fills at 4 L/min and drains at 1.5 L/min. It starts at 20 L and holds 200 L. "
         "How many minutes until it is full?\n\nThink briefly if you need to, then end your "
         "reply with exactly one line:\nExact Answer: <your answer>")

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

def ask(p,n):
    body={"messages":[{"role":"user","content":p}],"temperature":0,"top_k":1,"n_predict":n}
    req=urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",
        data=json.dumps(body).encode(),headers={"Content-Type":"application/json"})
    d=json.loads(urllib.request.urlopen(req,timeout=900).read())
    m=d["choices"][0]["message"]
    t=(m.get("content") or "")+(m.get("reasoning_content") or "")
    return t, t.count("!")/max(len(t),1), d["choices"][0].get("finish_reason")

SCEN = [
  ("A: canary256 -> item3072  (the fixture pattern)", [(CAN,256),(TMPL,3072)]),
  ("B: item3072 alone",                               [(TMPL,3072)]),
  ("C: canary256 -> canary3072 (same prompt, long)",  [(CAN,256),(CAN,3072)]),
]
print(f"### mixed-length sweep · KV={KV}", flush=True)
for name, steps in SCEN:
    print(f"\n-- {name} --", flush=True)
    if not start(f"{OUT}/ml_{KV}_{name[0]}.log"):
        print("  server failed to start", flush=True); continue
    for i,(p,n) in enumerate(steps,1):
        t,b,f = ask(p,n)
        print(f"  step{i} n={n:<5} chars={len(t):<5} fin={str(f):<7} !frac={b:.2f}  "
              f"{'COLLAPSED' if b>0.5 else 'ok'}", flush=True)
subprocess.run(["pkill","-x","llama-server"], capture_output=True)
print("\n### done", flush=True)
