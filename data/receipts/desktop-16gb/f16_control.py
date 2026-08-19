"""f16-KV control. Identical model, identical request sequence, KV codec the ONLY variable.

VBR arm (established, 3 reproductions): tier-2 sequence at n_predict=3072 collapses the
server into pure '!' output, permanently, at HTTP 200.

If f16 collapses too  -> VBR is innocent; this is IQ2_S weights or the HIP path.
If f16 survives       -> VBR is implicated by elimination rather than by guessing.
"""
import json, urllib.request, subprocess, time, os, sys
B="/mnt/TG_2TB/Projects/Apollo/engines/buun-llama-cpp/build_rocm/bin"
M="/home/mark/Downloads/Qwen3.8-27B-AD-IQ2_S.gguf"
S="/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad"
TMPL="{}\n\nThink briefly if you need to, then end your reply with exactly one line:\nExact Answer: <your answer>"
CAN="What is 17 multiplied by 23? Reply with just the number."
ITEMS=[("T2-01","A tank fills at 4 L/min and drains at 1.5 L/min. It starts at 20 L and holds 200 L. How many minutes until it is full?","72"),
       ("T2-02","A shirt costs 40 dollars after a 20 percent discount. What was the original price in dollars?","50"),
       ("T2-03","If today is Wednesday, what day of the week will it be in 100 days?","Friday"),
       ("T2-04","What is the output of this Python: print(len([x for x in range(20) if x % 3 == 0]))","7"),
       ("T2-05","Solve for x: 3x + 7 = 2x + 15. Give only the value of x.","8"),
       ("T2-06","A bag has 3 red and 5 blue marbles. Two are drawn without replacement. What is the probability both are red? Give the answer as a fraction in lowest terms.","3/28"),
       ("T2-07","How many bytes are in 2.5 kibibytes?","2560"),
       ("T2-08","Put these in ascending order and give only the second smallest: 0.5, 1/3, 0.45, 2/5","2/5"),
       ("T2-09","A train travels 240 km in 3 hours. At the same speed, how many kilometres does it travel in 50 minutes?","66.67"),
       ("T2-10","What is the smallest prime number greater than 90?","97")]

def start(kv, log):
    subprocess.run(["pkill","-x","llama-server"],capture_output=True); time.sleep(6)
    env=dict(os.environ, LD_LIBRARY_PATH=B)
    subprocess.Popen([f"{B}/llama-server","-m",M,"-ngl","99","-c","16384",
                      "-ctk",kv,"-ctv",kv,"--jinja","--host","127.0.0.1","--port","8080"],
                     stdout=open(log,"w"),stderr=subprocess.STDOUT,env=env,start_new_session=True)
    for _ in range(120):
        try: urllib.request.urlopen("http://127.0.0.1:8080/health",timeout=2); return True
        except Exception: time.sleep(2)
    return False

def ask(c,n):
    body={"messages":[{"role":"user","content":c}],"temperature":0,"top_k":1,"n_predict":n}
    req=urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",
        data=json.dumps(body).encode(),headers={"Content-Type":"application/json"})
    d=json.loads(urllib.request.urlopen(req,timeout=900).read())
    m=d["choices"][0]["message"]
    return (m.get("content") or "")+(m.get("reasoning_content") or ""), d["choices"][0].get("finish_reason")

def canary(tag):
    b,_=ask(CAN,256); bf=b.count("!")/max(len(b),1)
    ok = bf<0.5 and "391" in b
    print(f"  CANARY {tag:<10} {'ok' if ok else 'DEAD'}  (!frac={bf:.2f}, chars={len(b)})", flush=True)
    return ok

for kv in ("f16","vbr"):
    print(f"\n{'='*66}\n=== KV = {kv}\n{'='*66}", flush=True)
    if not start(kv, f"{S}/ctl_{kv}.log"):
        print("  server failed to start", flush=True); continue
    if not canary("before"):
        print("  server born broken — skipping arm", flush=True); continue
    dead_at=None
    for tag,q,gold in ITEMS:
        b,f=ask(TMPL.format(q),3072); bf=b.count("!")/max(len(b),1)
        hit = gold.lower().replace(" ","") in b.lower().replace(" ","").replace(",","")
        print(f"  {tag}  chars={len(b):<6} fin={f:<7} !frac={bf:.2f}  {'COLLAPSED' if bf>0.5 else ('has-answer' if hit else 'no-answer')}", flush=True)
        if bf>0.5 and dead_at is None:
            dead_at=tag
    canary("after")
    print(f"  --> first collapse: {dead_at or 'NONE — arm survived'}", flush=True)
subprocess.run(["pkill","-x","llama-server"],capture_output=True)
print("\ndone; servers stopped", flush=True)
