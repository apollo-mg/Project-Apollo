"""Exact prefill-token boundary. Between 51 (clean) and 71 (collapsed)."""
import json, urllib.request, subprocess, time, os
BIN="/mnt/TG_2TB/Projects/Apollo/engines/buun-llama-cpp/build_rocm/bin"
MODEL="/home/mark/Downloads/Qwen3.8-27B-AD-IQ2_S.gguf"
KV=os.environ.get("PF_KV","turbo4")
OUT="/mnt/TG_2TB/Projects/Apollo/data/receipts/vbr-backend/raw"

def start(log):
    subprocess.run(["pkill","-x","llama-server"],capture_output=True); time.sleep(8)
    env=dict(os.environ, LD_LIBRARY_PATH=BIN)
    subprocess.Popen([f"{BIN}/llama-server","-m",MODEL,"-ngl","99","-c","4096",
        "-ctk",KV,"-ctv",KV,"-fa","on","--kv-unified","--jinja",
        "--host","127.0.0.1","--port","8080"],
        stdout=open(log,"w"),stderr=subprocess.STDOUT,env=env,start_new_session=True)
    for _ in range(150):
        try: urllib.request.urlopen("http://127.0.0.1:8080/health",timeout=2); return True
        except Exception: time.sleep(2)
    return False

def post(path,obj,t=900):
    req=urllib.request.Request(f"http://127.0.0.1:8080{path}",
        data=json.dumps(obj).encode(),headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(req,timeout=t).read())

def build(target):
    """Prompt whose CHAT-FORMATTED token count is ~target."""
    base="Answer briefly. "; tail=" What is 2 plus 2?"
    words=[]
    while True:
        p=base+" ".join(words)+tail
        n=len(post("/tokenize",{"content":p})["tokens"])
        if n>=target: return p,n
        words.append("alpha")

if not start(f"{OUT}/bisect_pf.log"):
    print("server failed"); raise SystemExit(1)
print(f"### exact prefill boundary · KV={KV} · one fresh server, one request per length", flush=True)
results={}
for target in range(52,74,2):
    p,n=build(target)
    if not start(f"{OUT}/bpf_{target}.log"):
        print(f"  target={target} server failed"); continue
    d=post("/v1/chat/completions",{"messages":[{"role":"user","content":p}],
           "temperature":0,"top_k":1,"n_predict":64})
    m=d["choices"][0]["message"]
    t=(m.get("content") or "")+(m.get("reasoning_content") or "")
    b=t.count("!")/max(len(t),1)
    pt=d.get("usage",{}).get("prompt_tokens")
    v="COLLAPSED" if b>0.5 else "ok"
    print(f"  content_tokens={n:<4} prompt_tokens(server)={str(pt):<5} !frac={b:.2f}  {v}", flush=True)
    results[n]={"prompt_tokens":pt,"bang":round(b,3),"verdict":v}
subprocess.run(["pkill","-x","llama-server"],capture_output=True)
json.dump(results,open(f"{OUT}/prefill_boundary.json","w"),indent=2)
print("\n### done", flush=True)
