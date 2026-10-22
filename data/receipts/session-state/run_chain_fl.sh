#!/bin/bash
# Addendum 1 arm FL8: Flint Q8 on .194 :8190 (--reasoning-budget 0), the FROZEN writer 67328fda via SESSION_STATE_PY,
# then a G3 determinism re-run of segment 80, then score + analyze over all arms.
set -u
R=/mnt/TG_2TB/Projects/Apollo; PY=$R/venv_cachyos/bin/python3; E=$HOME/.local/share/apollo/session_state_eval
H=http://10.0.0.194:8190; TK='{}'; export SESSION_STATE_PY=$E/frozen/session_state_67328fda.py
log () { echo "$(date +%T) $*" >> $E/chain_fl.log; }
want () { curl -s -m 10 $H/props | python3 -c "import sys,json; p=json.load(sys.stdin)['model_path']; sys.exit(0 if p.endswith('$1') else 1)"; }
log "start"; want flint-Q8_0.gguf || { log "ABORT: :8190 is not serving flint-Q8_0"; exit 1; }
$PY $R/tools/session_state_eval.py arm-writer --name FL8 --host $H --template-kwargs "$TK" >> $E/chain_fl.log 2>&1 || { log "ABORT: FL8 failed"; exit 1; }
log "FL8 done; G3 re-check"
T=$($PY -c "import sys; sys.path.insert(0,'$R/tools'); import session_state_eval as V; print(V.T)")
S80=$($PY -c "import json; s={x['k']:x for x in json.load(open('$E/segments.json'))}[80]; print(s['start'], s['end'])")
rm -rf $E/g3fl_seg80; $PY $SESSION_STATE_PY replay --transcript $T --start-byte ${S80% *} --end-byte ${S80#* } --out $E/g3fl_seg80 --host $H --template-kwargs "$TK" >> $E/chain_fl.log 2>&1
$PY - >> $E/chain_fl.log <<PYEOF
import json
a=json.load(open('$E/FL8/seg80/state.json')); b=json.load(open('$E/g3fl_seg80/state.json'))
strip=lambda st: [(k,v['kind'],v['text'],v['refs']) for k,v in sorted(st['items'].items())]
print('G3 identical' if strip(a)==strip(b) else 'G3 DIFFER')
PYEOF
log "DONE"
