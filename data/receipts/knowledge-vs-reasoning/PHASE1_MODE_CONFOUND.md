# Phase 1, first attempt — VOID as a knowledge measurement (mode × arm interaction)

**Date:** 2026-08-06. **Status:** the K=5 paired comparison ran cleanly and its numbers are real, but
they do **not** measure knowledge. Recorded in full rather than discarded, per §8 — retractions stay
visible.

## What was run

Base `GLM-4.7-Flash-Q6_K` vs `GLM-4.7-Flash-REAP-23B-A3B-Q6_K`, K=5 each, 714 IKP probes
(T1–T4, `--exclude-source researcher`), temp 0, `max_tokens 64`, `-np 1`, **thinking OFF on both
arms**, `.73` 2×P100 at 1063 MHz / 150 W, build `b100-0967f4997`. G-1a asserted sigmoid on both.

```
tier          base                  reap        delta   noise  margin
T1   92.00% [92.00-92.00]  36.00% [36.00-36.00]  -56.00   0.00    inf
T2   88.00% [88.00-88.00]  20.60% [20.50-21.00]  -67.40   0.50  134.8x
T3   56.61% [56.36-56.97]   7.88% [ 7.88- 7.88]  -48.73   0.61   80.4x
T4   23.89% [22.15-24.83]   0.00% [ 0.00- 0.00]  -23.89   2.68    8.9x
ALL  68.49% [68.07-68.63]  17.68% [17.65-17.79]  -50.81   0.56   90.7x

refusal rate ALL:  12.72%  ->  61.26%   (+48.54pp)
G-5 no_answer:     0.00%   ->   0.92%   (spread 0.92pp, under threshold)
```

The replicate structure is sound: within-arm ranges of 0.0–2.7 pp against deltas of 24–67 pp. This is
not noise. **It is also not knowledge.**

## The tell

**P-R1 predicted T1 within ±2 pp and it came back −56 pp** — a miss by 28× the stated tolerance, on
the tier that asks for the capital of France. A 25% expert prune cannot plausibly do that; the model
would be visibly unusable, and the release has 926 downloads / 80 likes with no such reports.

When a pre-registered prediction fails by that margin, the instrument is the first suspect, not the
hypothesis. Ruled out before proceeding: probe set (both arms scored exactly 714, identical
exclusions), chat template (**byte-identical**, `sha=d63ad536c3c81880`, same BOS/EOS/EOT, same `glm4`
pre-tokenizer), gating function (sigmoid asserted on both), and total breakage (the pruned arm
answers Paris, Ag, Vienna correctly in fluent prose).

## The cause: thinking-off is not neutral between arms

Control on matched probe IDs, n=145, T1 only:

| condition | correct | wrong | **refusal** | no_answer | raw | answered |
|---|---|---|---|---|---|---|
| base, think **OFF** | 131 | 9 | **5** | 0 | **90.3 %** | 90.3 % |
| pruned, think **OFF** | 51 | 39 | **53** | 0 | 35.2 % | 35.2 % |
| pruned, think **ON** | 66 | 37 | **0** | 41 | 45.5 % | **63.5 %** |

Turning thinking off costs the pruned model **53 refusals out of 145**; turning it on drops that to
**zero**. The base model barely notices either way (5 refusals). The setting suppresses one arm and
not the other, so the measured gap is *scaffold-dependence + knowledge*, and this design cannot
separate them.

**This is a §6 violation, and it is the author's.** "Mode is an axis, not a setting." The spec applied
thinking-off identically to both arms and treated identical as neutral. It is not. §6 says to
enumerate modes and report all of them; a single mode was chosen on an argument that sounded right
(recall is not a reasoning task, and a `<think>` chain under a token budget truncates — both true)
without testing whether the choice interacted with the variable under study.

Same error shape as the others this week: a plausible mechanism accepted without confirming which
path executed.

## What survives, and what does not

**Survives:** a large, highly reproducible difference exists between the arms; the pruned model
produces fluent confident errors on trivial facts (*"The capital of Canada is Toronto"*, *"capital of
Portugal is Madrid"*, the Strait of Messina declared *"a fictional geographical feature"*); and
thinking-off suppresses the pruned arm far more than the base arm — itself a finding worth keeping.

**Does not survive:** any magnitude for a knowledge deficit. The −56 pp / −67 pp / −50.8 pp figures
above must not be cited as knowledge loss.

## Required fix: the 2×2, and the ON/ON contrast is the honest number

| | think OFF | think ON |
|---|---|---|
| base | 90.3 % (n=145) | **← the missing cell** |
| pruned | 35.2 % (n=145) | 63.5 % answered (n=145, 41 truncated) |

Comparing pruned/ON (63.5 %) against base/OFF (90.3 %) is unmatched on mode and is not a result.

**Anticipated G-5 problem in the ON cell.** The pruned arm truncated **41/145 = 28 %** even at
`max_tokens 512`, because it rambles in reasoning. If base/ON truncates materially less, the ON
comparison inherits exactly the divergent-termination problem G-5 exists to catch, and accuracy must
be reported over answered items with both denominators visible rather than as one number.

## Open, unrelated to the above

`IKP_T2_0363` returns **HTTP 500** from llama-server on the pruned arm in **all five** runs, and never
on the base arm. A reproducible server-side failure tied to one input and one model file is worth
isolating on its own; it may be a genuine defect in the pruned GGUF rather than anything about
recall.

## Spec amendments this forces

1. **Mode must be run as an axis, not fixed.** Both arms × both modes, minimum, before any knowledge
   claim. §6 already said this; the spec violated it.
2. **Refusal rate is a primary readout, not context.** The base-vs-pruned refusal gap under
   thinking-off (12.7 % → 61.3 %) was the loudest signal in the whole run and it is not a knowledge
   metric.
3. **A pre-registered prediction missing by an order of magnitude is a stop condition.** P-R1 failing
   by 28× should halt reporting and start diagnosis — which is what happened here, but by judgement
   rather than by rule. Make it a rule.
