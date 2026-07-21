#!/usr/bin/env bash
# ARC-Challenge on the shipped GGUFs — DavidAU Fable-Fusion vs stock Qwen3.6-27B base.
# .194 edition: 4x P100 (64 GB) after the .73 2x16 GB run hit a hard capacity ceiling.
#
# WHY .194: multiple-choice scoring needs logits at every answer-token position, and this
# family's 248,320-token vocab makes that buffer several GB. It lands on the output GPU on
# top of the model. On .73's 2x16 GB split the model filled each card to ~12 GB, leaving
# ~4 GB — not enough, OOM at cuMemCreate every time regardless of -b/-ub/-c. On .194 the
# model splits 4 ways (~5.7 GB/GPU), leaving ~8 GB of headroom on the output card. Budget
# computed, not guessed — the lesson from six wasted .73 runs.
#
# BINARY: build_carveout (upstream + sm_60 carve-out), the SAME binary that ran the full
# IMAT ladder cleanly today. It is NOT buun's VBR fork, so the VMM-pool reserve that killed
# .73 is not even present here. NO_VMM=1 is set anyway as belt-and-suspenders (harmless).
#
# COMPARISON: DavidAU Q6_K (Fable-Fusion merge + Heretic abliteration of Qwen3.6-27B) vs the
# plain Qwen3.6-27B Q6_K base. Both Q6_K. This is exactly the card's claim: "exceeds the base
# Qwen 3.6 27B". The MTP block in DavidAU is irrelevant to a forward pass — nextn tensors are
# only in the speculative-decode graph, not the logits path — so no MTP confound.
#
# -np 8: multiple_choice evaluates a task's N answer continuations as N parallel sequences and
# ABORTS (but exits rc=0) when n_parallel < N. ARC-Challenge choice-count distribution measured
# from the bin: {3:4, 4:1165, 5:3} -> max 5. First run died at task 836, the first 5-choice item.
# -np 8 covers the measured max of 5 with margin; -np divides the shared KV context, it does not
# multiply memory, so this is free on 64 GB.
#
# SCORING CAVEAT (unchanged from .73 spec): llama.cpp --multiple-choice takes raw-logprob
# argmax = lm-eval `acc`, NOT `acc_norm`. Published ARC figures are frequently acc_norm and
# run higher. => absolute number NOT comparable to the card's 0.711. The MATCHED delta is
# the load-bearing quantity.
#
# PREDICTIONS (carried from the .73 spec, logged before any data):
#   P-ARC1 (0.75): DavidAU scores BELOW the claimed 0.711 here (acc vs acc_norm + stack).
#   P-ARC2 (0.60): DavidAU still EXCEEDS the base on this matched test. Falsified if base >=
#                  DavidAU, which contradicts the card directly.
#   P-ARC3 (0.65): measured gap SMALLER than the claimed 6.4 pts (0.711 - 0.647).
set -u

# --- single-instance guard: a second launch (e.g. fat-fingered twice) must refuse, not
# --- collide. Two instances share ~/arc/*.out and kill each other via free_gpus() -> corrupt.
exec 9>/home/mark/arc/.arc.lock
if ! flock -n 9; then
  echo "[$(date +%F_%T)] ANOTHER run_arc_194 IS ALREADY RUNNING — refusing to start a second." >&2
  exit 3
fi

BIN=/home/mark/llama_stock/build_carveout/bin/llama-perplexity
DATA=/home/mark/arc/arc_challenge_test.mc.bin
STOCK="/home/mark/AI/Models/Qwen 3.6/27B/Qwen3.6-27B-Q6_K.gguf"
DAVIDAU=/home/mark/AI/Models/DavidAU-Fable-Fusion-711-MTP-Q6_K.gguf
OUT=~/arc
LOG=$OUT/arc.log
mkdir -p "$OUT"
log(){ echo "[$(date +%F_%T)] $*" | tee -a "$LOG"; }

# free all 4 GPUs (should already be idle post-IMAT, but be sure)
free_gpus(){
  pgrep -f "[l]lama-perplexity|[l]lama-server" | while read -r p; do kill "$p" 2>/dev/null; done
  sleep 6
  pgrep -f "[l]lama-perplexity|[l]lama-server" | while read -r p; do kill -9 "$p" 2>/dev/null; done
  sleep 3
  for i in $(seq 1 40); do
    u=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | paste -sd+ | bc)
    [ "${u:-9999}" -lt 500 ] && return 0
    sleep 5
  done
  log "WARN: GPUs still hold ${u}MiB"
}

