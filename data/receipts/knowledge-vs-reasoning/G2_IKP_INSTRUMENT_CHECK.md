# G-2 — does IKP discriminate on GLM-4.7-Flash? (base arm)

**Date:** 2026-08-06. **Verdict: PASS.** All four tiers carry headroom; T3 is the sweet spot.
**Not a result about GLM.** This gate only asks whether the instrument can measure anything on this
model. No pruned arm has been run.

## Environment (§9)

| field | value |
|---|---|
| model | `GLM-4.7-Flash-Q6_K.gguf`, 24,693,098,848 B |
| build | `~/tom_default/build/bin/llama-server`, `b100-0967f4997` |
| node | `.73`, 2 × Tesla P100-PCIE-16GB, **1063 MHz / 150 W** |
| server flags | `-c 4096 -ngl 99 -sm layer -np 1 --jinja -v` |
| VRAM | 12057 + 12231 MiB |
| client | `temp 0`, `max_tokens 64`, `concurrency 1`, `enable_thinking: false` |
| gate G-1a | `expert_gating_func = sigmoid` — asserted before inference, run would have aborted otherwise |
| probes | IKP T1–T4, **800**, `n_answered/n_total` reported below |
| wall clock | 432 s, 0 errors |

## Result

```
arm           tier      n  corr wrong refus ambig  noans      raw  answered  penalized
glm-base      T1      200   184    10     6     0      0   92.0%    92.0%      0.870
glm-base      T2      200   176    15     8     1      0   88.0%    88.0%      0.805
glm-base      T3      200    94    41    33    14     18   47.0%    51.6%      0.265
glm-base      T4      200    37    66    57    26     14   18.5%    19.9%     -0.145
glm-base      ALL     800   491   132   104    41     32   61.4%    63.9%      0.449
```

**Discrimination: good on every tier.** T1 at 92.0% is high but **not at ceiling** — 8 pp of room to
fall. T3 at 51.6% answered is close to ideal for detecting a change in either direction. T4 at 19.9%
is clearly above the floor, unlike T5–T7 which the upstream audit put at 10%/3%/4%.

Context, not a claim: the reference figures in `ikp_run.py`'s header for an unquantized 27B are
99.5 / 97.5 / 78.5 / 38. GLM-4.7-Flash sits well below that on every tier. Different model, different
training data, so this is **not** a controlled comparison — but it is consistent with an A3B-active
MoE holding less retrievable fact per token of compute than a dense 27B, which is the thesis this
campaign exists to test properly.

## ⚠️ Truncation is entirely one source type

32/800 probes (4.0%) hit `max_tokens=64`. `reasoning_chars` is `None` on **all 32**, so
`--no-think` worked and these are not reasoning chains. Broken down over T3+T4:

| `source_type` | truncated | rate |
|---|---|---|
| **researcher** | **32 / 86** | **37.2 %** |
| wikidata | 0 / 205 | 0.0 % |
| llm | 0 / 83 | 0.0 % |
| T3_final / T4_final / manual | 0 / 26 | 0.0 % |

Response length confirms the mechanism — median completion is short everywhere, but the tail is not:

| tier | median | p90 | max |
|---|---|---|---|
| T1 | 5 | 13 | 39 |
| T2 | 6 | 15 | 52 |
| T3 | 9 | **61** | 64 |
| T4 | 6 | **60** | 64 |

The researcher probes ask *"what is the research subfield of \<name\>"* and the model answers with a
formatted mini-essay — bold subfield names, affiliations, an associated paper — blowing past 64
tokens. Samples show answers that are arguably right but unmatchable by substring: gold
`computer networking` against *"**Computer Networks** and **Distributed Systems**"*.

**This is the same source the upstream audit flagged worst.** `ikp_run.py`'s header records that
T5–T7 were dropped partly because they draw 100% from researcher+wikidata, with **researcher at
24.9% of probes ambiguous or incorrect**. Those probes are also present in T3/T4, and they are
exactly the ones misbehaving here.

