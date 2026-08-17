#!/usr/bin/env bash
# Follow-up: is the defect q8_0-SPECIFIC, or does it hit any quantized KV under sharding?
# And is there a config that gets BOTH the 1.62x tensor-split speed AND correct output?
#
#  P7  turbo8 K + turbo4 V   the "everything we know" config: asymmetric (K is the
#                            sensitive side and gets more bits), both buun codecs,
#                            tensor split + MTP. The get-both candidate.
#  P8  vbr K+V               VBR enters at f16 and degrades only under pressure, so it
#                            may sidestep the quantized path entirely at low fill.
#  P9  q4_0 K+V              THE DISCRIMINATOR. If q4_0 also collapses, this is "stock
#                            quantized KV codecs under tensor sharding". If q4_0 is
#                            clean while q8_0 dies, the bug is q8_0-specific and much
#                            narrower -- a far more actionable report.
# P10  turbo3_tcq K+V        the margin winner from tcq-leg3, under sharding
set -u
B=~/buun_vbr/build/bin/llama-server
M=~/models/unsloth-Qwen3.8-27B-Q6_K.gguf
PORT=8092
probe() {
  for i in 1 2 3; do
    curl -s --max-time 400 "http://127.0.0.1:$PORT/v1/chat/completions" -H "Content-Type: application/json" \
      -d "{\"messages\":[{\"role\":\"user\",\"content\":\"Explain how a $i-stage CPU pipeline works, with examples.\"}],\"temperature\":1.0,\"top_p\":0.95,\"top_k\":20,\"n_predict\":512,\"cache_prompt\":false}" \
    | python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: print(\"  req$i PARSE_FAIL\"); raise SystemExit
if \"choices\" not in d: print(\"  req$i ERR \"+str(d)[:50]); raise SystemExit
m=d[\"choices\"][0][\"message\"]; t=(m.get(\"content\") or \"\")+(m.get(\"reasoning_content\") or \"\")
if not t: print(\"  req$i EMPTY\"); raise SystemExit
run=mx=1; prev=\"\"
for c in t:
    run = run+1 if c==prev else 1
    mx=max(mx,run); prev=c
print(\"  req$i \"+(\"DEGENERATE\" if (mx>200 or len(set(t))<12) else \"ok\")+f\" len={len(t)} maxrun={mx} uniq={len(set(t))}\")
"
  done
}
run() { name=$1; shift; echo "### $name : $*"
  pkill -x llama-server 2>/dev/null; sleep 4
  setsid nohup $B -m $M -ngl 99 -c 16384 --jinja --host 127.0.0.1 --port $PORT "$@" > ~/srv_kvpin2_$name.log 2>&1 < /dev/null &
  for i in $(seq 1 90); do
    curl -s --max-time 5 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q "\"status\":\"ok\"" && { probe; echo; return; }
    sleep 4
  done
  echo "  SERVER FAILED"; tail -3 ~/srv_kvpin2_$name.log; echo; }
run P9  -sm tensor -ts 1,1 --spec-type draft-mtp -ctk q4_0   -ctv q4_0
run P7  -sm tensor -ts 1,1 --spec-type draft-mtp -ctk turbo8 -ctv turbo4
run P8  -sm tensor -ts 1,1 --spec-type draft-mtp -ctk vbr    -ctv vbr
run P10 -sm tensor -ts 1,1 --spec-type draft-mtp -ctk turbo3_tcq -ctv turbo3_tcq
pkill -x llama-server 2>/dev/null
echo "### KV PIN2 DONE"
