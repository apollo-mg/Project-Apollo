# Error structure of the 25%-pruned arm — and what it does/doesn't say about healing

**Date:** 2026-08-07. Post-hoc analysis of runs already in hand (`ikp_glm_base_rep2` vs
`ikp_glm_reap_rep1`, researcher-excluded, n=714). **No new inference.** Exploratory throughout —
nothing here was pre-registered, and the classifications are string-level heuristics, not judgments
about the model's internals.

## Motivation

h4rm0n1c (Discord, 2026-08-07) proposed that post-REAP errors "land near the right answer" the way
TurboQuant's quantization error does, and that a healing pass over general knowledge could pull them
back. That is a claim about **weight space**. Everything below measures **token space**. The gap
between those two is the main finding, and §4 names the experiment that closes it.

## 1. Verdict transitions

Of the **486** probes the base arm answered correctly:

| becomes, in the pruned arm | n | share |
|---|---|---|
| still CORRECT | 122 | 25 % |
| REFUSAL ("I don't know") | 260 | **54 %** |
| confidently WRONG | 98 | 20 % |
| AMBIGUOUS | 6 | 1 % |

Movement is not one-way: 94 WRONG→REFUSAL and 8 REFUSAL→WRONG. But the dominant transition is
**withdrawal, not fabrication** — the pruned model mostly stops answering things it knew rather than
inventing answers for them. That is well-calibrated behaviour and it is the reason the refusal rate
rose 12.7 % → 61.3 %.

## 2. Grader-artifact symmetry check (this one was blocking)

The pruned arm sometimes clips to surnames — `"Johannes Kepler."` → `"Kepler."` — which the
deterministic grader books WRONG because the gold carries the forename. **If that terseness shift
were arm-asymmetric, part of the committed −36.8 pp would be a style artifact, not knowledge.**
Same failure class as the thinking-mode confound and the numpy fail-green. We had applied
symmetry checks to truncation (G-5) and to source exclusion, never to grader-artifact rate.

Upper bound — WRONG verdicts whose response contains ≥1 content token of the gold (over-inclusive;
it also catches genuine near-misses like `Lake Huron`→`Lake Michigan`):

| arm | WRONG | partial-hit | rate |
|---|---|---|---|
| base | 130 | 17 | 13.1 % |
| pruned | 135 | 23 | 17.0 % |

Hand-classifying those into *answers a human would mark correct* vs *genuinely wrong*:

- **base ≈ 5** — `Al Neuharth`/Allen Neuharth, `Glinka`, `Pyotr Ilyich Tchaikovsky`, `Saimaa`,
  `Mount Cook (Aoraki)`
- **pruned ≈ 5** — `Faraday`, `Kepler`, `Dalton`, `Pauli …`, `Warszawa`

**The artifact rate is symmetric.** The base arm clips to surnames at the same rate. Even at the
over-inclusive upper bound the differential is 17 vs 23 probes out of 714 — 0.8 pp against a
−36.8 pp effect. **The headline in `RESULT_differential_knowledge_vs_code.md` stands unmodified.**

## 3. Do the confident errors retain any of the right answer?

Regrading the 5 artifacts out leaves **93 genuine** CORRECT→WRONG errors.

| | n | share |
|---|---|---|
| retains a content token or word-prefix of the gold | 16 | 17 % |
| **shares nothing with the gold** | **77** | **83 %** |

The 17 % is real and visually striking — the generation starts on the correct sequence and decays:

```
Tim Berners-Lee        -> "Tim Berners."
Gabriel García Márquez -> "Gabriel Garci."
Antoine Lavoisier      -> "Antoine-Lavois"                       (mid-word)
Mekong                 -> "The Mek River"                        (mid-word)
Igor Stravinsky        -> "Igor and Jean-Poltzer."               (correct forename, then noise)
William Harvey         -> "William Edward A. H. (William Edward A. H.)"   (correct forename, then loop)
Rudolf Mössbauer       -> "**Hansö Bauer**"                      (fragment of the surname)
```

The other 83 % show no trace of it: `Ottawa`→`Toronto`, `Emily Brontë`→`Joseph Almasay`,
`Bach`→`Nicolas Rougé`, `Copernicus`→`Johannes Johannes`, `Röntgen`→`the German physicist **X**
(the letter X)`.

**At the level of emitted strings, most of the lost knowledge leaves no residue.**

## 4. Why §3 does not answer the question, and what would

Token overlap is a proxy for output, not for representation. **The argmax can flip completely while
the underlying distribution still carries the fact** — if `Ottawa` sits at rank 3 behind `Toronto`,
the information is present and merely mis-sharpened. So **83 % is an upper bound on "the fact is
gone," not a measurement of it.**

The 54 % refusal bucket points the same way and is the stronger hint. A model that refuses has an
elevated internal uncertainty estimate, which is what a *flattened but correctly-centred*
distribution looks like. Wholesale deletion would more plausibly yield confident garbage. **The
largest bucket is the one most likely to retain signal**, and §3 never looked at it.

### Proposed leg — teacher-forced gold rank (pre-registration)

Condition the pruned model on the identical prefix, teacher-force the gold continuation, read back
per-token logprobs. Run it on the 77 "shares nothing" cases **and** on a sample of the 260 refusals.

> **P-HEAL1** — on the 77 confident-error cases, the gold's first content token is within the top 10
> for **≥ 50 %** of cases. *Confidence 0.35.*
>
> **P-HEAL2** — on a 60-probe sample of the CORRECT→REFUSAL cases, the same measure clears the same
> bar. *Confidence 0.60* — refusal is predicted to be the recoverable bucket.

Design note: first-token rank is sufficient for single-token golds (`Ottawa`/`Toronto`) but
**not** for multi-token names (`Wilhelm Röntgen`) — those must be teacher-forced across the full
continuation or the test reads falsely negative.

Interpretation, fixed in advance:

- **Gold stays high-rank** → information present, argmax displaced. Healing is *re-sharpening*:
  cheap, plausibly LoRA-scale, and h4rm0n1c's analogy to quantization error holds.
- **Gold at rank 10³⁺** → information absent. Healing is *re-learning*, at training cost, and
  requires the facts to be in the healing corpus — which is a different and much more expensive
  proposition than "a healing pass."

## 5. Limits

- One arm-pair, one prune ratio, one replicate per arm (rep2 base / rep1 pruned). Verdict transitions
  will move somewhat across the K=5 replicates; the 17 known verdict flips (`DETERMINISM_TEMP0_GLM_P100.md`)
  are concentrated in T4 and do not touch the T1 examples quoted here, but the transition *counts*
  in §1 carry that noise and are not exact.
- §3's classifier is a string heuristic. It cannot see semantic adjacency (`Dalí`→`Picasso` scores
  "shares nothing" and is obviously a near miss in concept space), so it **understates** residual
  signal by construction. Another reason 83 % is an upper bound.
- Post-hoc and unregistered. The examples were read before the categories were written, so the
  category boundaries are contaminated by the data. §4 exists because of this.
- Says nothing about whether healing *works* — only about which mechanism it would have to be.