### Recommendation: exclude `source_type == "researcher"`, do not just raise `max_tokens`

Raising the budget lets them finish, but they then land in AMBIGUOUS rather than being scored — the
scorer routes responses over 25 words to the judge queue by design (T3 already has 14 ambiguous,
T4 has 26). So the probes still do not produce a verdict, and a quarter of them are audit-flagged as
bad gold anyway. Dropping them removes 86 of 400 T3+T4 probes, leaving 314, on the same reasoning
that removed T5–T7.

**Whichever is chosen, it must be fixed before the pruned arm runs and applied identically to both.**
Choosing after seeing the pruned arm's numbers would be selecting the filter that produces the
preferred answer.

### DECISION (locked 2026-08-06, before any pruned-arm inference)

**Exclude `source_type == "researcher"`.** Applied via `--exclude-source researcher` on both the
runner and the scorer, identically to every arm. Because raw responses are retained, the base arm was
re-scored rather than re-run.

The re-score validates the decision more strongly than the argument for it did:

```
arm           tier      n  corr wrong refus ambig  noans      raw  answered  penalized
glm-base      T1      200   184    10     6     0      0   92.0%    92.0%      0.870
glm-base      T2      200   176    15     8     1      0   88.0%    88.0%      0.805
glm-base      T3      165    94    39    31     1      0   57.0%    57.0%      0.333
glm-base      T4      149    36    66    47     0      0   24.2%    24.2%     -0.201
glm-base      ALL     714   490   130    92     2      0   68.6%    68.6%      0.504
```

| | all 800 | researcher excluded (714) |
|---|---|---|
| NO_ANSWER | 32 | **0** |
| AMBIGUOUS | 41 | **2** |
| T3 | 47.0 % raw / 51.6 % answered | **57.0 %** |
| T4 | 18.5 % / 19.9 % | **24.2 %** |

Those 86 probes produced **100% of the truncations and 39 of the 41 ambiguous verdicts**, while
contributing **one** correct answer between them — T3's correct count is unchanged at 94 and T4's
moves 37 → 36. They were not signal being discarded; they were probes that mostly never received a
verdict at all, on the source the upstream audit rates 24.9% ambiguous or incorrect.

`raw` now equals `answered` on every tier, and all four tiers retain headroom. T1/T2 are untouched —
the researcher source appears only in T3/T4.

The scorer reports the excluded count per arm and **warns loudly if the counts differ between arms**,
since unequal exclusion would mean the arms are no longer answering the same question set.

## Refusal base rates — needed before the comparison, not after

| tier | refusal rate |
|---|---|
| T1 | 3.0 % |
| T2 | 4.0 % |
| T3 | 16.5 % |
| T4 | **28.5 %** |

GLM declines heavily on obscure questions, which is well-calibrated behaviour and scores 0 raw
without penalty. It matters for Phase 1 because **pruning could convert refusals into
hallucinations** rather than reducing correct answers — capability loss showing up as degraded
calibration. That would leave `raw` nearly unchanged while `penalized` collapses. T4 is already at
**−0.145**, more wrong than correct. Report both metrics or that mechanism is invisible.

## Throughput note

Rate fell from 3.54 to 1.85 probes/s across the run. Benign and explained: probes run in tier order
and T3/T4 generate far longer responses (p90 61 tokens vs T1's 13). Not thermal — clocks held at
1063 MHz throughout.

Full arm cost is ~7 minutes, so a K=5 Phase 1 comparison is roughly an hour, not an overnight job.

## Status

- G-2 instrument discrimination — **PASS**
- G-3 positive verification — **PASS** (800/800 records written, count asserted by the runner)
- G-5 `no_answer` accounting — **working**, and it caught a real 4.0% truncation on the first run
- **OPEN decision:** researcher-source filter, to be fixed before the pruned arm
- **OPEN:** K, still pending the determinism answer
