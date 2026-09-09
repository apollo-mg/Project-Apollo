# RESULT: DavidAU 40B merge — coherence smoke + measured power

**Date:** 2026-09-08 · **Node:** `.73`, dual P100 @ 150 W cap / 1063 MHz · **Build:** `build_a56` @ `a56eeef5`
**Model:** `Qwen3.6-40B-GrIntell-F-Fusion-Uncen-Htic-NEO-MAX-MTP-IQ4_XS.gguf` (22.08 GiB)
**Config:** `--split-mode tensor --spec-type draft-mtp -c 32768 -np 1 -ctk/-ctv vbr --vbr-floor t2`
**Sampling:** temperature 0.7, top_p 0.95 · **max_tokens 8192**

## Smoke result: passes all four arms, n=1 each

| arm | verdict | answer |
|---|---|---|
| A. instruction format | **PASS** | `101, 103, 107` — three primes, comma-separated, no preamble |
| B. factual | **PASS** | "The capital of Australia is Canberra. A common wrong answer people give is Sydney." |
| C. **abstention** | **PASS** | "There is no publicly traded company named *Acme Dynamics Corporation*… *Acme* is commonly used as a fictional company name" |
| D. reasoning | **PASS** | 0.05, with breakdown, and explicitly names the intuitive 10¢ trap as wrong |

All arms `finish=stop`. Loop check: top repeated 6-gram ×1 in every arm. Script check: CJK=0,
Cyrillic=0 — no code-switching, which is a real failure mode for multi-parent merges.

**Arm C is the load-bearing one.** Asked for the exact closing share price of a company that does not
exist, it abstained *and* named the reason. For a candidate advisor model, confabulating there would
have ended the evaluation.

**Reasoning-model tax is heavy:** 939 reasoning chars to produce a 13-character answer (arm A);
1,912 for bat-and-ball. Budget accordingly — see the invalidation note below.

## v1 of this smoke test was INVALID — recorded so the mistake is not repeated

Smoke v1 capped `max_tokens` at 200–900. Every arm returned `finish=length` with **empty content**
and non-empty reasoning: the model spent the entire budget thinking and never emitted an answer. It
measured the cap, not the model.

**Backlog A5 already said this in plain text:** *"Do NOT cap per-item below ~7.5k — `CAL-U5` needed
7109 and a 3072 cap scored it as truncation, hiding a real confabulation."* The warning existed, in
our own receipts, and was not applied. v2 uses 8192.

This was the fifth wrong-semantics measurement of 2026-09-08 (after `tg`, `reused`, the decode
survivorship bias, and the block-buffered log). It is the only one where the correct procedure was
already written down. See AFM-34.

## Measured power under load

Sampled every 2 s **during generation** (an earlier sample caught the cards idle at 405 MHz / 27 W
and would have understated draw by ~4×).

| arm | peak (both cards, W) | mean (W) |
|---|---|---|
| A_format | 202 | 172 |
| B_fact | 198 | 131 |
| C_abstain | 207 | 190 |
| D_reason | **216** | **195** |

**~108 W per card at peak, against a 150 W cap** — decode is memory-bandwidth bound, so the cards
wait on HBM rather than saturating the power budget. Mark's independent observation ("just above
100 W/ea") matches.

### Energy per token

Host adds ~50 W (8600K, largely idle during GPU inference) + ~40 W mobo/RAM/fans + ~10 W drives,
divided by ~0.90 PSU efficiency → **~330 W at the wall**, which matches Mark's estimate.

| basis | rate | J/token | tokens/kWh |
|---|---|---|---|
| controlled 64-token decode | 16.20 tok/s | **20.4** | ~177,000 |
| 848-token generation, end-to-end | 20.7 tok/s | **15.9** | ~226,000 |

**~16–20 J per output token.** Longer generations are cheaper per token as startup amortises.

**Do not quote a $/token figure without these caveats:** batch-1 (cloud serving amortises weights
across a batch, which is most of how hosted pricing gets low), output tokens only, excludes the
~300 s cold load from spinning disk, excludes idle draw. The defensible claim is the physical one —
*a 40B dense model at ~16–20 tok/s costs ~16–20 J per output token on two power-limited P100s* —
not a dollar comparison against APIs serving at concurrency we are not running.

## Status

Smoke is a gate, not a benchmark: n=1 per arm, four items, one sampling setting. It says the model
is **worth spending real fixture time on**, and nothing about capability ranking.

**Next:** `tier_cal` (15 items, calibration/abstention) on this model AND on
`Qwen3.6-27B-Q6_K-MTP` as a control — same node, same `build_a56` binary, per AFM-26 and the
`a56eeef5` build boundary.
