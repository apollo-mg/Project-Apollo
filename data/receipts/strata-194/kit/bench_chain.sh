#!/usr/bin/env bash
# Strata community-report runs on .194 (addendum): start Strata, record memory, run strata_bench.py, copy the engine's timing lines.
cd "$(dirname "$0")"; OUT=runs_community; mkdir -p $OUT
CFG=$HOME/strata/strata-iq3_xxs.json; LOGF=$HOME/strata/strata-iq3_xxs.log
L0=$(wc -l < $LOGF)
(cd ~/strata && exec ~/strata/.venv/bin/python serve/server.py --engine strata --config "$CFG" --port 8080) > $OUT/server.log 2>&1 & SP=$!
trap 'kill $SP 2>/dev/null; for i in $(seq 1 90); do kill -0 $SP 2>/dev/null || break; sleep 1; done' EXIT
for i in $(seq 1 1200); do curl -s -m 2 http://127.0.0.1:8080/health | grep -q '"loaded": *true' && break; kill -0 $SP || exit 1; sleep 1; done
{ date '+%F %T'; free -g; nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv; } > $OUT/memory_after_load.txt
nvidia-smi --query-gpu=timestamp,index,clocks.sm,memory.used,power.draw --format=csv,noheader -lms 1000 > $OUT/gpu_during.csv & CP=$!
python3 strata_bench.py --url http://127.0.0.1:8080 --repo ~/strata --lengths 4096,32768 --runs 3 --out $OUT/bench.jsonl > $OUT/bench.out 2>&1
kill $CP; free -g > $OUT/memory_after_runs.txt
tail -n +$((L0 + 1)) $LOGF > $OUT/engine_log_this_run.txt
echo BENCH_DONE >> $OUT/bench.out
