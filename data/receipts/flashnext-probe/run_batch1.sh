#!/bin/bash
# PREREG_FLASHNEXT_PROBE.md Addendum 1 on .194: three arms with the same probe (run_probe.py, seeds 1-400), one fresh
# server per arm, each file's shards hashed against Unsloth's published sha256 first; stop by PID; power off at the end.
# Launch: systemd-run --user --unit=fn-probe-b1 --collect bash <this file>
set -u
R=/mnt/TG_2TB/Projects/Apollo; D=$R/data/receipts/flashnext-probe; PY=$R/venv_cachyos/bin/python3; LOG=$D/state.log
S=mark@10.0.0.194; H=http://10.0.0.194:8190; BIN='$HOME/buun-0b278/build_sm60/bin/llama-server'
IQ4='~/strata-data/models/unsloth-UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-0000'; Q2='~/AI/Models/flashnext_q2/Qwen3.8-Flash-Next-UD-Q2_K_XL-0000'
FLAGS='-sm layer -c 4096 -ctk f16 -ctv f16 -np 1 -fit off --host 0.0.0.0 --port 8190'
log () { echo "$(date '+%F %T') $*" >> $LOG; }
stop () { ssh $S "P=\$(cat ~/fnprobe.pid 2>/dev/null); [ -n \"\$P\" ] && [ \"\$(readlink /proc/\$P/exe)\" = \"$BIN\" ] && kill \$P && timeout 60 tail --pid=\$P -f /dev/null; rm -f ~/fnprobe.pid"; }
cleanup () { stop; timeout 120 $R/tools/s194.sh off >> $LOG 2>&1; log "host powered off"; }
arm () {   # name, shard prefix, expected sha256 prefixes (comma list with trailing comma), -ngl
  local got; got=$(ssh $S "for k in 1 2 3; do sha256sum ${2}\${k}-of-00003.gguf | cut -c1-16; done | tr '\n' ,")
  [ "$got" = "$3" ] || { log "$1 SKIPPED: shard sha256 prefixes '$got' != '$3'"; return 1; }
  ssh $S "CUDA_VISIBLE_DEVICES=0,1,2,3 GGML_CUDA_ALLREDUCE=internal nohup $BIN -m ${2}1-of-00003.gguf -ngl $4 $FLAGS > ~/fnprobe_$1.log 2>&1 < /dev/null & echo \$! > ~/fnprobe.pid"
  local ok=0; for i in $(seq 1 180); do sleep 5; curl -s -m 3 $H/health | grep -q '"ok"' && { ok=1; break; }; done
  [ $ok = 1 ] || { log "$1 ABORT: server did not come up: $(ssh $S "tail -2 ~/fnprobe_$1.log")"; stop; return 1; }
  log "$1 up (-ngl $4, shards $got): $(ssh $S 'nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr "\n" " "')"
  $PY $D/run_probe.py --url $H --arm $1 --n 400 >> $D/raw/run_$1.log 2>&1; log "$1 probe rc=$?: $(tail -1 $D/raw/run_$1.log)"
  stop
}
log "batch 1 start"
for i in $(seq 1 60); do ssh -o ConnectTimeout=5 -o BatchMode=yes $S true 2>/dev/null && break; sleep 10; done
trap cleanup EXIT
log ".194: kernel $(ssh $S uname -r); driver $(ssh $S 'nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1'); clocks $(ssh $S 'nvidia-smi --query-gpu=clocks.applications.graphics,power.limit --format=csv,noheader | tr "\n" " "')"
arm FNIQ4P "$IQ4" "5ce89370720f8bf9,577a38a2392b40ca,d4634e6d84f0ebb0," 44
arm FNQ2P44 "$Q2" "a4f3b21e77353999,2e3bf1ee7d2a04e2,ec8c106759fdf4f4," 44
arm FNQ2P99 "$Q2" "a4f3b21e77353999,2e3bf1ee7d2a04e2,ec8c106759fdf4f4," 99
$PY $D/analyze_probe.py >> $LOG 2>&1; log "analysis rc=$?"
log "batch 1 DONE"
