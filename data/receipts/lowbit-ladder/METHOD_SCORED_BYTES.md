# Method note -- quality per byte, and which bytes actually count

**2026-09-19, written mid-panel** (three stock cells scored, Bonsai cells not yet run).
Adopted at Mark's direction: *"I prefer to measure quality against file size. I think it's the
most fair way."* Agreed -- the quant label is marketing, the bytes are the bill, and file size is
what you actually pay in VRAM headroom and in what context you can afford beside it.

This note records a correction that makes that axis honest.

## Not all bytes in the file are measured

The gate run printed, fifteen times, lines of the form:

```
W model has unused tensor blk.64.nextn.eh_proj.weight (size = 55705600 bytes) -- ignoring
```

`blk.64` is the **MTP (multi-token prediction) draft head**. `llama-perplexity` does not read it.
So those bytes sit in the file, are paid for on disk, and contribute **nothing** to the KLD being
measured. Verified exhaustively: the binary's own unused-tensor list is exactly `blk.64.*` /
`.nextn.*` and nothing else, so the accounting below covers precisely the ignored set.

| cell | MTP head bytes | share of file | raw bpw | **scored bpw** |
|---|---:|---:|---:|---:|
| G-IQ2XS | 348,469,248 | **3.97%** | 2.579 | **2.476** |
| A-IQ2XS | 292,067,328 | 2.95% | 2.908 | 2.822 |
| G-IQ3XXS | 348,469,248 | 3.34% | 3.070 | 2.968 |
| A-IQ3XXS | 292,067,328 | 2.42% | 3.550 | 3.465 |
| A-IQ3S | 292,067,328 | 2.25% | 3.817 | 3.732 |
| B-PTQ1 | **0** | 0.00% | 1.748 | 1.748 |
| B-PQ2 | **0** | 0.00% | 2.119 | 2.119 |

**The families are not charged equally.** GSQ-RCO spends ~4% of its file on a draft head; AD
spends ~3%; **Bonsai 2 ships none at all.** Raw file size therefore overcharges GSQ relative to
AD, and overcharges both relative to Bonsai.

Effective parameter count 27.21e9, recovered from the four cells whose bpw the prereg states and
reproducing all four to within 0.02.

## Consequences, including one against our own prediction

**P-L2 gets HARDER, not easier.** The prereg frames B-PQ2 as *"1.56 GB smaller and 0.45 bpw
lower"* than G-IQ2XS. On scored bytes that is **1.13 GiB and 0.36 bpw** -- Bonsai's size
advantage shrinks by 22%. Recorded plainly because it cuts against the prediction this project
made.

**The MTP bytes are not waste in production.** They are only waste *to this measurement*. A draft
head buys speculative decoding, and the fleet's own daily driver runs `--spec-type draft-mtp`. So
"scored bytes" is the right axis for a fidelity-per-byte question and the wrong axis for a
what-do-I-deploy question. Both are reported; neither is presented as the single truth.

## The comparison this enables: matched file size

With two GSQ cells measured, GSQ's own KLD-vs-size curve is known and any other codec can be
priced against it at **identical file size** -- which is what "at comparable size" in P-L3 was
reaching for, and what the quant labels obscure.

```
GSQ curve:  G-IQ2XS  2.476 bpw  KLD 0.202243
            G-IQ3XXS 2.968 bpw  KLD 0.101180
            exchange rate: 0.2054 KLD per scored bpw
            (+0.492 bpw halves KLD)
```

Applied to AD at the IQ2_XS label:

| | |
|---|---|
| A-IQ2XS, measured | 2.822 bpw, KLD **0.174453** |
| GSQ interpolated to that same size | KLD **0.131170** |
| **at matched file size** | **GSQ is 24.8% lower KLD** |
| AD's extra +0.346 bpw over G-IQ2XS should buy | 0.071073 KLD |
| it actually buys | 0.027790 KLD |
| **AD captures** | **39% of what its extra bytes should deliver** |

