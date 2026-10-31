#!/bin/bash
# PREREG_DRIFT_CAUSE.md Addendum 2: same judge server as the instrument. Clef paused; ExecStopPost restores it.
# Launch: systemd-run --user --unit=date-judge --collect -p ExecStopPost="/usr/bin/systemctl --user start apollo-clef.service apollo-clef-monitor.service" bash <this file>
set -u
R=/mnt/TG_2TB/Projects/Apollo; D=$R/data/receipts/abstend/llama-3.1-8b-instruct; AB=$R/data/receipts/abstentionbench; RAW=$AB/raw; AP=/mnt/TG_2TB/toolchains/abench-venv/bin/python
T=$D/date_judge.txt; BIN=$R/engines/llama_cpp_upstream_f74e2fa/build_rocm/bin/llama-server; N=Meta-Llama-3.1-8B-Instruct-Q8_0.gguf; M=/mnt/TG_2TB/models_small/gguf/$N
K=/mnt/TG_2TB/toolchains/AbstentionBench
judge () { $AP -s $AB/judge_abench.py --checkout $K --items $K/sub1000_items.jsonl --host http://127.0.0.1:8196 --variant norefs --expect-model $N --responses "$1" --out "$2" --date "$3" >> $T 2>&1; }
systemctl --user stop apollo-clef-monitor.service apollo-clef.service; sleep 3
$BIN -m $M -ngl 99 -c 32768 -np 1 -ctk f16 -ctv f16 --cache-ram 0 --host 127.0.0.1 --port 8196 > $RAW/date_judge_server.log 2>&1 < /dev/null & SP=$!
for i in $(seq 1 60); do sleep 3; curl -s -m 3 127.0.0.1:8196/health | grep -q '"ok"' && break; done
python3 -I $D/date_judge.py flips
judge $RAW/flip2.jsonl $RAW/flip2.d24.jsonl "24 Oct 2026"
judge $RAW/flip2.jsonl $RAW/flip2.d28.jsonl "28 Oct 2026"
python3 -I $D/date_judge.py answers >> $T 2>&1
judge $RAW/L31AB.jsonl $RAW/L31AB.judge_d28.jsonl "28 Oct 2026"
judge $RAW/L31AB.jsonl $RAW/L31AB.judge_dpin.jsonl "26 Jul 2024"
python3 -I $D/date_judge.py report >> $T 2>&1
[ "$(readlink /proc/$SP/exe)" = "$(readlink -f $BIN)" ] && kill $SP && timeout 60 tail --pid=$SP -f /dev/null
echo DONE >> $T