run(){ # $1 tag  $2 model
  local tag="$1" model="$2"
  log "--- $tag ---"
  [ -f "$model" ] || { log "$tag SKIP: missing $model"; echo "$tag NO_MODEL 0" >> "$OUT/summary.txt"; return; }
  rm -f "$OUT/$tag.out" "$OUT/$tag.err"
  free_gpus
  log "$tag clocks: $(nvidia-smi --query-gpu=index,clocks.sm,clocks.mem,power.limit --format=csv,noheader | paste -sd' | ')"

  local t0=$(date +%s)
  GGML_CUDA_NO_VMM=1 timeout 10800 "$BIN" -m "$model" --multiple-choice -bf "$DATA" \
      -c 2048 -np 8 -b 512 -ub 512 -ngl 999 -ts 1,1,1,1 -fa off --no-warmup < /dev/null \
      > "$OUT/$tag.out" 2> "$OUT/$tag.err"
  local rc=$? dur=$(( $(date +%s) - t0 ))

  for i in $(seq 1 40); do pgrep -f "[l]lama-perplexity" >/dev/null || break; sleep 5; done

  # multiple_choice prints per-task running accuracy to STDOUT as "<taskidx>\t<acc%>".
  # After a COMPLETE run the LAST such line is "<n_task>\t<final_acc>" -- that IS the score.
  # rc=0 does NOT mean success: the earlier runs died at task 836/1172 (5-choice items,
  # -np too low) yet still exited 0. So we do not trust rc -- we verify done_task == n_task.
  local final n_task done_task lastline
  n_task=$(grep -oE "there are [0-9]+ tasks" "$OUT/$tag.err" | grep -oE "[0-9]+" | tail -1)
  lastline=$(awk 'NF>=2 && $1 ~ /^[0-9]+$/ && $2 ~ /^[0-9.]+$/ {a=$1; b=$2} END{if(a!="")print a" "b}' "$OUT/$tag.out")
  done_task=$(printf '%s' "$lastline" | awk '{print $1}')
  final=$(printf '%s' "$lastline" | awk '{print $2}')
  local crashed=0 np_short=0
  grep -qiE "CUDA error|out of memory|GGML_ASSERT|core dumped" "$OUT/$tag.err" && crashed=1
  grep -qiE "requires a higher -np" "$OUT/$tag.err" && np_short=1

  local status="OK"
  [ -z "$final" ] && status="NO_SCORE"
  [ -n "$done_task" ] && [ -n "$n_task" ] && [ "$done_task" != "$n_task" ] && status="INCOMPLETE_${done_task}of${n_task}"
  [ "$np_short" = 1 ] && status="NP_TOO_LOW"
  [ "$crashed" = 1 ] && [ -z "$final" ] && status="CRASHED"
  log "$tag $status score=${final:-NONE} tasks=${done_task:-?}/${n_task:-?} rc=$rc ${dur}s"
  echo "$tag ${final:-NONE} ${n_task:-0}" >> "$OUT/summary.txt"
}

log "=========== ARC-Challenge on shipped GGUFs — .194 4xP100, matched Q6_K ==========="
log "card claims: DavidAU 0.711 (mxfp8) / 0.701 (mxfp4) vs base 0.647"
log "scoring: llama.cpp --multiple-choice = raw-logprob argmax (acc, NOT acc_norm)"
log "data: 1172 ARC-Challenge test items, 0 skipped; choice-counts {3:4,4:1165,5:3}, -np 8"
log "binary: build_carveout (no VBR/VMM). split -ts 1,1,1,1 across 4x P100."
: > "$OUT/summary.txt"

run base    "$STOCK"
run davidau "$DAVIDAU"

log "=== summary ==="
cat "$OUT/summary.txt" | tee -a "$LOG"

python3 - <<'PY' 2>&1 | tee -a "$LOG"
import os
p = os.path.expanduser("~/arc/summary.txt")
v = {}
for line in open(p):
    f = line.split()
    if len(f) >= 2 and f[1] not in ("NONE", "NO_MODEL"):
        try: v[f[0]] = float(f[1])
        except ValueError: pass
b, d = v.get("base"), v.get("davidau")
print("\n--- results (acc, unnormalized; llama.cpp prints percent) ---")
for k in ("base", "davidau"):
    print(f"  {k:8s} {v.get(k, '-')}")
if b is not None and d is not None:
    bf = b/100 if b > 1 else b
    df = d/100 if d > 1 else d
    print(f"\n--- P-ARC1 (0.75): DavidAU below claimed 0.711 ---")
    print(f"  {df:.4f} vs 0.711 -> {'CONFIRMED' if df < 0.711 else 'FALSIFIED'}")
    print(f"\n--- P-ARC2 (0.60): DavidAU exceeds base, matched Q6_K ---")
    print(f"  davidau {df:.4f} vs base {bf:.4f}  delta {df-bf:+.4f} -> "
          f"{'CONFIRMED' if df > bf else 'FALSIFIED — contradicts the card'}")
    print(f"\n--- P-ARC3 (0.65): gap smaller than claimed 6.4 pts ---")
    print(f"  measured {abs(df-bf)*100:.1f} pts vs claimed 6.4 -> "
          f"{'CONFIRMED' if abs(df-bf) < 0.064 else 'FALSIFIED'}")
    print("\n  reminder: absolute values are acc, not acc_norm — do not compare directly")
    print("  to leaderboard figures. The matched delta is the load-bearing number.")
else:
    print("\n  incomplete — at least one arm produced no score")
PY
touch "$OUT/arc.done"
log "=== ARC complete ==="