**So P-L3 is falsified on the naive reading and confirmed on the size-normalised one.** AD posts
the lower raw KLD at the shared `IQ2_XS` label, but only by carrying 13% more bytes, and it
converts those bytes at well under half the rate GSQ's own curve sets. Both readings are reported.
The naive one is not wrong, it is answering a different question: *"which file is better?"* rather
than *"which codec is better?"*

**Limitation, stated:** the GSQ curve is a two-point linear fit. The A-IQ2XS interpolation falls
*inside* the measured range, which is the safer case, but a two-point fit cannot show curvature.
A-IQ3XXS and A-IQ3S will give AD its own curve, allowing the same comparison in the opposite
direction as a check; if the two directions disagree, the linearity assumption is what broke.

## Generalisation worth keeping

This is [[gguf-label-is-not-a-spec]] appearing across packagers rather than within one. `IQ2_XS`
names a *recipe*, not a size: it is 2.58 bpw from ISTA-DASLab and 2.91 bpw from AD, a 13% spread
under one label. Any comparison keyed on the label rather than on measured bytes silently compares
different size classes and attributes the difference to the codec.

---

# Amendment -- 2026-09-19 12:45: the linear fit above is WRONG, use log-linear

**The 24.8% figure above is superseded. Corrected value: ~30%.** The number moved because the
model was wrong, not because the data changed. Kept in place rather than edited away, because the
error is instructive.

## Why linear was inadmissible

A second AD cell (A-IQ3XXS, 3.465 scored bpw, KLD 0.073686) made it testable, and linear fails on
its own terms:

```
GSQ linear fit extrapolated to 3.465 bpw -> KLD -0.000910
GSQ linear fit extrapolated to 3.732 bpw -> KLD -0.055755
```

**KL divergence cannot be negative.** A model that predicts a negative divergence a third of a bit
beyond its anchors is not slightly imprecise, it is the wrong functional form.

The second symptom: under a linear fit the two families' rates differ by **24%** (GSQ 0.2054, AD
0.1567 KLD per bpw), which would say the codecs improve at fundamentally different rates.

## Log-linear, and what it reveals

| family | decay constant | KLD multiplier per +1 bpw |
|---|---:|---:|
| GSQ-RCO | 1.4077 / bpw | x0.245 |
| AD | 1.3403 / bpw | x0.262 |

**4.8% apart, against 24% apart under the linear fit.** The families improve at essentially the
same exponential rate and differ by a constant multiplicative factor -- which is what a codec
*quality* difference ought to look like, as opposed to two different scaling behaviours.

```
KLD(bpw) ~ A * exp(-1.37 * bpw)      lambda within 5% across both scalar families
```

Restated: **every additional bit per weight cuts KLD by about 4x, for both packagers.** The
codecs are not competing on slope, they are competing on intercept.

## Corrected matched-size result

| at scored bpw | GSQ (log-linear) | AD (measured) | GSQ advantage | |
|---|---:|---:|---:|---|
| 2.822 | 0.124265 | 0.174453 | **28.8%** | interpolated |
| 3.465 | 0.050264 | 0.073686 | **31.8%** | *extrapolated* |

**GSQ-RCO is ~30% lower KLD than AD at matched file size.** The 2.822 row is interpolated inside
GSQ's measured range and is the load-bearing one; the 3.465 row sits beyond GSQ's largest cell and
is flagged as extrapolated in the scorer output.

Independent cross-check on same-top, which only depends on the argmax and not on the distribution
shape, agrees: AD carries **+22.1%** more top-1 errors at 2.822 bpw and **+37.9%** at 3.465.

## The lesson worth keeping

The correction was found by a check that had been stated in advance: *"the GSQ curve is a two-point
linear fit... A-IQ3XXS and A-IQ3S will give AD its own curve, allowing the same comparison in the
opposite direction as a check; if the two directions disagree, the linearity assumption is what
broke."* It did disagree, and linearity is what broke.

**Two points can always be joined by a line.** With only G-IQ2XS and G-IQ3XXS there was no way to
see the curvature, and no residual to inspect -- a two-point fit has zero degrees of freedom and
therefore always looks perfect. The sanity check that caught it was not statistical at all: it was
asking whether the fit predicts values the quantity is allowed to take.
