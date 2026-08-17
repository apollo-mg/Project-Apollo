#!/usr/bin/env bash
# Pin WHICH factor breaks: the codec, the K/V asymmetry, tensor split, or MTP.
#
# Prior claim was overstated. Arms A/B differed only in KV codec, but BOTH carried
# -sm tensor AND --spec-type draft-mtp. Mark runs K=q8_0 V=turbo4 daily on this node
# without trouble, which rules out "q8_0 K is broken" outright.
#
#   P1  q8_0 K only, V f16      tensor+MTP   -- is it K?
#   P2  f16 K, q8_0 V           tensor+MTP   -- is it V? (fork has V-cache history:
#                                               turboquant#241 was V-cache corruption)
#   P3  q8_0 K+V, -sm layer,    MTP          -- does tensor split matter?
#   P4  q8_0 K+V, tensor,       NO MTP       -- does speculation matter?
#   P5  q8_0 K + turbo4 V,      tensor+MTP   -- Mark's daily codec pair, new build
set -u
B=~/buun_vbr/build/bin/llama-server
M=~/models/unsloth-Qwen3.8-27B-Q6_K.gguf
PORT=8091

probe() {
    for i in 1 2 3; do
        curl -s --max-time 400 "http://127.0.0.1:$PORT/v1/chat/completions" -H 'Content-Type: application/json' \
          -d "{\"messages\":[{\"role\":\"user\",\"content\":\"Explain how a $i-stage CPU pipeline works, with examples.\"}],\"temperature\":1.0,\"top_p\":0.95,\"top_k\":20,\"n_predict\":512,\"cache_prompt\":false}" \
        | python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: print('  req$i PARSE_FAIL'); raise SystemExit
if 'choices' not in d: print('  req$i ERR '+str(d)[:50]); raise SystemExit
m=d['choices'][0]['message']; t=(m.get('content') or '')+(m.get('reasoning_content') or '')
if not t: print('  req$i EMPTY'); raise SystemExit
run=mx=1; prev=''
for c in t:
    run = run+1 if c==prev else 1
    mx=max(mx,run); prev=c
print('  req$i '+('DEGENERATE' if (mx>200 or len(set(t))<12) else 'ok')+f' len={len(t)} maxrun={mx} uniq={len(set(t))}')
"
    done
}

run() { name=$1; shift
    echo "### $name : $*"
    pkill -x llama-server 2>/dev/null; sleep 4
    setsid nohup $B -m $M -ngl 99 -c 16384 --jinja --host 127.0.0.1 --port $PORT "$@" \
        > ~/srv_kvpin_$name.log 2>&1 < /dev/null &
    for i in $(seq 1 90); do
        curl -s --max-time 5 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q '"status":"ok"' && { probe; echo; return; }
        sleep 4
    done
    echo "  SERVER FAILED"; tail -3 ~/srv_kvpin_$name.log; echo; }

# REORDERED: P3 first. Hypothesis is that -sm tensor SHARDS the KV cache and a
# quantized block straddles the shard boundary -- f16 has no block structure to
# straddle, which is why arm A was clean at the same ctx and same split mode.
# -sm layer does not shard the cache, so P3 clean == mechanism confirmed.
run P3 -sm layer  -ts 1,1 --spec-type draft-mtp -ctk q8_0 -ctv q8_0
run P4 -sm tensor -ts 1,1                       -ctk q8_0 -ctv q8_0
run P5 -sm tensor -ts 1,1 --spec-type draft-mtp -ctk q8_0 -ctv turbo4
run P2 -sm tensor -ts 1,1 --spec-type draft-mtp -ctv q8_0
run P1 -sm tensor -ts 1,1 --spec-type draft-mtp -ctk q8_0
run P6 -sm tensor -ts 1,1                       -ctk q8_0 -ctv turbo4
pkill -x llama-server 2>/dev/null
echo "### KV PIN DONE"
