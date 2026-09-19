# Finding -- one 18-point fidelity curve across five codec families, and GSQ-RCO is not on it

**2026-09-19, built while the ladder's fifth cell was still running.** Merges this ladder with the
EXL3 campaign's test-10 compression curve (`exl3-campaign/RESULT_EXL3_COMPRESSION.md`). No new GPU
time: the two datasets were already comparable and nobody had put them on one axis.

## Why they can be merged

Both used **the same `ref.kld`** (Qwen3.8-27B Q8_0 @ `4ca72078`, 29,047,086,048 B), the same
`wiki.test.raw` (sha `173c87a5...`), the same `buun-sm60-qual` binary and the same frozen flags
(`-c 512 -b 512 -ub 8 --chunks 40`, f16 KV). The only obstacle was the reporting axis: that
campaign records **peak VRAM MiB**, this ladder records **file bytes**.

**The bridge came from two cells I ran redundantly.** `A-IQ2XS` and `A-IQ3XXS` had already been
measured there as `G2x` and `G3xx`; I did not check the existing receipts before spending ~34
minutes of GPU time re-running them. They reproduce to every digit that campaign printed:

| cell | prior | ours | agreement |
|---|---|---|---|
| A-IQ2XS | 0.1745 / 81.7% | 0.174453 / 81.735% | 0.000047, 0.035 pp |
| A-IQ3XXS | 0.0737 / 88.5% | 0.073686 / 88.529% | 0.000014, 0.029 pp |

Because those two arms have **both** a file size and a peak-VRAM figure, they calibrate the axis:

```
A-IQ2XS    scored  9153.2 MiB   peak VRAM  9272 MiB   offset +118.8
A-IQ3XXS   scored 11237.8 MiB   peak VRAM 11358 MiB   offset +120.2
```

Two independent points agreeing to **1.3 MiB** -- the fixed KV + compute buffer at these flags. So
`VRAM_MiB = scored_MiB + 119.5`, and converting the campaign's 13 points back through it lands
A-IQ2XS at 2.822 and A-IQ3XXS at 3.465 scored bpw, **exactly** our measured values.

The redundant runs paid for themselves twice: a cross-session validation of the harness, and the
calibration that makes an 18-point curve possible. That does not excuse not searching first.

## The curve

Sorted by scored bits per weight. "Envelope" marks a new best KLD at increasing size.

| arm | family | scored bpw | mean KLD | top-1 | envelope |
|---|---|---:|---:|---:|---|
| GSQ-RCO IQ2_XS | GSQ-RCO | 2.476 | 0.2022 | 81.5% | (leftmost only -- see note) |
| EXL3 2.50bpw | EXL3 | 2.774 | 0.0934 | 87.3% | **yes** |
| AD-IQ2_XS | AD | 2.822 | 0.1745 | 81.7% | |
| UD-Q2_K_XL | unsloth | 2.862 | **0.0842** | 87.3% | **yes** |
| GSQ-RCO IQ3_XXS | GSQ-RCO | 2.968 | 0.1012 | 86.5% | |
| EXL3 3.00bpw | EXL3 | 3.221 | **0.0462** | 90.7% | **yes** |
| AD-IQ3_XXS | AD | 3.465 | 0.0737 | 88.5% | |
| UD-IQ3_XXS | unsloth | 3.518 | 0.0476 | 90.9% | |
| EXL3 3.50bpw | EXL3 | 3.668 | **0.0250** | 93.3% | **yes** |
| i1-IQ3_M | i1 | 3.737 | 0.0613 | 89.8% | |
| EXL3 4.00bpw | EXL3 | 4.115 | **0.0120** | 95.4% | **yes** |
| UD-IQ4_XS | unsloth | 4.125 | 0.0157 | 94.2% | |
| UD-Q4_K_M | unsloth | 4.726 | **0.0078** | 96.2% | **yes** |
| EXL3 5.00bpw | EXL3 | 5.011 | **0.0040** | 97.2% | **yes** |
| Q6_K | stock | 6.522 | **0.0028** | 97.7% | **yes** |

**Note on the leftmost point:** GSQ-RCO IQ2_XS is "on the envelope" only because it is the
smallest file measured and nothing exists to compare it against at that size. Its KLD of 0.2022 is
the **worst number in the entire table.** That is an artifact of sort order, not a result.

## Finding 1 -- the envelope belongs to EXL3 and unsloth, alternating

