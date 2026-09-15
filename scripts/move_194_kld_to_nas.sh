#!/bin/bash
# Move .194's regenerable KLD reference artifacts to the NAS. Written 2026-09-14.
#
# Standing rule for these files is MOVE, NEVER DELETE -- they are expensive to regenerate (the 73.7 GB
# q8_base_logits.bin is a full logits dump) and several published receipts were computed against them.
#
# Order is copy -> verify at the DESTINATION by sha256 -> only then unlink the source. Never the other
# way round, and never "rsync --remove-source-files", which unlinks on transfer success rather than on
# content match. Today's dedup pass found that name+size agreement is not content agreement.
#
# Route: pulls from .194 to the control plane's /mnt/HDD mount, so .194 needs no cifs credentials.
# That is two network hops (.194 -> CP -> NAS). Mounting the share on .194 directly would halve it,
# and is worth doing if this proves slow -- but it needs root and a credentials file there.
#
# /mnt/HDD is an x-systemd.automount with idle-timeout=600: it reads as ABSENT until touched, which is
# what made memory record it as unmounted and read-only for three weeks. Touch it first, always.
#
# RUN THIS ONLY WHEN .194 IS IDLE. It streams ~145 GiB through page cache on a 60 GB box and will
# perturb any measurement in flight -- which is why it is sequenced after the Stage 5 spill ladder.
#
# Usage:  bash scripts/move_194_kld_to_nas.sh            # dry run: show plan, check space
#         bash scripts/move_194_kld_to_nas.sh --go       # copy + verify (still does NOT unlink)
#         bash scripts/move_194_kld_to_nas.sh --unlink   # unlink sources VERIFIED present at dest

set -u
MODE="${1:-dry}"
NODE=10.0.0.194
DEST=/mnt/HDD/apollo-kld-194
FILES="
/home/mark/puzzle_lab/w1/q8_base_logits.bin
/home/mark/quant_ladder/qwen27b_bf16_truth_f32kv_faoff_2k32.kld
/home/mark/puzzle_lab/w1/qwen27b_q8truth_f32kv_faoff_2k32.kld
/home/mark/moe_panel/moe36b_f32kv_faoff_ctx2048_32ch_PATCHED.kld
/home/mark/puzzle_lab/puzzle75b_q8truth_f32kv_faoff_ctx2048_32ch.kld
/home/mark/hep/fa_kld/puzzle_q2_faoff.kld
/home/mark/kldsweep_q6k/base_f16.dat
/home/mark/kldsweep/base_f16.dat
"

ls /mnt/HDD >/dev/null 2>&1 || { echo "ABORT: cannot reach /mnt/HDD"; exit 1; }
mountpoint -q /mnt/HDD || { echo "ABORT: /mnt/HDD did not mount on touch"; exit 1; }
echo "NAS free: $(df -h /mnt/HDD | tail -1 | awk '{print $4}')"

# Two pairs share a byte size (2x 8,133,238,740 base_f16.dat, 3x 16,258,531,092 .kld). Same size is NOT
# same content -- that assumption produced a false corruption report earlier today. Hash decides.
echo "--- plan ---"
TOTAL=0
for f in $FILES; do
  sz=$(ssh -o BatchMode=yes "$NODE" "stat -c %s '$f' 2>/dev/null" || echo 0)
  [ "${sz:-0}" -eq 0 ] && { echo "  MISSING on $NODE: $f"; continue; }
  TOTAL=$((TOTAL+sz))
  printf "  %14d  %s\n" "$sz" "$f"
done
echo "  total: $((TOTAL/1073741824)) GiB"
[ "$MODE" = "dry" ] && { echo "(dry run -- pass --go to copy)"; exit 0; }

mkdir -p "$DEST"

if [ "$MODE" = "--go" ]; then
  for f in $FILES; do
    b=$(basename "$f"); d=$(dirname "$f" | sed 's#/home/mark/##; s#/#_#g')
    out="$DEST/${d}__${b}"
    echo "=== $f -> $out"
    rsync -h --partial --inplace --progress -e ssh "mark@$NODE:$f" "$out" || { echo "  RSYNC FAILED"; continue; }
    src=$(ssh -o BatchMode=yes "$NODE" "sha256sum '$f' | cut -d' ' -f1")
    dst=$(sha256sum "$out" | cut -d' ' -f1)
    if [ "$src" = "$dst" ]; then echo "  VERIFIED $src"; echo "$src  $f  $out" >> "$DEST/MANIFEST.txt"
    else echo "  *** HASH MISMATCH: src $src dst $dst -- destination copy is NOT good"; fi
  done
  echo "--- copied. Sources untouched. Run with --unlink once you are satisfied. ---"
  exit 0
fi

if [ "$MODE" = "--unlink" ]; then
  [ -f "$DEST/MANIFEST.txt" ] || { echo "ABORT: no MANIFEST.txt -- nothing was verified"; exit 1; }
  while read -r h src out; do
    [ -z "${out:-}" ] && continue
    [ -f "$out" ] || { echo "  SKIP (dest gone): $out"; continue; }
    now=$(sha256sum "$out" | cut -d' ' -f1)
    [ "$now" = "$h" ] || { echo "  SKIP (dest hash drifted): $out"; continue; }
    echo "  dest verified $h -- unlinking source $src"
    ssh -o BatchMode=yes "$NODE" "rm -f -- '$src'"
  done < "$DEST/MANIFEST.txt"
  ssh -o BatchMode=yes "$NODE" 'df -h / | tail -1'
fi
