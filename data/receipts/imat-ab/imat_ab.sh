#!/usr/bin/env bash
# Does the Q3 PPL inversion survive WITHOUT imatrix?
#
# Quant_Ladder_Results.md: Q3_K_M posts PPL 6.4370 — better than Q8 (6.5334) and better than the
# BF16 it came from (6.5159) — while being the most distributionally damaged tier in the ladder.
# Every tier carries `quantize.imatrix.dataset = unsloth_calibration_Qwen3.6-27B.txt`, and the
# ladder was scored on wikitext-2. Hypothesis: lower-bit quants lean hardest on imatrix guidance,
# so if the calibration corpus resembles wikitext, Q3 is the tier most fit to the eval set.
#
# 2x2 design makes it falsifiable:
#            wikitext-2 (plausible calibration overlap)   own-notes (guaranteed unseen)
#   IMAT                 A                                        B
#   NOIMAT               C                                        D
#
# P-IMAT1 (0.65): (C - A) > (D - B). Removing imatrix hurts MORE on wikitext than on unseen text.
#                 That is the overlap signature.
# P-IMAT2 (0.55): NOIMAT on wikitext lands ABOVE the BF16 base 6.5159 — i.e. it behaves like a
#                 damaged model should, and the inversion is an imatrix artifact.
# Falsified if the inversion survives without imatrix (C < 6.5159) -> something deeper than
# calibration overlap, and the PPL-vs-KLD story stands on its own.
set -u
Q=~/AI/Models/'Qwen 3.6'/27B
PPL=~/llama_stock/build_carveout/bin/llama-perplexity
WIKI=~/wikitext-2-raw/wiki.test.raw
NOTES=~/quant_ladder/own_notes_corpus.txt
LOG=~/quant_ladder/imat_ab.log
log(){ echo "[$(date +%F_%T)] $*" | tee -a "$LOG"; }

run(){ # $1 tag  $2 model  $3 corpus
  log "--- $1 ---"
  timeout 5400 "$PPL" -m "$2" -f "$3" -c 2048 --chunks 32 -ngl 99 -ts 1,1,1,1 \
      -fa off -ctk f32 -ctv f32 -ub 128 --no-warmup < /dev/null \
      > ~/quant_ladder/imat_$1.out 2> ~/quant_ladder/imat_$1.err
  local p
  p=$(grep -oE 'Final estimate: PPL = [0-9.]+' ~/quant_ladder/imat_$1.err | grep -oE '[0-9.]+$')
  log "$1 PPL = ${p:-FAILED}"
  echo "$1 ${p:-FAILED}" >> ~/quant_ladder/imat_summary.txt
}

log "=== IMAT vs NOIMAT, 2x2 ==="
log "ladder reference: BF16 6.5159 | Q8_0 6.5334 | Q3_K_M(imat) 6.4370"
: > ~/quant_ladder/imat_summary.txt

run A_imat_wiki    "$Q/Qwen3.6-27B-Q3_K_M-STOCK-IMAT.gguf"   "$WIKI"
run C_noimat_wiki  "$Q/Qwen3.6-27B-Q3_K_M-STOCK-NOIMAT.gguf" "$WIKI"
run B_imat_notes   "$Q/Qwen3.6-27B-Q3_K_M-STOCK-IMAT.gguf"   "$NOTES"
run D_noimat_notes "$Q/Qwen3.6-27B-Q3_K_M-STOCK-NOIMAT.gguf" "$NOTES"

log "=== summary ==="
cat ~/quant_ladder/imat_summary.txt | tee -a "$LOG"
python3 - <<'PY' 2>&1 | tee -a "$LOG"
import re
v={}
for line in open("/home/mark/quant_ladder/imat_summary.txt"):
    k,s=line.split()
    if s!="FAILED": v[k]=float(s)
need=["A_imat_wiki","C_noimat_wiki","B_imat_notes","D_noimat_notes"]
if all(k in v for k in need):
    dw=v["C_noimat_wiki"]-v["A_imat_wiki"]
    dn=v["D_noimat_notes"]-v["B_imat_notes"]
    print(f"imatrix benefit on wikitext  (C-A) = {dw:+.4f}")
    print(f"imatrix benefit on own notes (D-B) = {dn:+.4f}")
    print(f"P-IMAT1 ({'CONFIRMED' if dw>dn else 'FALSIFIED'}): overlap signature "
          f"{'present' if dw>dn else 'absent'}")
    print(f"P-IMAT2 ({'CONFIRMED' if v['C_noimat_wiki']>6.5159 else 'FALSIFIED'}): "
          f"NOIMAT wikitext {v['C_noimat_wiki']:.4f} vs BF16 base 6.5159")
else:
    print("incomplete run, no verdict")
PY
touch ~/quant_ladder/imat.done
