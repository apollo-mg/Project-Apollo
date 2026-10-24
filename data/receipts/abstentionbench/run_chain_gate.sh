#!/bin/bash
# PREREG_ABSTENTIONBENCH Arm 1 on the RX 9070 XT: pause Clef (VRAM), serve Llama 3.1 8B Instruct Q8_0 on :8197, subject
# inference over the fast subset, exact + blind judges (same server), analysis; Clef restored on exit, success or not.
# --cache-ram 0: the default 8 GiB host-RAM prompt cache fills even with cache_prompt:false, and on attempt 1 that
# pushed the desktop past systemd-oomd's limit (raw/attempt1_oom/). Launch with systemd-run so a kill still restores Clef.
set -u
R=/mnt/TG_2TB/Projects/Apollo; D=$R/data/receipts/abstentionbench; CK=/mnt/TG_2TB/toolchains/AbstentionBench
PY=/mnt/TG_2TB/toolchains/abench-venv/bin/python; BIN=$R/engines/llama_cpp_upstream_f74e2fa/build_rocm/bin/llama-server
M=/mnt/TG_2TB/models_small/gguf/Meta-Llama-3.1-8B-Instruct-Q8_0.gguf; H=http://127.0.0.1:8197; LOG=$D/raw/gate_state.log
log () { echo "$(date '+%F %T') $*" >> $LOG; }
cleanup () {
  [ -n "${SP:-}" ] && [ "$(readlink /proc/$SP/exe 2>/dev/null)" = "$BIN" ] && kill $SP && timeout 60 tail --pid=$SP -f /dev/null
  systemctl --user start apollo-clef.service apollo-clef-monitor.service; log "clef restored: $(systemctl --user is-active apollo-clef apollo-clef-monitor | tr '\n' ' ')"
}
trap cleanup EXIT
log "chain start"; systemctl --user stop apollo-clef-monitor.service apollo-clef.service; sleep 3
$BIN -m $M -ngl 99 -c 32768 -np 1 -ctk f16 -ctv f16 --cache-ram 0 --host 127.0.0.1 --port 8197 > $D/raw/server_gate.log 2>&1 < /dev/null & SP=$!
for i in $(seq 1 60); do sleep 3; curl -s -m 3 $H/health | grep -q '"ok"' && break; done
curl -s -m 3 $H/health | grep -q '"ok"' || { log "ABORT: server did not come up"; exit 1; }
log "server up pid $SP: $(curl -s $H/props | python3 -c 'import sys,json; print(json.load(sys.stdin)["model_path"])')"
$PY -s $D/run_abench.py --items $CK/fast_subset.jsonl --out $D/raw/LLAMA8.jsonl --host $H --expect-model Meta-Llama-3.1-8B-Instruct-Q8_0.gguf >> $LOG 2>&1
log "subject rc=$? rows=$(wc -l < $D/raw/LLAMA8.jsonl) errors=$(grep -c '"error"' $D/raw/LLAMA8.jsonl)"
for V in exact blind; do
  $PY -s $D/judge_abench.py --checkout $CK --items $CK/fast_subset.jsonl --responses $D/raw/LLAMA8.jsonl --out $D/raw/LLAMA8.judge_$V.jsonl --host $H --variant $V --expect-model Meta-Llama-3.1-8B-Instruct-Q8_0.gguf >> $LOG 2>&1
  log "judge $V rc=$? rows=$(wc -l < $D/raw/LLAMA8.judge_$V.jsonl)"
done
$PY -s $D/analyze_abench.py --checkout $CK --arm LLAMA8 >> $LOG 2>&1; log "analysis rc=$?"
log "DONE"
