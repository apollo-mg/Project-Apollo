# MTP n-max: dense and MoE have different optima **for different reasons** — and dense wins bigger

Date 2026-08-03. `.73`, 2× Tesla P100-PCIE-16GB (sm_60), 150 W / 1063 MHz.
Build `TheTom/llama-cpp-turboquant` @ `d0e2a8b64`. `-c 8192 -fa on -np 1 -ngl 99 -sm tensor`,
n_predict 128, temp 0, K=3.

## Results

**Dense — `Qwen3.6-27B-Q6_K-MTP.gguf`** (arch `qwen35`, 65 blocks, `nextn_predict_layers=1`,
21.31 GiB, **zero `_exps` tensors**):

| n-max | tok/s | speedup | accept | mean len | step Δ |
|---|---|---|---|---|---|
| none | 13.29 / 13.31 / 13.30 | 1.00× | — | — | — |
| 1 | 22.41 / 22.44 / 22.45 | 1.69× | 90.9% | 1.91 | +68.8% |
| 2 | 24.55 / 24.63 / 24.60 | 1.85× | 79.6% | 2.59 | +9.6% |
| **3** | 24.72 / 25.39 / **25.42** | **1.91×** | 79.5% | 3.34 | +3.3% |
| **4** | 24.65 / 25.42 / **25.44** | **1.91×** | 72.3% | 3.85 | +0.1% |
| 5 | 22.09 / 22.82 / 22.83 | 1.72× | 59.7% | 3.97 | −10.3% |

**MoE — `Qwen3.6-35B-A3B-UD-IQ4_NL-MTP.gguf`** (from `MTP_PASCAL_NMAX_MMVQ.md`):

| n-max | tok/s | speedup | step Δ |
|---|---|---|---|
| none | 47.4 | 1.00× | — |
| 1 | 67.4 | 1.42× | +42.2% |
| 2 | 68.6 | 1.45× | +1.8% |
| **3** | **70.5** | **1.49×** | +2.8% |
| 4 | 35.3 | 0.74× | **−49.9%** |

## The structural finding

| | MoE 35B-A3B | dense 27B |
|---|---|---|
| optimum | **n-max 3** | **n-max 3–4** (tied) |
| what sets it | **hard kernel threshold** — verify batch 4 = IQ3_S `mmvq_mmid_max` on sm_60 | **soft economics** — acceptance vs per-cycle overhead |
| cost of overshooting by one | **−49.9%** | **−10.3%** |
| MTP speedup | 1.487× | **1.91×** |
| acceptance n1→n4 | 84.1 → 62.1% | 90.9 → 72.3% |

**Dense gets the larger MTP win (1.91× vs 1.49×)** despite being far slower in absolute terms.
Two contributors, neither isolated by a controlled run here: dense acceptance is higher at *every*
depth, and dense verify has no `MUL_MAT_ID` batch threshold to trip.

**The practical difference is the shape, not the peak.** Both peak near 3, but on the MoE that
number is a cliff edge — one step past it costs half your throughput — while on dense the whole
2–4 range is within 3.4% and overshooting is nearly free. **A "use n-max 3" rule generalised from
the MoE result would be right for the wrong reason on dense, and expensive to get wrong on MoE.**

## Predictions (logged before the run) and scoring

- **P-D1 (0.6) — FALSIFIED.** Predicted dense peaks at n-max 2, following Mark's recollection
  ("performed best with only max 2 vs 3"). Measured peak is 3–4; n-max 2 is 3.4% behind.
  ⚠️ But the curve is flat there (24.60 / 25.42 / 25.44), so a different build, quant, prompt or
  context length could easily reorder 2 and 3. This does **not** establish his earlier observation
  was mistaken — only that it does not reproduce on *this* build with *this* file.
- **P-D2 (0.7) — CONFIRMED.** No cliff on dense: largest single-step drop is −10.3% (n4→n5)
  against the MoE's −49.9%. Supports the account that the MoE cliff is a `MUL_MAT_ID` threshold
  and that dense, having no `_exps` tensors, never reaches it.
- **P-D3 (0.65) — FALSIFIED.** Predicted dense acceptance falls faster with depth. It is
  *uniformly higher* at every depth (90.9/79.6/79.5/72.3 vs 84.1/76.0/72.5/62.1) and falls at a
  similar rate. The shallower-optimum reasoning was wrong; the optimum is not shallower.

## Limits

- One prompt, one length, greedy. Acceptance is prompt-dependent.
- Two different models AND two different quants — dense/MoE is confounded with Q6_K/mixed-IQ.
  Separating them needs the same architecture at both quant levels.
- n-max 3 vs 4 on dense is inside run-to-run spread; do not claim a winner between them.

## Provenance

`.73:~/densetest/` — `dense.log`, `r_*.json`, `srv_*.log`; script `~/dense_nmax.sh`.
MoE reference: `MTP_PASCAL_NMAX_MMVQ.md`.
