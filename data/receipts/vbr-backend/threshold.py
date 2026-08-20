"""Where between 256 and 3072 generated tokens does the collapse start?

FRESH SERVER PER LENGTH. The collapse is permanent — once a server is poisoned every
later measurement on it is meaningless, so lengths cannot share a process.
ONE request per server, so this measures single-generation length, not cumulative load.
"""
import json, urllib.request, subprocess, time, os, sys

BIN   = "/mnt/TG_2TB/Projects/Apollo/engines/buun-llama-cpp/build_rocm/bin"
MODEL = "/home/mark/Downloads/Qwen3.8-27B-AD-IQ2_S.gguf"
KV    = os.environ.get("TH_KV", "turbo4")
OUT   = "/mnt/TG_2TB/Projects/Apollo/data/receipts/vbr-backend/raw"
PROMPT = ("Write a detailed step-by-step explanation of how binary search works, "
          "including a worked example on a sorted list of 16 integers.")

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

def ask(n):
    body = {"messages":[{"role":"user","content":PROMPT}],"temperature":0,"top_k":1,"n_predict":n}
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
    d = json.loads(urllib.request.urlopen(req, timeout=900).read())
    m = d["choices"][0]["message"]
    txt = (m.get("content") or "") + (m.get("reasoning_content") or "")
    return txt, d["choices"][0].get("finish_reason"), d.get("usage",{}).get("completion_tokens")

print(f"### collapse threshold sweep · KV={KV} · fresh server per length", flush=True)
res={}
for n in (256, 512, 768, 1024, 1280, 1536, 2048, 2560, 3072):
    if not start(f"{OUT}/th_{KV}_{n}.log"):
        print(f"  n_predict={n:<5} server failed to start", flush=True); continue
    txt, fin, ct = ask(n)
    bang = txt.count("!")/max(len(txt),1)
    # where in the output does the ! run begin?
    first = None
    run = 0
    for i,ch in enumerate(txt):
        run = run+1 if ch=="!" else 0
        if run >= 32: first = i-31; break
    verdict = "COLLAPSED" if bang > 0.5 else ("partial-!" if first is not None else "clean")
    print(f"  n_predict={n:<5} tokens={str(ct):<5} fin={str(fin):<7} !frac={bang:.2f} "
          f"first!run@char={first} -> {verdict}", flush=True)
    res[n]={"tokens":ct,"finish":fin,"bang":round(bang,3),"first_run":first,"verdict":verdict}
subprocess.run(["pkill","-x","llama-server"], capture_output=True)
json.dump(res, open(f"{OUT}/threshold_{KV}.json","w"), indent=2)
print("\n### done", flush=True)
