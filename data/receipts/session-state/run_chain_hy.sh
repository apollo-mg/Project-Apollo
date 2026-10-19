#!/bin/bash
# HY arms of PREREG_SESSION_STATE.md, run from the desktop (the transcript is local; .194 serves on :8190).
# HY4 -> G3 determinism re-check (segment 80 twice) -> swap .194 to Q8 -> HY8 -> agreement (HY4's prompts to HY8).
set -u
R=/mnt/TG_2TB/Projects/Apollo; PY=$R/venv_cachyos/bin/python3; E=$HOME/.local/share/apollo/session_state_eval
H=http://10.0.0.194:8190; TK='{"reasoning_effort":"no_think"}'
log () { echo "$(date +%T) $*" >> $E/chain_hy.log; }
want () { curl -s -m 10 $H/props | python3 -c "import sys,json; p=json.load(sys.stdin)['model_path']; sys.exit(0 if p.endswith('$1') else 1)"; }
log "start"; want Q4_K_M-imat.gguf || { log "ABORT: :8190 is not serving Q4"; exit 1; }
$PY $R/tools/session_state_eval.py arm-writer --name HY4 --host $H --template-kwargs "$TK" >> $E/chain_hy.log 2>&1 || { log "ABORT: HY4 failed"; exit 1; }
log "HY4 done; G3 re-check"
T=$($PY -c "import sys; sys.path.insert(0,'$R/tools'); import session_state_eval as V; print(V.T)")
S80=$($PY -c "import json; s={x['k']:x for x in json.load(open('$E/segments.json'))}[80]; print(s['start'], s['end'])")
rm -rf $E/g3_seg80; $PY $R/tools/session_state.py replay --transcript $T --start-byte ${S80% *} --end-byte ${S80#* } --out $E/g3_seg80 --host $H --template-kwargs "$TK" >> $E/chain_hy.log 2>&1
$PY - >> $E/chain_hy.log <<PYEOF
import json,sys; sys.path.insert(0,'$R/tools'); import session_state as S
a=json.load(open('$E/HY4/seg80/state.json')); b=json.load(open('$E/g3_seg80/state.json'))
strip=lambda st: [(k,v['kind'],v['text'],v['refs']) for k,v in sorted(st['items'].items())]
print('G3 identical' if strip(a)==strip(b) else 'G3 DIFFER')
PYEOF
Q8SHA=3ba2897dbb7e21e618cb65cec4b31498e59eca2960b381c5e0a0590e7ce8526b
for i in $(seq 1 60); do ssh mark@10.0.0.194 "grep -q $Q8SHA /dev/shm/hymem/q8.sha" && break; sleep 10; done
ssh mark@10.0.0.194 "grep -q $Q8SHA /dev/shm/hymem/q8.sha" || { log "ABORT: Q8 sha256 does not match Tencent's listing"; exit 1; }
log "Q8 sha256 verified; swap .194 to Q8"
ssh mark@10.0.0.194 'P=$(cat ~/bench/hymem-1019/server.pid); [ "$(readlink /proc/$P/exe)" = "$HOME/llama.cpp-beam/build_sm60/bin/llama-server" ] && kill $P; sleep 8; nohup ~/bench/hymem-1019/serve_hymem.sh /dev/shm/hymem/Hy-Memory-Step250-Q8_0.gguf Q8 > /dev/null 2>&1 < /dev/null & echo $! > ~/bench/hymem-1019/server.pid'
for i in $(seq 1 60); do sleep 5; want Q8_0.gguf && break; done
want Q8_0.gguf || { log "ABORT: Q8 server not up"; exit 1; }
log "Q8 up; HY8"
$PY $R/tools/session_state_eval.py arm-writer --name HY8 --host $H --template-kwargs "$TK" >> $E/chain_hy.log 2>&1 || { log "ABORT: HY8 failed"; exit 1; }
log "HY8 done; agreement"
$PY $R/tools/session_state_eval.py agree --a HY4 --b-host $H --b-name HY8 --template-kwargs "$TK" >> $E/chain_hy.log 2>&1
log "DONE"