**GSQ-RCO never appears on it. Neither does AD.** In the contested 2.8-3.0 bpw band:

| arm | scored bpw | mean KLD | top-1 |
|---|---:|---:|---:|
| **UD-Q2_K_XL** | 2.862 | **0.0842** | 87.3% |
| EXL3 2.50bpw | 2.774 | 0.0934 | 87.3% |
| GSQ-RCO IQ3_XXS | 2.968 | 0.1012 | 86.5% |
| AD-IQ2_XS | 2.822 | 0.1745 | 81.7% |

**unsloth's UD-Q2_K_XL is SMALLER than GSQ-RCO IQ3_XXS (2.862 vs 2.968 bpw) and 17% closer to the
reference (0.0842 vs 0.1012).** GSQ-RCO is mid-tier: a large win over AD, a clear loss to both
unsloth and EXL3 at matched size.

This bears directly on the public advice logged in `EXTERNAL_OBSERVATION_2026-09-19.md`, which
recommends GSQ-RCO over Bonsai for anyone with >=12 GB VRAM. On this model and this metric, the
recommendation points at a mid-tier option: **unsloth's UD recipe is smaller and better.** The
comparison the thread never ran is GSQ-RCO against unsloth, not against Bonsai.

It also echoes the original campaign's own finding 4: *"Choosing the GGUF packager is worth as
much as choosing the format."* Here it is again with two more packagers on the board.

## Finding 2 -- "3-bit is the new 4-bit" fails, but a weaker version holds

On the merged axis, EXL3's nominal *3.00bpw* is really **3.221 scored bpw** at KLD 0.0462, against
UD-IQ4_XS at 4.125 bpw and 0.0157 -- still **2.9x apart**, and EXL3 needs ~3.82 nominal bpw to
cross it. turboderp's Flash-Next chart places EXL3 3.05bpw level with UD-IQ4_XS; that does not
reproduce here, as `RESULT_EXL3_COMPRESSION.md` already reported independently.

**The weaker claim does hold, and it is not trivial:** EXL3 at 3.221 bpw (0.0462) beats
**AD-IQ3_XXS at 3.465** (0.0737) and **i1-IQ3_M at 3.737** (0.0613). A good 3-bit codec now beats
mediocre quants a half-bit to a full bit larger. The floor has not moved from 4 to 3; the *spread
between codecs at a given size* has grown large enough that codec choice outweighs a half-bit of
size. See [[PREDICTION_MARK_3BIT_FLOOR]].

## Caveats

- One model (Qwen3.8-27B), one corpus (wikitext-2, 40 chunks), one metric family.
- Campaign KLD values are quoted at 4 decimals; ours at 6. Every gap discussed above is far larger
  than that rounding.
- The 119.5 MiB axis offset is derived from two points. They agree to 1.3 MiB and both land on
  their independently measured bpw, but it is a two-point calibration.
- **KLD over wikitext does not measure agentic usability.** This project has documented that gap
  twice. A codec ranking here is a fidelity ranking, not a verdict on task behaviour.

## Fairness note on the GSQ-RCO verdict

Two things keep "GSQ-RCO is mid-tier" honest rather than a dunk:

**1. The comparison is sound on the axis used.** The campaign's peak-VRAM figures were measured
during runs that *ignore* the MTP head, so VRAM already reflects loaded-and-scored tensors only.
Converting VRAM to scored bytes and comparing against our file-minus-MTP figures compares like
with like. The two arms present in both datasets land on their independently measured bpw, which
is the check that this is true.

**2. GSQ's files ship an MTP head and some competitors' may not.** The GSQ-RCO releases are named
`-mtp` and carry ~348 MB of draft head. Those bytes buy **speculative decoding**, which is real
deployment value and which this measurement cannot see -- the fleet's own daily driver runs
`--spec-type draft-mtp`. Scored-bytes accounting correctly removes them from the *fidelity*
comparison, and equally correctly does not credit them. So:

> **On fidelity per byte, GSQ-RCO loses to unsloth and EXL3. On what you can actually deploy, a
> GSQ file additionally gives you a draft head.** Those are different questions and this receipt
> only answers the first.

**What would change the verdict:** a measurement of UD-Q2_K_XL and GSQ-RCO IQ3_XXS at matched
*wall-clock serving throughput* rather than matched bytes. If GSQ's MTP head buys enough decode
speed, a user might rationally prefer the slightly-worse-per-byte file. Not measured here, and not
claimed either way.
