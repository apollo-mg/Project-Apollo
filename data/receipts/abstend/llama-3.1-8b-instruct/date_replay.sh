#!/bin/bash
# PREREG_DRIFT_CAUSE.md Addendum 1: same binary, file and flags as LLAMA8 and L31AB. Clef paused; ExecStopPost restores it.
# Launch: systemd-run --user --unit=date-replay --collect -p ExecStopPost="/usr/bin/systemctl --user start apollo-clef.service apollo-clef-monitor.service" bash <this file> [label]
set -u
L=${1:+_$1}; R=/mnt/TG_2TB/Projects/Apollo; D=$R/data/receipts/abstend/llama-3.1-8b-instruct
BIN=$R/engines/llama_cpp_upstream_f74e2fa/build_rocm/bin/llama-server
M=/mnt/TG_2TB/models_small/gguf/Meta-Llama-3.1-8B-Instruct-Q8_0.gguf
C=$(for c in /sys/class/drm/card*/device; do [ "$(cat $c/device 2>/dev/null)" = 0x7550 ] && echo $c; done | head -1)
{ date '+%F %T %Z'; uname -r; pacman -Q linux-cachyos linux-firmware-amdgpu mesa llvm-libs; echo "mec $(cat $C/fw_version/mec_fw_version)"; echo "pcie $(cat $C/current_link_speed) x$(cat $C/current_link_width)"; sha256sum $BIN | cut -c1-16; } > $D/date_replay$L.state
systemctl --user stop apollo-clef-monitor.service apollo-clef.service; sleep 3
$BIN -m $M -ngl 99 -c 32768 -np 1 -ctk f16 -ctv f16 --cache-ram 0 --host 127.0.0.1 --port 8197 > $R/data/receipts/abstentionbench/raw/date_replay${L}_server.log 2>&1 < /dev/null & SP=$!
for i in $(seq 1 60); do sleep 3; curl -s -m 3 127.0.0.1:8197/health | grep -q '"ok"' && break; done
python3 -I $D/date_replay.py $D/date_replay$L.json > $D/date_replay$L.txt 2>&1
[ "$(readlink /proc/$SP/exe)" = "$(readlink -f $BIN)" ] && kill $SP && timeout 60 tail --pid=$SP -f /dev/null
echo DONE >> $D/date_replay$L.txt
