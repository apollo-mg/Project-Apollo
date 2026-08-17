#!/usr/bin/env bash
# Isolate what made the .73 server collapse into emitting '/' for a whole budget.
#
# Four variables changed across working -> degraded -> fixed, and I previously
# described it as three. Actual history:
#
#   rounds 1-2  -c 16384  f16   default slots  default reuse  -> fine
#   degraded    -c 40960  q8_0  default slots  default reuse  -> '/' collapse
#   fixed       -c 16384  f16   -np 1          --cache-reuse 0 -> fine
#
# Slot reuse was ACTIVE in the working config, so it is not sufficient alone.
# That leaves KV precision and context size, plus their interaction.
#
#   A  16384 f16   default   negative control -- must stay clean
#   B  16384 q8_0  default   KV precision alone
#   C  40960 f16   default   context size alone
#   D  40960 q8_0  default   the degraded config -- must reproduce, or the test
#                            is not triggering and every other arm is meaningless
#
# D is the load-bearing arm. If D stays clean the trigger is something else
# (elapsed time, total tokens, a specific prompt) and this design is wrong.
set -u
B=~/buun_vbr/build/bin/llama-server
M=~/models/unsloth-Qwen3.8-27B-Q6_K.gguf
PORT=8090
REQS=${REQS:-8}
NPRED=${NPRED:-2048}

probe() {   # emits: index<TAB>verdict<TAB>detail
    for i in $(seq 1 "$REQS"); do
        r=$(curl -s --max-time 600 "http://127.0.0.1:$PORT/v1/chat/completions" \
            -H 'Content-Type: application/json' \
            -d "{\"messages\":[{\"role\":\"user\",\"content\":\"Explain concept number $i: describe how a $i-stage pipeline works in a CPU, with examples.\"}],\"temperature\":1.0,\"top_p\":0.95,\"top_k\":20,\"n_predict\":$NPRED}")
        echo "$r" | python3 -c "
import json,sys,re,collections
try: d=json.load(sys.stdin)
except Exception: print('$i\tPARSE_FAIL\t'); raise SystemExit
if 'choices' not in d: print('$i\tERR\t'+str(d)[:60]); raise SystemExit
m=d['choices'][0]['message']
t=(m.get('content') or '')+(m.get('reasoning_content') or '')
if not t: print('$i\tEMPTY\t'); raise SystemExit
# degeneracy: longest run of one char, and unique-char ratio
run=maxrun=1; prev=''
for c in t:
    run = run+1 if c==prev else 1
    maxrun=max(maxrun,run); prev=c
uniq=len(set(t))/max(1,min(len(t),500))
bad = maxrun>40 or len(set(t))<12
print('$i\t'+('DEGENERATE' if bad else 'ok')+f'\tlen={len(t)} maxrun={maxrun} uniq={len(set(t))}')
"
    done
}

for arm in "A 16384 f16" "B 16384 q8_0" "C 40960 f16" "D 40960 q8_0"; do
    set -- $arm; name=$1; ctx=$2; kv=$3
    echo "### ARM $name  ctx=$ctx kv=$kv  (default slots, default cache-reuse)"
    pkill -x llama-server 2>/dev/null; sleep 4
    if [ "$kv" = f16 ]; then KVARGS=""; else KVARGS="-ctk $kv -ctv $kv"; fi
    setsid nohup $B -m $M -ngl 99 -sm tensor -ts 1,1 --spec-type draft-mtp \
        -c "$ctx" $KVARGS --jinja --host 127.0.0.1 --port $PORT \
        > ~/srv_iso_$name.log 2>&1 < /dev/null &
    ok=0
    for i in $(seq 1 90); do
        curl -s --max-time 5 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q '"status":"ok"' && { ok=1; break; }
        sleep 4
    done
    [ "$ok" = 1 ] || { echo "  SERVER FAILED TO START"; tail -3 ~/srv_iso_$name.log; echo; continue; }
    probe
    echo
done
pkill -x llama-server 2>/dev/null
echo "### ISOLATION DONE"
