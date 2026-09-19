# Finding -- the KLD decay slope is ~ln(4) per bit across three codec families

**2026-09-19, from the completed stock panel plus the EXL3 campaign.** Prompted by Mark asking
whether Qwen3.8-27B might simply be unusually good at 3-4 bits, shifting expectations.

## The measurement

Fitting `KLD ~ A * exp(-lambda * bpw)` on scored bytes:

| family | points | lambda | vs ln(4) = 1.3863 |
|---|---:|---:|---:|
| GSQ-RCO | 2 | 1.4077 | +1.5% |
| AD | 3 | 1.4156 | +2.1% |
| EXL3 (campaign) | 5 | 1.4542 mean | +4.9% |

EXL3's per-segment values scatter more (1.2261 to 1.6420). Some of that is real and some is
rounding: the campaign quotes KLD to four decimals, so at its smallest value (0.0040) the relative
precision is only ~1%, which propagates hard into a segment slope.

## Why ln(4) is the number to compare against

For a uniform scalar quantiser, one additional bit halves the step size, which quarters the error
variance. KL divergence is locally quadratic in a small weight perturbation, so it should track
that variance:

```
KLD ~ 4^(-bits) = exp(-ln(4) * bits),   ln(4) = 1.3863
```

**The striking part is that these codecs are nothing like uniform scalar quantisers.** They use
codebooks, per-tensor mixed precision, importance weighting, and in Bonsai's case a Hadamard
rotation. They follow the textbook scalar scaling anyway, to within a few percent.

**The slope looks like a property of information theory, not of the codec.** Codecs compete on the
prefactor `A` -- how efficiently each bit is spent -- not on the rate of decay. That is the same
conclusion reached independently in [[METHOD_SCORED_BYTES]] ("same slope, different intercept") and
in the EXL3 campaign's flat-log-gap finding, now with a theoretical anchor for *why* the slope is
shared.

## Bearing on "is Qwen3.8-27B just unusually good at low bits?"

The hypothesis splits, and the two halves are very different:

**(a) The model is unusually quantisation-ROBUST.** If lambda is theory-driven it should be
model-independent, so robustness cannot appear as a flatter slope. It could only appear as a lower
*intercept* -- this model's weight distributions happening to quantise more cleanly than another's.
**Plausible and entirely untested.** There is no weight-quantisation KLD ladder for any second
model in this repo; everything is Qwen3.8-27B. (`layer-pricing/RESULT_4B_CONTROL.md` covers
Qwen3.5-4B but for KV-cache banding, a different question.)

**(b) The model is simply strong enough that a degraded copy still clears the bar.** This requires
no robustness at all, and **this panel structurally cannot distinguish it**, because:

> **KLD is self-referential.** Every value here is a distance from *that model's own Q8_0*. It
> says nothing about whether the model is good. A 2024 model at KLD 0.01 is very close to its own
> mediocre full-precision self; Qwen3.8-27B at 0.10 is further from its own excellent self and may
> still be far more capable in absolute terms.

So "expectations changed" is fully explained by base-model improvement, with zero codec progress
and zero unusual robustness. This ladder cannot see that, by construction.

This is the third time today the same blind spot has decided a question: the fidelity metric cannot
observe absolute capability, which is also why it cannot settle the Bonsai usability reports
([[EXTERNAL_OBSERVATION_2026-09-19]]) or the 3-bit floor claim in the sense it was meant
([[PREDICTION_MARK_3BIT_FLOOR]]).

## The experiment that would settle (a)

Run this same ladder on a **second model**, same reference discipline, and compare **intercepts at
matched scored bpw**. Two predictions worth preregistering:

| id | prediction |
|---|---|
| P-M1 | the second model's lambda also lands within ~10% of ln(4) -- i.e. the slope is model-independent |
| P-M2 | the intercepts differ, and that difference is what "this model quantises well" actually means |

A smaller model makes this cheap: fewer parameters means faster load and faster chunks, so five
cells is plausibly ~40 minutes rather than ~80. It needs its own Q8_0 reference and its own gate
cell, which is the real cost and is non-negotiable -- the P-L0 discipline applies per model.
