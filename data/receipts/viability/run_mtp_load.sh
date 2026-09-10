#!/usr/bin/env bash
# MTP x concurrency sweep. See PREREG_MTP_UNDER_LOAD.md.
# -c scales with np so per-slot context is constant at 2048.
set -u
B=/mnt/TG_2TB/Projects/Apollo/engines/buun-llama-cpp/build_rocm/bin/llama-server
M="/mnt/TG_2TB/AI/Models/gsq-rco/Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf"
OUT=mtp_load.log; : > $OUT; exec 3>>$OUT
say(){ echo "$*" >&3; }
say "### MTP x concurrency $(date -Iseconds)"
say "model=$(basename "$M")"
cell(){
  local np="$1"; local mtp="$2"
  local ctx=$(( 2048 * np ))
  local extra=""; [ "$mtp" = "on" ] && extra="--spec-type draft-mtp"
  local log=/tmp/mtpload_${np}_${mtp}.log
  setsid nohup $B -m "$M" -ngl 99 -c $ctx -np $np -fa on $extra \
      --host 127.0.0.1 --port 8088 > $log 2>&1 < /dev/null &
  local pid=$!; local i=0
  while [ $i -lt 90 ]; do grep -qa "listening on\|failed to load\|error while" $log && break; i=$((i+1)); sleep 2; done
  say ""; say "======== np=$np mtp=$mtp  (ctx=$ctx)"
  if ! grep -qa "listening on" $log; then
    say "  did NOT start"; grep -aiE "error|failed" $log | head -2 | sed 's/^/    /' >&3
  else
    local t0=$(date +%s.%N)
    python3 - "$np" <<'PY' > /tmp/mtpload_client.txt 2>&1
import json,sys,threading,urllib.request,time
np=int(sys.argv[1]); res=[]
def one(i):
    b={"messages":[{"role":"user","content":"Explain in detail how a Linux kernel module is built, loaded, and unloaded, including DKMS."}],
       "max_tokens":300,"temperature":0,"seed":1234}
    t=time.time()
    r=urllib.request.Request("http://127.0.0.1:8088/v1/chat/completions",data=json.dumps(b).encode(),
        headers={"Content-Type":"application/json"})
    d=json.loads(urllib.request.urlopen(r,timeout=900).read())
    res.append((d["usage"]["completion_tokens"], time.time()-t))
ts=[threading.Thread(target=one,args=(i,)) for i in range(np)]
[t.start() for t in ts]; [t.join() for t in ts]
tot=sum(x[0] for x in res); wall=max(x[1] for x in res)
print(f"agg_tokens={tot} wall={wall:.2f} agg_tps={tot/wall:.2f} per_req_tps={sum(x[0]/x[1] for x in res)/len(res):.2f} n={len(res)}")
PY
    local t1=$(date +%s.%N)
    sed 's/^/  /' /tmp/mtpload_client.txt >&3
    say "  wall_total=$(echo "$t1 - $t0" | bc)s"
    grep -ao "draft acceptance = [0-9.]* ([^)]*)" $log | tail -1 | sed 's/^/  /' >&3 || say "  (no draft acceptance line)"
    sync
  fi
  kill $pid 2>/dev/null; local j=0
  while kill -0 $pid 2>/dev/null && [ $j -lt 30 ]; do j=$((j+1)); sleep 1; done
  kill -9 $pid 2>/dev/null
  while ss -ltn 2>/dev/null | grep -q ":8088 "; do sleep 1; done
}
for np in 1 2 4 8; do for m in off on; do cell $np $m; done; done
say ""; say "######## MTP LOAD DONE $(date -Iseconds)"
