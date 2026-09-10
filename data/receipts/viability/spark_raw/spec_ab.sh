#!/usr/bin/env bash
# Speculative decoding A/B: Spark-1.7B drafting for Spark-4B, same family.
# Fixed prompt, fixed max_tokens, temp 0 so both arms generate the same text and the
# comparison is decode rate on identical work.
set -u
B=/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad/spark-llama/build_rocm/bin/llama-server
M=/mnt/TG_2TB/AI/Models/spark25/Spark-X2.5-4B-Q4_K_M.gguf
D=/mnt/TG_2TB/AI/Models/spark25/Spark-X2.5-1.7B-Q4_K_M.gguf
OUT=~/spec_ab.log; : > $OUT; exec 3>>$OUT
say(){ echo "$*" >&3; }
say "### spec decode A/B $(date -Iseconds)"
arm(){
  local name="$1"; shift
  local log=/tmp/spec_$name.log
  setsid nohup $B -m $M -ngl 99 -c 8192 -np 1 -fa on --host 127.0.0.1 --port 8087 "$@" > $log 2>&1 < /dev/null &
  local pid=$!; local i=0
  while [ $i -lt 60 ]; do grep -qa "listening on\|failed to load\|error" $log && break; i=$((i+1)); sleep 2; done
  say ""; say "======== arm $name  extra args: $*"
  if ! grep -qa "listening on" $log; then say "  did NOT start"; grep -aiE "error|failed" $log | head -2 >&3
  else
    for r in 1 2; do
      python3 - <<'PY' > /dev/null 2>&1
import json,urllib.request
b={"messages":[{"role":"user","content":"Write a detailed step-by-step guide to configuring a systemd service unit, covering unit files, dependencies, restart policies, and journald logging."}],
   "max_tokens":600,"temperature":0}
r=urllib.request.Request("http://127.0.0.1:8087/v1/chat/completions",data=json.dumps(b).encode(),headers={"Content-Type":"application/json"})
urllib.request.urlopen(r,timeout=600).read()
PY
    done
    grep -ao "tg = *[0-9.]* t/s" $log | grep -oE "[0-9.]+" | sort -n | awk '{a[NR]=$1} END{if(NR>0) printf "  tg samples=%d  median %.2f  max %.2f t/s\n", NR, a[int(NR/2)+1], a[NR]}' >&3
    grep -aoE "draft acceptance[^,]*|n_drafted[ =]+[0-9]+|n_accept[ed]*[ =]+[0-9]+" $log | tail -4 | sed 's/^/  /' >&3 || true
  fi
  kill $pid 2>/dev/null; local j=0
  while kill -0 $pid 2>/dev/null && [ $j -lt 20 ]; do j=$((j+1)); sleep 1; done
  kill -9 $pid 2>/dev/null
  while ss -ltn 2>/dev/null | grep -q ":8087 "; do sleep 1; done
}
arm baseline
arm draft --model-draft $D --spec-type draft-simple --spec-draft-n-max 4
say ""; say "######## SPEC AB DONE $(date -Iseconds)"
