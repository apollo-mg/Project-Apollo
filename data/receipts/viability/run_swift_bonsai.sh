#!/usr/bin/env bash
# PREREG_SWIFT_BONSAI.md: base Bonsai 2 PQ2_0 then Swift-Bonsai-2 PQ2_0 on the 9070 (prism 9a9394a89 build_hip).
# Per model: one fresh VERIFIED server (own log loaded; /props names the file), a discarded warm-up, then stage 1 (M1,
# thinking off) and stage 2 (CAL xhigh, 3 seeds). Resumable: run_main skips done ids; CAL reps re-run only missing ids.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; QA="$HERE/../quant-abstention"
PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
BIN=/mnt/TG_2TB/Projects/Apollo/engines/prism_sep/build_hip/bin/llama-server
M=/mnt/TG_2TB/AI/Models/bonsai2; PORT=8097; URL="http://127.0.0.1:$PORT"
OUT="$HERE/swift_bonsai"; mkdir -p "$OUT"; LOG="$OUT/run.log"
VAR='{" UNKNOWN": 59322, " Unknown": 21024, " unknown": 9496}'
ALL="CAL-A1,CAL-A2,CAL-A3,CAL-A4,CAL-A5,CAL-A6,CAL-A7,CAL-A8,CAL-U1,CAL-U2,CAL-U3,CAL-U4,CAL-U5,CAL-U6,CAL-U7,CAL-U8"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
port_pid() { ss -tlnpH "sport = :$PORT" | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2; }
stop() { local p; p=$(port_pid); [ -n "$p" ] && { kill "$p"; while kill -0 "$p" 2>/dev/null; do sleep 1; done; }; return 0; }
trap stop EXIT
missing() { $PY - "$1" "$ALL" <<'PYX'
import json, os, sys
have = set()
if os.path.exists(sys.argv[1]):
    for l in open(sys.argv[1]):
        try: have.add(json.loads(l)["id"])
        except Exception: pass
print(",".join(i for i in sys.argv[2].split(",") if i not in have))
PYX
}
for spec in "BONB9|Ternary-Bonsai-2-27B-PQ2_0.gguf" "SWB9|Swift-Bonsai-2-PQ2_0.gguf"; do
  IFS='|' read -r arm file <<< "$spec"
  stop
  setsid nohup "$BIN" -m "$M/$file" -ngl 99 -c 16384 -ctk f16 -ctv f16 -np 1 -fit off -lv 4 --host 127.0.0.1 --port $PORT \
      > "$OUT/server_$arm.log" 2>&1 < /dev/null &
  for i in $(seq 1 120); do
    sleep 3
    [ -n "$(port_pid)" ] && grep -q 'model loaded' "$OUT/server_$arm.log" && curl -sf -m 5 "$URL/health" >/dev/null && break
    grep -q -E 'failed to load|error loading' "$OUT/server_$arm.log" && { log "$arm: load failed"; exit 1; }
  done
  mp=$(curl -s -m 5 "$URL/props" | $PY -c 'import json,sys; print(json.load(sys.stdin).get("model_path",""))')
  [ "$(basename "$mp")" = "$file" ] || { log "$arm: WRONG SERVER ($mp)"; exit 1; }
  log "$arm: verified -- serving $file, pid $(port_pid)"
  curl -s -m 600 "$URL/v1/chat/completions" -H 'content-type: application/json' \
    -d '{"messages":[{"role":"user","content":"Say ready."}],"max_tokens":8,"chat_template_kwargs":{"enable_thinking":false}}' >/dev/null
  meta=$($PY -c 'import json,sys; print(json.dumps({"arm": sys.argv[1], "model": sys.argv[2], "build": "prism 9a9394a89 build_hip", "host": "RX 9070 XT", "flags": "-ngl 99 -c 16384 -ctk f16 -ctv f16 -np 1 -fit off"}))' "$arm" "$file")
  log "$arm: stage 1 (M1, thinking off)"
  (cd "$QA" && $PY run_main.py --url "$URL" --arm "$arm" --meta "$meta" --expect-variants "$VAR") >> "$OUT/stage1_$arm.log" 2>&1
  log "$arm: stage 1 exit $? ($(($(wc -l < "$QA/raw/main_$arm.jsonl") - 1)) rows)"
  mkdir -p "$OUT/$arm"
  for rep in 1 2 3; do
    ids=$(missing "$OUT/$arm/armA_rep$rep.jsonl"); [ -z "$ids" ] && continue
    log "$arm: stage 2 rep$rep"
    (cd "$HERE" && $PY -u run_fixture_structfix.py --host "$URL" --tier cal --effort xhigh --sampling card \
        --seed $((1000 + rep)) --only "$ids" --arm A --jsonl "$OUT/$arm/armA_rep$rep.jsonl") >> "$OUT/stage2_${arm}_rep$rep.log" 2>&1
    log "$arm: stage 2 rep$rep exit $? ($(wc -l < "$OUT/$arm/armA_rep$rep.jsonl") rows)"
  done
done
log "== swift-bonsai done"
