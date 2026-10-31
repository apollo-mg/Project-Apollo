#!/bin/bash
# PREREG_FLASHNEXT_PROBE.md Addendum 4, Deviation 2 on .194: the three setups, one fresh server each (shards hashed first),
# ladder_self.py per setup; stop by PID; power off at the end. Rerunning resumes by seed.
# Launch: systemd-run --user --unit=fn-selfgen --collect bash <this file>
set -u
R=/mnt/TG_2TB/Projects/Apollo; D=$R/data/receipts/flashnext-probe; PY=$R/venv_cachyos/bin/python3; LOG=$D/state.log
S=mark@10.0.0.194; H=http://10.0.0.194:8190; BIN='$HOME/buun-0b278/build_sm60/bin/llama-server'
IQ4='~/strata-data/models/unsloth-UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-0000'; Q2='~/AI/Models/flashnext_q2/Qwen3.8-Flash-Next-UD-Q2_K_XL-0000'
FLAGS='-sm layer -c 4096 -ctk f16 -ctv f16 -np 1 -fit off --host 0.0.0.0 --port 8190'
log () { echo "$(date '+%F %T') $*" >> $LOG; }
stop () { ssh $S "P=\$(cat ~/fnprobe.pid 2>/dev/null); [ -n \"\$P\" ] && [ \"\$(readlink /proc/\$P/exe)\" = \"$BIN\" ] && kill \$P && timeout 60 tail --pid=\$P -f /dev/null; rm -f ~/fnprobe.pid"; }
cleanup () { stop; timeout 120 $R/tools/s194.sh off >> $LOG 2>&1; log "host powered off"; }
arm () {
  # name, shard prefix, expected sha256 prefixes, -ngl, Addendum 3 arm
  local got rc; got=$(ssh $S "for k in 1 2 3; do sha256sum ${2}\${k}-of-00003.gguf | cut -c1-16; done | tr '\n' ,")
  [ "$got" = "$3" ] || { log "$1 ABORT: shard sha256 prefixes '$got' != '$3'"; return 1; }
  ssh $S "CUDA_VISIBLE_DEVICES=0,1,2,3 GGML_CUDA_ALLREDUCE=internal nohup $BIN -m ${2}1-of-00003.gguf -ngl $4 $FLAGS > ~/fnprobe_S$1.log 2>&1 < /dev/null & echo \$! > ~/fnprobe.pid"
  local ok=0; for i in $(seq 1 180); do sleep 5; curl -s -m 3 $H/health | grep -q '"ok"' && { ok=1; break; }; done
  [ $ok = 1 ] || { log "$1 ABORT: server did not come up"; stop; return 1; }
  log "$1 selfgen up: $(ssh $S 'nvidia-smi --query-gpu=clocks.gr,memory.used --format=csv,noheader | tr "\n" ";"')"
  $PY $D/ladder_self.py --url $H --setup $1 --td $5 >> $D/raw/run_S$1.log 2>&1; rc=$?; log "$1 selfgen rc=$rc"; tail -2 $D/raw/run_S$1.log | cut -c1-200 >> $LOG
  stop; return $rc
}
timeout 300 $R/tools/s194.sh on >> $LOG 2>&1
log "deviation 2 start"
for i in $(seq 1 60); do ssh -o ConnectTimeout=5 -o BatchMode=yes $S true 2>/dev/null && break; sleep 10; done
trap cleanup EXIT
arm IQ4_44 "$IQ4" "5ce89370720f8bf9,577a38a2392b40ca,d4634e6d84f0ebb0," 44 TDIQ4_44 || exit 1
arm Q2_44 "$Q2" "a4f3b21e77353999,2e3bf1ee7d2a04e2,ec8c106759fdf4f4," 44 TDQ2_44 || exit 1
arm Q2_99 "$Q2" "a4f3b21e77353999,2e3bf1ee7d2a04e2,ec8c106759fdf4f4," 99 TDQ2_99 || exit 1
$PY $D/analyze_ladder.py >> $D/raw/analyze_ladder.log 2>&1; log "analysis rc=$?"
log "deviation 2 DONE"
