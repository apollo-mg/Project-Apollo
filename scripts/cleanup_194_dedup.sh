#!/bin/bash
# Remove content-verified duplicates from .194. Written 2026-09-14.
#
# Every path below was sha256-verified byte-identical to a named control-plane survivor
# (data/receipts/RESULT_CLEANUP_DEDUP_2026-09-14.md). Both EXL3 sets are deliberately EXCLUDED
# and stay on .194 at Mark's instruction -- Flash-Next 3.05bpw (79.1 GB) and 27B 3.00bpw (12.9 GB).
#
# Safety properties, in order of how they have actually failed here before:
#   * gates on VRAM, NOT `pgrep -f` -- CLAUDE.md forbids -f patterns you may be inside of, and
#     `pgrep -x llama-perplexity` is inert anyway (16 chars > the 15-char comm).
#   * re-stats each file and refuses to unlink if the byte size moved since verification.
#   * byte-exact sizes, never rounded -- a rounded-GB match is what produced a false mismatch
#     report earlier the same day (two builds 409,824 bytes apart both render as "3.59 GB").
#   * dry-run by default. Pass --go to actually delete.
#
# Usage:  bash scripts/cleanup_194_dedup.sh          # show what would go
#         bash scripts/cleanup_194_dedup.sh --go     # delete
# Run it ON .194, or:  ssh 10.0.0.194 'bash -s -- --go' < scripts/cleanup_194_dedup.sh

set -u
GO=0
[ "${1:-}" = "--go" ] && GO=1

MANIFEST="22431000576	/home/mark/AI/Models/Carnice-V3-Q6_K.gguf
6433687744	/home/mark/AI/Models/Llama-3.2-3B-Instruct-BF16.gguf
13943350752	/home/mark/AI/Models/apex/Qwen3.8-27B-APEX-I-Mini.gguf
11240605152	/home/mark/AI/Models/apex/Qwen3.8-27B-APEX-I-Nano.gguf
23582382656	/home/mark/AI/Models/Qwen3.8-27B/Qwen3.8-27B-Cold-Fusion-GAIN-V1.1-NM-DAU-NEO-MAX-NEO-Q6_K.gguf
3859883392	/home/mark/AI/Models/Qwen3.8-27B/Qwen3.8-27B-DFlash2-BF16.gguf
29047086048	/home/mark/AI/Models/ud3xl/Qwen3.8-27B-Q8_0.gguf
10319907904	/home/mark/AI/Models/Qwen3.8-27B/Qwen3.8-27B-UD-IQ2_M.gguf
11913559104	/home/mark/AI/Models/qwen27b/Qwen3.8-27B-UD-IQ3_XXS.gguf
14252845984	/home/mark/AI/Models/Qwen3.8-27B/Qwen3.8-27B-UD-IQ4_XS.gguf
16464440224	/home/mark/AI/Models/Qwen3.8-27B/Qwen3.8-27B-UD-Q4_K_M.gguf
1369590656	/home/mark/AI/Models/Qwen3.8-27B/mtp-Qwen3.8-27B-Q4_0.gguf"

USED=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null \
       | awk '{s+=$1} END {print s+0}')
if [ "${USED:-0}" -gt 64 ]; then
  echo "ABORT: ${USED} MiB VRAM in use -- a run is live. Nothing touched."
  exit 1
fi
echo "VRAM gate ok (${USED} MiB in use)"
[ "$GO" -eq 1 ] || echo "DRY RUN -- pass --go to delete"
df -h / | tail -1
echo "---"

FREED=0; N=0; SKIP=0
while IFS=$'\t' read -r want path; do
  [ -z "${path:-}" ] && continue
  if [ ! -f "$path" ]; then echo "  skip (already gone): $path"; SKIP=$((SKIP+1)); continue; fi
  act=$(stat -c %s "$path")
  if [ "$act" != "$want" ]; then
    echo "  SKIP (size changed: $act != $want): $path"; SKIP=$((SKIP+1)); continue
  fi
  if [ "$GO" -eq 1 ]; then
    if rm -f -- "$path"; then
      FREED=$((FREED+act)); N=$((N+1)); printf "  removed %14d  %s\n" "$act" "$path"
    else
      echo "  FAILED: $path"; SKIP=$((SKIP+1))
    fi
  else
    FREED=$((FREED+act)); N=$((N+1)); printf "  would remove %14d  %s\n" "$act" "$path"
  fi
done <<< "$MANIFEST"

echo "---"
echo "$N files, $((FREED/1073741824)) GiB, $SKIP skipped"
df -h / | tail -1
