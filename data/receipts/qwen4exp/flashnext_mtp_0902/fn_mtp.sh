#!/usr/bin/env bash
# Two jobs, run in sequence on an otherwise idle .194.
#
# JOB 1 (archaeology): does Tom's AUGUST head (c232282aa) produce garbage on Flash-Next at 3/4
#   devices with TODAY'S exact flags? Separates "the code got fixed by PR #324" from
#   "-ncmoe 44 was supplying the units all along". Only the commit differs from the matrix.
#
# JOB 2 (MTP scaling): Qwen3.8-27B-Q6_K, built-in MTP (qwen35.nextn_predict_layers = 1),
#   2x2 over {2,4 devices} x {MTP off, MTP on}. Dense model, fits fully on GPU, so no -ncmoe
#   confound -- pure device scaling. K=3, rep 1 discarded at analysis (slower in 6/6 legs today).
set -uo pipefail
FN=~/AI/Models/flashnext_q2/Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf
Q27=~/AI/Models/Qwen3.8-27B/Qwen3.8-27B-Q6_K.gguf
C232=~/tq-pr324/build_sm60_c232/bin/llama-server
BUUN=~/buun-llama-cpp/build_sm60_qwen4/bin/llama-server
ROOT=~/fn_mtp; mkdir -p "$ROOT"
RES="$ROOT/results.tsv"
[ -f "$RES" ] || printf "job\targ\tdevs\tstatus\tvram\tspread\tverdict\ttok_s\n" > "$RES"

go () { # $1 tag $2 bin $3 model $4 devs $5 extra-flags $6 job
  local TAG="$1" BIN="$2" MODEL="$3" DEVS="$4" EXTRA="$5" JOB="$6"
  local OUT="$ROOT/$TAG"; mkdir -p "$OUT"
  pkill -x llama-server 2>/dev/null; sleep 4
  CUDA_VISIBLE_DEVICES="$DEVS" GGML_CUDA_ALLREDUCE=internal \
    setsid nohup "$BIN" -m "$MODEL" --host 127.0.0.1 --port 8099 \
      -c 8192 -fa on --jinja -np 1 -fit off -sm tensor -ngl 99 $EXTRA \
    > "$OUT/server.log" 2>&1 < /dev/null &
  local SRV=$! R=no i
  for i in $(seq 1 300); do
    if curl -sS -m 5 http://127.0.0.1:8099/health 2>/dev/null | grep -q '"status":"ok"'; then R=yes; break; fi
    kill -0 $SRV 2>/dev/null || { R=died; break; }
    sleep 3
  done
  local VRAM="-" SPREAD="-" VERDICT="-" TOKS="-"
  if [ "$R" = yes ]; then
    VRAM=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr '\n' '/' | sed 's|/$||')
    SPREAD=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | awk 'BEGIN{mn=1e9;mx=0}{if($1>0){if($1<mn)mn=$1;if($1>mx)mx=$1}}END{if(mn<1e9)printf "%.2f",mx/mn;else print "-"}')
    curl -sS -m 900 http://127.0.0.1:8099/v1/chat/completions -H 'Content-Type: application/json' \
      -d '{"messages":[{"role":"user","content":"In one short paragraph, what is the capital of France and why is it historically significant?"}],"max_tokens":120,"temperature":0}' > "$OUT/coh.json" 2>&1
    VERDICT=$(python3 - "$OUT/coh.json" <<'PY'
import json,sys,re
try:
    _m=json.load(open(sys.argv[1]))["choices"][0]["message"]
    c=" ".join(str(_m.get(k) or "") for k in ("content","reasoning_content"))
except Exception: print("PARSE_FAIL"); raise SystemExit
if not c.strip(): print("EMPTY"); raise SystemExit
ns=re.sub(r"\s","",c)
t=max(((ns.count(ch),ch) for ch in set(ns)), default=(0,""))
if ns and t[0]/len(ns)>0.4 and not t[1].isalnum(): print("GARBAGE"); raise SystemExit
print("COHERENT" if "paris" in c.lower() else "OFFTOPIC")
PY
)
    for rep in 1 2 3; do
      curl -sS -m 900 http://127.0.0.1:8099/completion -H 'Content-Type: application/json' \
        -d '{"prompt":"Explain in detail how a four-stroke internal combustion engine works, step by step.","n_predict":128,"temperature":0,"cache_prompt":false}' > "$OUT/r$rep.json" 2>&1
    done
    TOKS=$(python3 - "$OUT" <<'PY'
import json,sys,glob
v=[]
for f in sorted(glob.glob(sys.argv[1]+"/r*.json")):
    try: v.append(json.load(open(f)).get("timings",{}).get("predicted_per_second"))
    except Exception: pass
v=[x for x in v if isinstance(x,(int,float))]
print("/".join(f"{x:.2f}" for x in v) if v else "-")
PY
)
  else
    VERDICT=$(grep -oiE "only [0-9]+ splittable units for [0-9]+ devices|out of memory|CUDA error|GGML_ASSERT|GGML_ABORT" "$OUT/server.log" | head -1)
    [ -z "$VERDICT" ] && VERDICT="died_unknown"
  fi
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$JOB" "$TAG" "$DEVS" "$R" "$VRAM" "$SPREAD" "$VERDICT" "$TOKS" >> "$RES"
  sync; pkill -x llama-server 2>/dev/null; sleep 2; tail -1 "$RES"
}

# JOB 1 — archaeology (flags identical to today's matrix, only the commit differs)
MTPSC=~/AI/Models/flashnext_mtp/mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf
MTPFLAGS="-md $MTPSC --spec-type draft-mtp --draft-max 3"
go fn_off_2 "$BUUN" "$FN" "0,1"     "-ncmoe 44"           FNMTP
go fn_on_2  "$BUUN" "$FN" "0,1"     "-ncmoe 44 $MTPFLAGS" FNMTP
go fn_off_4 "$BUUN" "$FN" "0,1,2,3" "-ncmoe 44"           FNMTP
go fn_on_4  "$BUUN" "$FN" "0,1,2,3" "-ncmoe 44 $MTPFLAGS" FNMTP
echo "######## FN-MTP DONE"
column -t "$RES"
