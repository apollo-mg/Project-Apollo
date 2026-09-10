# VBR on Qwen3.8-27B at 2/3 bpw: it runs — but this run did NOT exercise degradation

**2026-09-03.** RX 9070 XT (gfx1201), buun-llama-cpp `3823c9eb6` (contains `424c3361e`).
Models: ISTA-DASLab GSQ-RCO `IQ3_XXS-mtp` (3.05 bpw) and `IQ2_XS-mtp` (2.58 bpw).
Pre-registered in `PREDICTION_VBR_QWEN38_GSQ.md`. Raw: `raw_vbr_qwen38.jsonl` / `.log`.

## Headline, stated correctly

**29 of 30 cells clean — and that number means much less than it looks like, because the KV
cache never left the f16 entry tier in any arm.**

Byte-identity against the f16 control is the test for whether VBR actually degraded:

| arm | budget | byte-identical to f16 |
|---|---|---|
| `iq3_vbr_256` | 256 MiB | **6 of 6** |
| `iq3_vbr_512` | 512 MiB | 5 of 6 |
| `iq3_vbr_auto` | 5,480 MiB | 4 of 6 |

Identical output means identical cache precision. **The tightest budget I set produced output
indistinguishable from f16, so no degradation occurred.**

## Why the design failed

I sized the budgets against the *declared* context (`-c 32768` -> 2.0 GiB at 64 KiB/token)
and assumed 256 MiB would force the ladder. But the cache fills with the *working set*, and
the longest probe is 2,133 tokens = **133 MiB at f16** — comfortably inside 256 MiB. The
controller armed on every arm and correctly never needed to degrade anything.

This is the same failure the stock-arm receipt records from 2026-08-19 —
*"kv_bpv pinned 16.0 all session — VBR never degraded"* — reached by a different route.
I checked that the controller armed, and never checked that it *acted*.

**Correct design:** the budget must sit below the working set. For the 2,133-token probe,
`--vbr-vram 64MiB` forces ~2x compression and `32MiB` ~4x; or drive the working set up with
20k+ token prompts against a 512 MiB budget.

## Prediction scoring

| # | prediction | conf | outcome |
|---|---|---|---|
| P1 | degrade order resolves via the KV-layout fallback | 0.65 | **UNRESOLVED** — no `VBR degrade order` line was emitted on any arm |
| P2 | `--vbr-vram auto` never degrades on a 16 GiB card | 0.80 | **HIT** |
| P3 | a forced small budget actually degrades | 0.75 | **FALSIFIED** — 256 MiB degraded nothing |
| P4 | output stays coherent under forced degradation | 0.70 | **VACUOUS** — no degradation to survive |
| P5 | IQ2_XS degrades quality more than IQ3_XXS at equal budget | 0.55 | **UNTESTABLE** here |
| P6 | the MTP layer takes a KV slot (17 vs 16), breaking the set match | 0.30 | **UNRESOLVED** |

## What the run does establish

- VBR **arms cleanly** on this model class post-fix, on both quants, at every budget:
  `"VBR dynamic runtime controller: KV budget N (explicit), entry tier f16, floor 1.25
  bits/value, price-ordered decode-time degrades"`.
- Fit prices the KV at the floor tier up front:
  `"fitting with KV priced at the turbo1_tcq floor tier"`.
- **Entry tier is now `f16`.** That is `283ba19ed` ("vbr: support configurable dynamic entry
  tiers") answering the map's finding that the `q27` ladder's first step was already a turbo
  tier, so any budget pressure at all put turbo tensors in the cache.
- With explicit `-ctk vbr -ctv vbr` the floor defaults to **1.25 bits/value (turbo1_tcq)**,
  the bottom of the ladder; implicit VBR gets a t4 = 4.125 floor. The explicit form is far
  more aggressive than what a normal user lands on.
- IQ2_XS serves fine at 2.58 bpw — 3/3 on both probes, ~65% VRAM at `-c 32768`.

## The one anomaly, honestly scoped

`iq3_vbr_auto / long1500 / rep 3`: **`finish=length`, 1,200 completion tokens, zero content
characters** — the exact pre-fix collapse signature, generation that never leaves the
thinking block.

Scope: **1 occurrence in 30 cells.** It did not reproduce in reps 1-2 of the same arm, in
either fixed-budget arm, or on IQ2_XS. The f16 control answered the identical prompt in 495
tokens with content, 3 of 3. So it is not the prompt.

It appeared only on the arm with the **largest** budget — the one with the most tiers
available and the most room to vary as the cache fills across requests — which is the
opposite of where budget pressure lives. That makes it interesting rather than obviously a
residual of the fixed bug.

**Not enough to report to buun.** One cell, no reproduction, and a test that never exercised
the feature.

## Next

1. Re-run with `--vbr-vram` at 64 MiB and 32 MiB so the ladder is actually walked.
2. K>=10 on `iq3_vbr_auto / long1500` to establish whether the anomaly is real and at what rate.
3. Find why no `VBR degrade order` line is emitted — if the order resolves only on first
   degradation, (1) answers P1 and P6 too.

## Method note — a probe that lied, and the fix

The first attempt at this run used **port 8099, which is `apollo-wake-proxy`** (serving
Qwen3.8-27B off `.73`). `llama-server` failed to bind and exited immediately
(`couldn't bind HTTP server socket ... port: 8099`), `/health` was answered by the proxy in
1 second, and **six probes were served by the wrong machine** before the 14%-VRAM reading
gave it away.

Readiness now gates on identity, not on a 200: after `/health`, query `/props` and require
`model_path` to end with the basename of the model actually passed on the command line;
abort loudly if a different model answers. Plus a pre-flight check that refuses to launch
into an occupied port. All results above are from the identity-gated run.
