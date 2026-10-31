#!/bin/bash
# PREREG_DRIFT_CAUSE.md Addendum 3: LLAMA8 again on today's kernel and firmware, with the date pinned. Clef paused; ExecStopPost restores it.
# Launch: systemd-run --user --unit=date-full --collect -p ExecStopPost="/usr/bin/systemctl --user start apollo-clef.service apollo-clef-monitor.service" bash <this file>
set -u
R=/mnt/TG_2TB/Projects/Apollo; D=$R/data/receipts/abstend/llama-3.1-8b-instruct; AB=$R/data/receipts/abstentionbench; RAW=$AB/raw; AP=/mnt/TG_2TB/toolchains/abench-venv/bin/python
T=$D/date_full.txt; BIN=$R/engines/llama_cpp_upstream_f74e2fa/build_rocm/bin/llama-server; N=Meta-Llama-3.1-8B-Instruct-Q8_0.gguf; M=/mnt/TG_2TB/models_small/gguf/$N
K=/mnt/TG_2TB/toolchains/AbstentionBench; H=http://127.0.0.1:8197
subject () { $AP -s $AB/run_abench.py --items "$1" --out "$2" --host $H --neutral-penalties --expect-model $N --template-kwargs "{\"date_string\": \"$3\"}" >> $T 2>&1; echo "$(date '+%T') subject $3 rc=$? rows=$(wc -l < "$2")" >> $T; }
systemctl --user stop apollo-clef-monitor.service apollo-clef.service; sleep 3
$BIN -m $M -ngl 99 -c 32768 -np 1 -ctk f16 -ctv f16 --cache-ram 0 --host 127.0.0.1 --port 8197 > $RAW/date_full_server.log 2>&1 < /dev/null & SP=$!
for i in $(seq 1 60); do sleep 3; curl -s -m 3 127.0.0.1:8197/health | grep -q '"ok"' && break; done
subject $K/sub1000_items.jsonl $RAW/LLAMA8R23.jsonl "23 Oct 2026"
python3 -I $D/date_full.py resid >> $T 2>&1
subject $RAW/LLAMA8R_resid_items.jsonl $RAW/LLAMA8R24.jsonl "24 Oct 2026"
python3 -I $D/date_full.py merge >> $T 2>&1
$AP -s $AB/judge_abench.py --checkout $K --items $K/sub1000_items.jsonl --responses $RAW/LLAMA8R.jsonl --out $RAW/LLAMA8R.judge_norefs.jsonl --host $H --variant norefs --expect-model $N --date "24 Oct 2026" >> $T 2>&1
echo "$(date '+%T') judge rc=$? rows=$(wc -l < $RAW/LLAMA8R.judge_norefs.jsonl)" >> $T
python3 -I $D/date_full.py report >> $T 2>&1
[ "$(readlink /proc/$SP/exe)" = "$(readlink -f $BIN)" ] && kill $SP && timeout 60 tail --pid=$SP -f /dev/null
$R/venv_cachyos/bin/python3 $R/data/scorecard/abstend.py compare-abench LLAMA8 LLAMA8R >> $T 2>&1
echo DONE >> $T
