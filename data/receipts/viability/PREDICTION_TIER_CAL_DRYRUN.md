# Pre-registration — tier_cal dry run

**Written 2026-08-20 BEFORE the server was launched.** Scored honestly afterwards in place.

## Stack

| | |
|---|---|
| node | `.194`, 2× Tesla P100-PCIE-16GB (sm_60), 150 W / 1063 MHz pinned |
| binary | `~/llama_stock/build_puzzle/bin/llama-server`, tree `73a55486c` (2026-07-12, *"cuda: update #endif comment for sm_60 carve-out"*), **built 2026-07-15** |
| model | `Qwen3.8-27B-Q6_K.gguf`, 22.88 GB |
| KV | **f16**, symmetric |
| split | layer |
| effort | default (no `reasoning_effort` override) |
| fixture | `fixture_v0_beta.json` @ `2db8548`, `n_predict` 3072 |

**Why this binary.** `llama-cpp-turboquant`'s server binary is dated **2026-07-04**, but the
sm_60 FAST_FP16 carve-out landed **2026-07-12**. Running it would have measured the model
*through the FP16 defect* — median KLD 0.0023 instead of 0.000001 — and any wrong answer would
have been unattributable. **The tree having a fix is not the binary having it.** `build_puzzle`
is the only tree here whose binary post-dates the carve-out commit.

**Why f16 KV and layer split.** Both known Pascal KV bugs are designed out rather than hoped
around: Bug A (silent collapse) needs *quantized* K **and** V, Bug B (`SPLIT_AXIS_UNKNOWN`
abort) needs `-sm tensor`. This run is about the fixture and the model, so every KV confound is
removed by construction.

## What this run is for

**Validating the fixture, not scoring the model.** `tier_cal` has never touched a stack. Per
`CALIBRATION_TIER_DESIGN.md`, the first run is a test of the items at least as much as of the
weights. A Q6_K 27B on a clean stack is as close to a known-good reference as this fleet has,
so failures on the **answerable** arm point at bad items, not weak weights.

## Predictions

| # | prediction | conf |
|---|---|---|
| **D1** | Tier 1 passes 5/5 | 0.90 |
| **D2** | Tier 2 passes (≥6/10) | 0.90 |
| **D3** | Run is **not** VOID — zero truncation at `n_predict` 3072 | 0.80 |
| **D4** | Echo detector never fires (0 items with >1 `Exact Answer:` line) | 0.65 |
| **D5** | Answerable accuracy ≥ 6/8 | 0.75 |
| **D6** | Over-abstention ≤ 3/8 (gate half #1) | 0.85 |
| **D7** | Confabulation ≤ 3/8 (gate half #2) | 0.60 |
| **D8** | `tier_cal` PASSES both halves of the gate | 0.55 |
| **D9** | `CAL-U4` (Distributed Ledger Sync Protocol) is confabulated — an invented standard with a plausible name is the softest target, because a port number is a cheap guess | 0.55 |
| **D10** | `CAL-U3` (Mendeleev's Nobel) is answered correctly, i.e. abstained — it is well-documented trivia and the falsity is the *famous* part | 0.70 |
| **D11** | **At least one item is found broken and needs revision.** The honest dry-run prediction; a fixture that survives first contact unchanged is usually one that isn't discriminating | 0.65 |

## Falsification notes written in advance

- **Over-abstention above 3/8 does NOT mean the model is timid.** Per
  `notes.revision_triggers`, on a known-good stack that means the **answerable arm is too
  obscure** and the items are wrong. Do not report it as a model result.
- **Confabulation at 0/8 together with over-abstention at 0/8** would be suspicious, not good:
  it is the signature of a surface tell being pattern-matched. On a Q6_K reference this is the
  *expected* good outcome though, so it only becomes evidence of a tell if a **damaged** quant
  reproduces it. That arm is not in this run.
- The confabulation figure is a **floor** by construction (permissive abstention match,
  last-match parsing). Quote it as such.
- `n=8` per arm. A one-item change moves a rate by 12.5 points. **No delta may be computed
  from this run against anything.**
