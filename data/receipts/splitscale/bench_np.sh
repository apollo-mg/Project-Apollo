#!/usr/bin/env bash
# Does concurrent-slot batching beat sequential requests? See PREREG_NP.md.
set -u
B=~/llama_stock/build_puzzle/bin/llama-server
M=~/AI/Models/Qwen3.8-27B/Qwen3.8-27B-Q6_K.gguf
export GGML_CUDA_ALLREDUCE=internal
PORT=8090

for NP in 1 2 4 8; do
  echo "### -np $NP   $(date -Iseconds)"
  CUDA_VISIBLE_DEVICES=0,1 numactl --cpunodebind=0 --membind=0 \
    $B -m $M -ngl 99 -c 16384 -np $NP -sm tensor -fit off -ctk f16 -ctv f16 \
    --host 127.0.0.1 --port $PORT > /tmp/np_$NP.log 2>&1 &
  SRV=$!
  READY=0
  for i in $(seq 1 90); do
    if [ "$(curl -s -o /dev/null -w %{http_code} http://127.0.0.1:$PORT/health 2>/dev/null)" = "200" ]; then
      READY=1; break
    fi
    kill -0 $SRV 2>/dev/null || { echo "    SERVER DIED before ready:"; tail -3 /tmp/np_$NP.log | sed 's/^/      /'; break; }
    sleep 2
  done
  if [ "$READY" != "1" ]; then echo "    SKIPPING np=$NP — server never became ready"; kill -9 $SRV 2>/dev/null; sleep 2; echo; continue; fi
  python3 - "$NP" "$PORT" <<'PY'
import json, sys, time, threading, urllib.request
NP=int(sys.argv[1]); PORT=sys.argv[2]
N_GEN=256
# distinct prompts — identical ones would measure the prompt cache, not throughput
PROMPTS=[f"Write exactly {200+i*7} words describing subsystem number {i} of a distributed "
         f"storage engine, focusing on its failure modes." for i in range(NP)]
res=[None]*NP
def work(i):
    body={"messages":[{"role":"user","content":PROMPTS[i]}],"temperature":0,"top_k":1,
          "n_predict":N_GEN,"cache_prompt":False}
    r=urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions",
        data=json.dumps(body).encode(),headers={"Content-Type":"application/json"})
    t0=time.time()
    with urllib.request.urlopen(r,timeout=1200) as f: d=json.loads(f.read())
    dt=time.time()-t0
    u=d.get("usage") or {}
    res[i]=(u.get("completion_tokens") or 0, dt)
for rep in range(2):
    ts=[threading.Thread(target=work,args=(i,)) for i in range(NP)]
    t0=time.time(); [t.start() for t in ts]; [t.join() for t in ts]; wall=time.time()-t0
    tok=sum(r[0] for r in res if r); per=[r[0]/r[1] for r in res if r and r[1]>0]
    print(f"    rep{rep+1}  np={NP}  aggregate {tok/wall:7.2f} t/s   "
          f"per-request {sum(per)/len(per):6.2f} t/s   wall {wall:6.1f}s   tokens {tok}", flush=True)
PY
  kill $SRV 2>/dev/null; for i in $(seq 1 10); do sleep 2; kill -0 $SRV 2>/dev/null || break; done
  kill -9 $SRV 2>/dev/null; sleep 3
  echo
done
echo "### finished $(date -Iseconds)"
