# Pre-registration — does VBR at ~4.2 bpv do real work at depth?

**2026-09-03, before the run.** RX 9070 XT 16 GiB, buun `3823c9eb6`,
`Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp` (3.05 bpw). Mark's claim, which this tests:
*"if the pricing ladder is doing real work — and I think it is — 4.3 avg bpv is more than
enough if it's allocated intelligently."*

## Established before this run

- Full native **262,144** context allocates and serves: `n_ctx_slot = 262144`, 74% VRAM,
  auto KV budget **5,312 MiB**, floor mix **4.217 bits/value**.
- **16 KV layers, not 17** — resolved from the server's own pricing line (135,200 bits/token
  / 4.125 bpv = 32,768 values/token). The MTP layer takes no cache slot.
- f16 KV tops out at **71,177 tokens** in the same budget. Above that, VBR is not an
  optimisation — it is the only way to run at all.
- Short-context evidence already favours the claim: at a 16 MiB budget against a 133 MiB f16
  working set (~1.9 bpv average) the 3-term copy probe stayed **3/3 character-exact**
  (`RESULT_VBR_FORCED_DEGRADE.md`).

## What is untested

Everything above is at <=2,133 tokens. Depth is the open question: the controller's own
warning says *"the deepest fills will hit the floor clamp early"*, and a price-ordered ladder
has far more to get wrong at 100k+ than at 2k.

## Method

Needle-in-haystack. Filler is neutral technical prose; each needle is a distinctive
fact ("the calibration constant for the Meridian array is 47.3 kelvin-seconds") placed at
~10%, ~50% and ~90% of the fill. One question per needle, temp 0, seed 42, K=2.
Scored on exact retrieval of the value string.

| arm | KV | context | note |
|---|---|---|---|
| A | f16 | 65,536 | matched control — fits at f16 |
| B | vbr, floor t4 | 65,536 | matched: same depth, ~4x less KV |
| C | vbr, floor t4 | 262,144 | ~200k fill — **no f16 control is possible** |

## Predictions

| # | prediction | conf |
|---|---|---|
| P1 | Arm A (f16, 64k) retrieves 3/3 at all depths | 0.80 |
| P2 | Arm B (VBR, 64k) matches A within one needle | 0.65 |
| P3 | Arm B degrades most at the ~50% (middle) depth, the classic lost-in-the-middle position, rather than at the deepest | 0.45 |
| P4 | Arm C (200k fill) retrieves at least the ~90% (most recent) needle | 0.70 |
| P5 | Arm C retrieves the ~10% (oldest) needle — the hardest cell, deepest in a floor-clamped cache | 0.35 |
| P6 | No collapse signature (1200-token empty output) in any arm | 0.85 |

**The claim is supported if B matches A and C retrieves at 2 of 3 depths.** It is falsified if
B loses needles A finds — that would mean the bitrate, not the position, is doing the damage.

**Known weakness, stated up front:** K=2 and 3 depths is 6 cells per arm. This is an
existence probe, not a rate. A single miss will not distinguish "VBR lost it" from
"the model was never going to find it" without the matched A arm, which is why A exists.
