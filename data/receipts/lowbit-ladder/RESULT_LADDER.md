# Result -- the low-bit codec ladder: 5 of 6 predictions confirmed, the headline one falsified

**2026-09-19, 10:48 to 14:03 EDT on `.73`** (dual Tesla P100, sm_60). Prereg:
`PREREG_CODEC_LADDER.md`, committed before any cell ran, plus three dated amendments each written
before the data they bear on.

Every cell: same model family (Qwen3.8-27B), same reference (`ref.kld`, 5,065,891,540 B), same
corpus (`wiki.test.raw`, sha `173c87a5...`), same frozen invocation, same two GPUs.

## The panel

Size axis is **scored bytes** -- file minus the MTP draft head `llama-perplexity` ignores. See
`METHOD_SCORED_BYTES.md`.

| cell | codec | scored bpw | mean KLD | same-top | s/pass | wall |
|---|---|---:|---:|---:|---:|---:|
| B-PTQ1 | Bonsai 2 PTQ1_0 | 1.748 | 0.358015 | 76.520% | 51.30 | 2180s |
| B-PQ2 | Bonsai 2 PQ2_0 | 2.119 | 0.358047 | 76.510% | **14.58** | **747s** |
| G-IQ2XS | GSQ-RCO IQ2_XS | 2.476 | 0.202243 | 81.471% | 19.01 | 954s |
| C-XBIN | *(control: G-IQ2XS on prism)* | 2.476 | 0.202212 | 81.422% | 19.24 | 1026s |
| A-IQ2XS | AD IQ2_XS | 2.822 | 0.174453 | 81.735% | 21.19 | 1016s |
| G-IQ3XXS | GSQ-RCO IQ3_XXS | 2.968 | 0.101180 | 86.549% | 29.43 | 1002s |
| A-IQ3XXS | AD IQ3_XXS | 3.465 | 0.073686 | 88.529% | 21.24 | 952s |
| A-IQ3S | AD IQ3_S-IQ3_XXS | 3.732 | 0.048110 | 90.461% | 19.74 | 925s |

## Scorecard

| id | prediction | verdict |
|---|---|---|
| **P-L0** | gate: reference reproduces against itself | **CONFIRMED** -- mean KLD 0.000000, same-top 100.000% on all 40 chunks; also an exact reproduction of the EXL3 campaign's own `R2` gate, weeks apart |
| **P-L1** | KLD monotonic with bpw within a family | **CONFIRMED** -- GSQ 0.2022>0.1012; AD 0.1745>0.0737>0.0481 |
| **P-L2** | **THE FORK: B-PQ2 beats G-IQ2XS despite being smaller** | **FALSIFIED** -- 0.358047 vs 0.202243. Bonsai is **77% worse**, not better |
| **P-L3** | GSQ-RCO beats AD at comparable size | **CONFIRMED** size-normalised, 3 of 3; falsified on the naive label reading |
| **P-L4** | ternary drops same-top more than KLD implies (>=0.5 pp) | **CONFIRMED** -- +0.773 pp (B-PQ2), +0.764 pp (B-PTQ1) |
| **P-L5** | **CONTROL: both Bonsai containers must agree** | **CONFIRMED** -- 3.2e-5, against a 1e-4 threshold |
| **C-XBIN** | *(Amendment 1)* cross-binary comparison is valid | **PASS** -- 3.1e-5 |

**Five confirmed, one falsified.** The falsified one is the headline, and it was mine.

## P-L2: my own prediction, wrong by a factor of 1.8

P-L2 claimed Bonsai's rotated ternary basis would be **categorically** better -- lower KLD than
GSQ-RCO despite 1.13 GiB fewer scored bytes. Amendment 2 computed the bar: beat the scalar trend by
~40% at 2.119 bpw.

**Measured: B-PQ2 sits at 0.358047 against G-IQ2XS's 0.202243. Not 40% better -- 77% worse.**
Withdrawn. Ternary does not beat scalar codecs head-to-head at these sizes.

Amendment 2 also recorded, before the data, that I had come to *expect* this falsification while
leaving the prediction unchanged. That distinction is the whole point of writing predictions down.

## But Bonsai's codec is not worthless, and the panel says exactly how

At **1.748 scored bpw**, B-PTQ1 delivers 0.358015 where the scalar trend
(`KLD ~ exp(-1.41 x bpw)`) extrapolates to **0.5635** -- **36.5% better than the trend**.
Equivalently a scalar codec would need **2.071 bpw** to match it, so Bonsai reaches that fidelity
with **15.6% fewer bits**.

**Both statements are true at once:** Bonsai beats the *trend* at its own size, and loses badly to
an *actual* GSQ-RCO file 0.36 bpw larger. The trend comparison is an extrapolation below GSQ's
measured range; the head-to-head is not. When they disagree, the measurement wins, and P-L2 asked
the head-to-head question.

## P-L4, and the mechanism it suggests

