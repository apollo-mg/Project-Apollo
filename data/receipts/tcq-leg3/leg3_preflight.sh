#!/usr/bin/env bash
# Leg-3 determinism pre-flight. Run BEFORE any margins are collected.
# Usage: leg3_preflight.sh <label> <server_bin> <ktype> [extra_env]
# Serves Qwopus3.6-27B-Coder-heretic-Q6_K with -np 1 (confines everything to slot 0, which
# DETERMINISM_ROOT_CAUSE.md showed matches true f16 byte-for-byte) and --no-cache-prompt
# (prefix-cache reuse is an upstream nondeterminism channel, on by default).
# Runs the same 5 routing cases 3x and byte-diffs the completions.
set -u
LABEL=$1; BIN=$2; KTYPE=$3
MODEL=/home/mark/AI/Models/Qwopus-Coder/Qwopus3.6-27B-Coder-heretic-Q6_K.gguf
D=/home/mark/leg3
OUT="$D/preflight_$LABEL"
PORT=8099
mkdir -p "$OUT"

head -5 "$D/cases/rd_2048_c2.jsonl" > "$OUT/cases5.jsonl"

pkill -x llama-server 2>/dev/null; sleep 4
echo "=== $LABEL: serving with -ctk/-ctv $KTYPE, -np 1, --no-cache-prompt ==="
TURBO_AUTO_ASYMMETRIC=0 "$BIN" -m "$MODEL" -c 4096 -ngl 99 -sm layer -np 1 \
  --no-cache-prompt -ctk "$KTYPE" -ctv "$KTYPE" \
  --host 127.0.0.1 --port $PORT > "$OUT/server.log" 2>&1 &

for i in $(seq 1 120); do curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && break; sleep 5; done
curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 || {
  echo "FATAL: $LABEL server never ready"; tail -20 "$OUT/server.log"; exit 1; }

# Guard: a silent K-type substitution would make this a different measurement entirely.
if grep -qai "auto.asymmetric\|SUBST" "$OUT/server.log"; then
  echo "!! WARNING: asymmetric/substitution notice in boot log — inspect before trusting"
  grep -ai "auto.asymmetric\|SUBST" "$OUT/server.log" | head -3
fi

for rep in 1 2 3; do
  rm -f "$OUT/rep${rep}.jsonl"
  python3 "$D/probe_router.py" --base-url "http://127.0.0.1:$PORT/v1" --model local \
    --data "$OUT/cases5.jsonl" --out "$OUT/rep${rep}.jsonl" \
    --max-tokens 64 --label "${LABEL}_rep${rep}" 2>&1 | tail -2
done
pkill -x llama-server 2>/dev/null; sleep 3

python3 - "$OUT" "$LABEL" <<'PY'
import json,sys,hashlib
out,label=sys.argv[1],sys.argv[2]
reps=[{json.loads(l)["id"]:json.loads(l) for l in open(f"{out}/rep{r}.jsonl")} for r in (1,2,3)]
ids=sorted(reps[0])
print(f"\n=== {label} DETERMINISM PRE-FLIGHT ===")
print(f"{'case':<28}{'rep1':>10}{'rep2':>10}{'rep3':>10}  identical")
bad=0
for i in ids:
    hs=[hashlib.sha256((r[i].get("raw") or "").encode()).hexdigest()[:8] for r in reps]
    ok=len(set(hs))==1
    bad += (not ok)
    print(f"{str(i)[:27]:<28}{hs[0]:>10}{hs[1]:>10}{hs[2]:>10}  {'yes' if ok else 'NO <<<'}")
print(f"\n{label}: {len(ids)-bad}/{len(ids)} byte-identical across 3 repeats -> "
      f"{'PASS' if bad==0 else 'FAIL — margins from this build are not trustworthy'}")
PY
