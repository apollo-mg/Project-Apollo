#!/bin/bash
# PREREG_DRIFT_CAUSE.md Addendum 4: the rows after midnight that pass 2 skipped, at 24 Oct. Clef paused; ExecStopPost restores it.
# Launch: systemd-run --user --unit=date-tail --collect -p ExecStopPost="/usr/bin/systemctl --user start apollo-clef.service apollo-clef-monitor.service" bash <this file>
set -u
R=/mnt/TG_2TB/Projects/Apollo; D=$R/data/receipts/abstend/llama-3.1-8b-instruct; AB=$R/data/receipts/abstentionbench; RAW=$AB/raw; AP=/mnt/TG_2TB/toolchains/abench-venv/bin/python
T=$D/date_tail.txt; BIN=$R/engines/llama_cpp_upstream_f74e2fa/build_rocm/bin/llama-server; N=Meta-Llama-3.1-8B-Instruct-Q8_0.gguf; M=/mnt/TG_2TB/models_small/gguf/$N
systemctl --user stop apollo-clef-monitor.service apollo-clef.service; sleep 3
$BIN -m $M -ngl 99 -c 32768 -np 1 -ctk f16 -ctv f16 --cache-ram 0 --host 127.0.0.1 --port 8197 > $RAW/date_tail_server.log 2>&1 < /dev/null & SP=$!
for i in $(seq 1 60); do sleep 3; curl -s -m 3 127.0.0.1:8197/health | grep -q '"ok"' && break; done
python3 -I $D/date_full.py tail-items >> $T 2>&1
$AP -s $AB/run_abench.py --items $RAW/LLAMA8R_tail_items.jsonl --out $RAW/LLAMA8R24b.jsonl --host http://127.0.0.1:8197 --neutral-penalties --expect-model $N --template-kwargs '{"date_string": "24 Oct 2026"}' >> $T 2>&1
python3 -I $D/date_full.py tail-report >> $T 2>&1
[ "$(readlink /proc/$SP/exe)" = "$(readlink -f $BIN)" ] && kill $SP && timeout 60 tail --pid=$SP -f /dev/null
echo DONE >> $T
