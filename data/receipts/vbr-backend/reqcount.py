"""Is the trigger the SECOND request rather than generation length?

The length sweep was clean at every length up to 3072 with ONE request per server.
The fixture collapses at T2-01 — which is the second request, after the canary.
Same short prompt every time; only the request index varies.
"""
import json, urllib.request, subprocess, time, os

BIN   = "/mnt/TG_2TB/Projects/Apollo/engines/buun-llama-cpp/build_rocm/bin"
MODEL = "/home/mark/Downloads/Qwen3.8-27B-AD-IQ2_S.gguf"
KV    = os.environ.get("RC_KV","turbo4")
OUT   = "/mnt/TG_2TB/Projects/Apollo/data/receipts/vbr-backend/raw"
Q     = "What is 17 multiplied by 23? Reply with just the number."

def start(log):
    subprocess.run(["pkill","-x","llama-server"], capture_output=True); time.sleep(8)
    env = dict(os.environ, LD_LIBRARY_PATH=BIN)
    subprocess.Popen([f"{BIN}/llama-server","-m",MODEL,"-ngl","99","-c","4096",
                      "-ctk",KV,"-ctv",KV,"-fa","on","--kv-unified",
                      "--jinja","--host","127.0.0.1","--port","8080"],
                     stdout=open(log,"w"), stderr=subprocess.STDOUT, env=env, start_new_session=True)
    for _ in range(150):
        try: urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=2); return True
        except Exception: time.sleep(2)
    return False

def ask(prompt, n=256):
    body={"messages":[{"role":"user","content":prompt}],"temperature":0,"top_k":1,"n_predict":n}
    req=urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
    d=json.loads(urllib.request.urlopen(req,timeout=900).read())
    m=d["choices"][0]["message"]
    t=(m.get("content") or "")+(m.get("reasoning_content") or "")
    return t, t.count("!")/max(len(t),1)

print(f"### request-index sweep · KV={KV} · identical short prompt each time", flush=True)
for trial in ("same-prompt", "different-prompts"):
    print(f"\n-- {trial} --", flush=True)
    if not start(f"{OUT}/rc_{KV}_{trial}.log"):
        print("  server failed to start", flush=True); continue
    for i in range(1,6):
        p = Q if trial=="same-prompt" else f"What is {17+i} multiplied by {23+i}? Reply with just the number."
        t,b = ask(p)
        print(f"  request #{i}  chars={len(t):<5} !frac={b:.2f}  {'COLLAPSED' if b>0.5 else 'ok'}", flush=True)
        if b>0.5: break
subprocess.run(["pkill","-x","llama-server"], capture_output=True)
print("\n### done", flush=True)