At equal KLD, a scalar cell would sit at 2.071 bpw with **77.283%** same-top. B-PQ2 delivers
**76.510%** -- **0.773 pp lower**, past the preregistered 0.5 pp threshold. B-PTQ1 agrees at
+0.764 pp.

**The rotated ternary basis damages the argmax more than it damages the distribution.** That is a
candidate mechanism for the gap between how Bonsai 2 measures and how people report it behaving:
a codec scored on distribution distance looks better than the same codec experienced through
sampling, which consumes the top of the distribution. Three independent public reports of Bonsai 2
failing at agentic work are logged in `EXTERNAL_OBSERVATION_2026-09-19.md`, recorded before any
cell ran.

**Stated as a mechanism consistent with the evidence, not as a demonstrated cause.** KLD over
wikitext cannot measure agentic behaviour; that needs a task panel.

## P-L5 confirmed, and what it rules out

`|KLD(B-PTQ1) - KLD(B-PQ2)| = 3.2e-5`, against a 1e-4 threshold. Same-top differs by 0.010 pp.
**Both containers decode the same weights to the same distribution.**

Worth one nuance: 3.2e-5 is ~64x the within-binary reproducibility floor P-L0 established
(<5e-7), so the two are not *bit*-identical -- but at 0.009% relative on a 0.358 KLD, that is
consistent with benign ordering differences in the unpack path, not a defect.

**So the v1 -> v2 regression is NOT a container bug.** That moves the blame to the recipe, and
`ANALYSIS_BONSAI_V1_VS_V2.md` ranks what is left: the halved scale density (g64 -> g128) and the
Hadamard rotation's Gated Delta Net special case.

## The engineering finding nobody was looking for

**P-L5 plus the timings make PQ2_0 strictly dominant over PTQ1_0.**

| | B-PTQ1 | B-PQ2 |
|---|---:|---:|
| scored bpw | 1.748 | 2.119 (+21%) |
| mean KLD | 0.358015 | 0.358047 (**identical**) |
| s/pass | 51.30 | **14.58** |
| wall clock | 2180s | **747s (2.92x faster)** |

**PQ2_0 is the fastest cell in the entire panel** -- faster than every stock GGUF measured,
including a 24% margin over the same binary running IQ2_XS (14.58 vs 19.24 s/pass).

So the extra 0.371 bpw in the wider container buys **decode speed, not fidelity**. Dense base-3
trit packing (5 per byte) needs division and modulo by 3 to unpack; 2-bit slots need shifts and
masks. **Unless bytes are the binding constraint, PQ2_0 is the correct choice** -- 21% more space
for 2.92x the speed at literally identical output.

This also corrects an earlier claim in `FINDING_BONSAI_SPEED.md`: "Bonsai ternary is 2.67x slower"
is true only of **PTQ1_0**. PQ2_0 is *faster* than stock. Correction applied there.

## Method findings, which may outlast the codec verdicts

1. **Both scalar families decay at ~ln(4) per bit.** GSQ 1.4077, AD 1.4156, EXL3 ~1.4542 -- all
   within a few percent of ln(4) = 1.3863, the naive scalar-quantiser scaling. **Codecs compete on
   intercept, not slope.** A 30% codec advantage is worth about 0.25 bits; getting from 4 bits to 3
   needs a factor of 4. See `FINDING_DECAY_IS_LN4.md`.
2. **A "3-bit" quant is 3.5 real bits**, and the label spans 26%. Only GSQ-RCO's IQ3_XXS (2.968) is
   genuinely sub-3. See `FINDING_LABEL_VS_REAL_BPW.md`.
3. **GSQ-RCO is mid-tier.** Merged with the EXL3 campaign into one 18-point curve, the lower
   envelope belongs to EXL3 and unsloth alternating; GSQ-RCO never appears on it, and unsloth's
   UD-Q2_K_XL is smaller *and* 17% closer to the reference. See `FINDING_MERGED_CURVE.md`.
4. **Not all bytes are measured.** GSQ files spend ~4% on an MTP head perplexity ignores, AD ~3%,
   Bonsai none -- so raw file size is not a fair axis.

## Limits

- One model, one corpus (wikitext-2, 40 chunks, ~10,200 scored tokens), one metric family.
- Comparisons below 2.476 bpw extrapolate the scalar curves beyond measured data. Direction robust,
  exact values not. **A measured scalar cell near 2.0 bpw would close this and none exists.**
- **KLD is self-referential**: it measures distance from a model's own Q8_0, not whether that model
  is good. It cannot rank models, only codecs within one.
- **Fidelity is not usability.** Nothing here measures agentic behaviour, which is what the public
  reports are about. `PREDICTIONS_DERIVED_FROM_PL4.md` preregisters three follow-ups.

Raw: `logs/results.jsonl`, `logs/batch.log`, `logs/gate_pl0_run.log`. Harness: `scripts/`.
Scorer: `tools/score_ladder.py`. Chart: `merged_curve.png`.
