#!/bin/bash
# PREREG_INSTRUMENT_V3.md: re-judge the anchors at the pin, then one v3 Llama subject run, on one server with the judge's
# file, binary and flags. Clef paused; ExecStopPost restores it.
# Launch: systemd-run --user --unit=rejudge-v3 --collect -p ExecStopPost="/usr/bin/systemctl --user start apollo-clef.service apollo-clef-monitor.service" bash <this file>
set -u
R=/mnt/TG_2TB/Projects/Apollo; AB=$R/data/receipts/abstentionbench; RAW=$AB/raw; AP=/mnt/TG_2TB/toolchains/abench-venv/bin/python
K=/mnt/TG_2TB/toolchains/AbstentionBench; I=$K/sub1000_items.jsonl; T=$AB/raw/rejudge_v3.log; H=http://127.0.0.1:8196; PIN="26 Jul 2024"
BIN=$R/engines/llama_cpp_upstream_f74e2fa/build_rocm/bin/llama-server; N=Meta-Llama-3.1-8B-Instruct-Q8_0.gguf; M=/mnt/TG_2TB/models_small/gguf/$N
log () { echo "$(date '+%F %T') $*" >> $T; }
[ "$(sha256sum $M | cut -d' ' -f1)" = 9da71c45c90a821809821244d4971e5e5dfad7eb091f0b8ff0546392393b6283 ] || { log "ABORT: judge sha256"; exit 1; }
systemctl --user stop apollo-clef-monitor.service apollo-clef.service; sleep 3
$BIN -m $M -ngl 99 -c 32768 -np 1 -ctk f16 -ctv f16 --cache-ram 0 --host 127.0.0.1 --port 8196 > $RAW/rejudge_v3_server.log 2>&1 < /dev/null & SP=$!
trap '[ "$(readlink /proc/$SP/exe)" = "$(readlink -f $BIN)" ] && kill $SP && timeout 60 tail --pid=$SP -f /dev/null' EXIT
for i in $(seq 1 60); do sleep 3; curl -s -m 3 $H/health | grep -q '"ok"' && break; done
log "server up, $(uname -r)"
for A in LLAMA8 L31AB Q27OFF Q27ON S25AB S26AB; do
  $AP -s $AB/judge_abench.py --checkout $K --items $I --responses <($AP -I -c "
import csv, json, sys
S = {(r['dataset'], r['index']) for r in csv.DictReader(open('$AB/subset_1000.csv'))}
for l in open('$RAW/$A.jsonl'):
    r = json.loads(l)
    if (r['dataset'], str(r['index'])) in S: sys.stdout.write(l)") --out $RAW/$A.judge_v3.jsonl --host $H --variant norefs --expect-model $N --date "$PIN" --prompt-hash >> $T 2>&1
  log "$A judged rc=$? rows=$(wc -l < $RAW/$A.judge_v3.jsonl)"
done
$AP -s $AB/run_abench.py --items $I --out $RAW/L31V3.jsonl --host $H --neutral-penalties --top-k 40 --min-p 0.05 --template-kwargs "{\"date_string\": \"$PIN\"}" --prompt-hash --expect-model $N >> $T 2>&1
log "L31V3 subject rc=$? rows=$(wc -l < $RAW/L31V3.jsonl)"
$AP -s $AB/judge_abench.py --checkout $K --items $I --responses $RAW/L31V3.jsonl --out $RAW/L31V3.judge_v3.jsonl --host $H --variant norefs --expect-model $N --date "$PIN" --prompt-hash >> $T 2>&1
log "L31V3 judged rc=$? rows=$(wc -l < $RAW/L31V3.judge_v3.jsonl)"
$R/venv_cachyos/bin/python3 $AB/analyze_v3.py >> $T 2>&1; log "analysis rc=$?"
log DONE
