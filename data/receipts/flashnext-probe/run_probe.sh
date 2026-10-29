#!/bin/bash
# PREREG_FLASHNEXT_PROBE.md on .194: verify the three UD-IQ4_XS shards against FNIQ4's recorded hashes, serve them with
# FNIQ4's build and placement, run run_probe.py from the desktop, stop the server by its PID, power .194 off.
# Launch: systemd-run --user --unit=fn-probe --collect bash <this file>
set -u
R=/mnt/TG_2TB/Projects/Apollo; D=$R/data/receipts/flashnext-probe; PY=$R/venv_cachyos/bin/python3; LOG=$D/state.log
S=mark@10.0.0.194; H=http://10.0.0.194:8190; M='~/AI/Models/flashnext/Qwen3.8-Flash-Next-UD-IQ4_XS-0000'; BIN='$HOME/buun-0b278/build_sm60/bin/llama-server'
log () { echo "$(date '+%F %T') $*" >> $LOG; }
cleanup () {
  ssh $S "P=\$(cat ~/fnprobe.pid 2>/dev/null); [ -n \"\$P\" ] && [ \"\$(readlink /proc/\$P/exe)\" = \"$BIN\" ] && kill \$P && timeout 60 tail --pid=\$P -f /dev/null"
  timeout 120 $R/tools/s194.sh off >> $LOG 2>&1; log "host powered off"
}
log "start"
for i in $(seq 1 60); do ssh -o ConnectTimeout=5 -o BatchMode=yes $S true 2>/dev/null && break; sleep 10; done
trap cleanup EXIT
log ".194: kernel $(ssh $S uname -r); driver $(ssh $S 'nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1'); clocks $(ssh $S 'nvidia-smi --query-gpu=clocks.applications.graphics,power.limit --format=csv,noheader | tr "\n" " "')"
got=$(ssh $S "for k in 1 2 3; do sha256sum ${M}\${k}-of-00003.gguf | cut -c1-16; done | tr '\n' ,")
[ "$got" = "5ce89370720f8bf9,577a38a2392b40ca,d4634e6d84f0ebb0," ] || { log "ABORT: shard sha256 prefixes $got"; exit 1; }
log "shards verified: $got"
ssh $S "CUDA_VISIBLE_DEVICES=0,1,2,3 GGML_CUDA_ALLREDUCE=internal nohup $BIN -m ${M}1-of-00003.gguf -ngl 44 -sm layer -c 4096 -ctk f16 -ctv f16 -np 1 -fit off --host 0.0.0.0 --port 8190 > ~/fnprobe.log 2>&1 < /dev/null & echo \$! > ~/fnprobe.pid"
ok=0; for i in $(seq 1 180); do sleep 5; curl -s -m 3 $H/health | grep -q '"ok"' && { ok=1; break; }; done
[ $ok = 1 ] || { log "ABORT: server did not come up: $(ssh $S 'tail -3 ~/fnprobe.log')"; exit 1; }
log "server up: $(ssh $S 'nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr "\n" " "')"
$PY $D/run_probe.py --url $H --arm FNIQ4P --n 200 >> $D/raw/run_FNIQ4P.log 2>&1; log "probe rc=$?"
tail -2 $D/raw/run_FNIQ4P.log >> $LOG
log "DONE"
