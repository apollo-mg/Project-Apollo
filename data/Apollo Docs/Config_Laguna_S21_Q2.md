# Laguna-S-2.1 (Q2_K_XL) — evidence-graded serving config

**Status:** working document, 2026-07-26. Every line is tagged **[MEASURED]**, **[INFERRED]**,
or **[UNKNOWN]**. Nothing here is a guess presented as a setting.

Underlying receipts:
- `data/receipts/humaneval-plus/` — 492-sample thinking ON/OFF A/B, full 164, K=3
- `data/receipts/thinking-suppression-2x2/` — persona × tools factorial
- Prior temp-0 leg (loop stratification by compression ratio) — see
  `puzzle-humanevalplus-run-2026-07-23` memory

Hardware for all of it: `.194` quad Tesla P100 (sm_60), 1063 MHz / 150 W, poolside llama.cpp
build, `-c 32768 -np 1 -ngl 99 -sm layer -ts 1,1,1,1 -fit off`.

---

## 1. Thinking: leave it ON — **[MEASURED]**

| | thinking ON (t0.7) | thinking OFF (t0.6) |
|---|---|---|
| pass@1 (492 samples) | **90.85 %** | 88.21 % |
| flaky problems | **11 / 164** | 24 / 164 |
| solved 3/3 | **143 / 164** | 131 / 164 |
| no extractable answer | 11 | 0 |
| median output tokens | 1 945 | 274 |

Thinking buys **+2.64 points** and — the less obvious half — **halves sampling sensitivity**,
despite running at a *higher* temperature. Turning it off doesn't just cost accuracy, it makes
the model less reproducible run to run.

The cost is real: **8.4× the tokens and 8× the wall clock.** Turn it off only when latency
matters more than correctness, and know you are buying that latency with 2.6 points and double
the flakiness.

## 2. Token budget: ~12 k, and treat cap-hits as failures — **[MEASURED + INFERRED]**

**[MEASURED]** Output token distribution with thinking on: median 1 945, p95 **10 152**,
12 samples pinned at the 16 000 cap.

**[INFERRED]** A budget near **12 k** covers p95 with headroom. Going to 16 k does not buy
correctness: the prior temp-0 leg established by compression ratio that most cap-hitters are
**degeneration loops** (`gzip ratio < 0.08`), not legitimate long reasoning
(observed non-looper range **0.33–0.75**, per the three-stack table in §3).
A loop consumes whatever budget it is given.

> **Consistency fix 2026-07-27:** this line previously gave the healthy boundary as
> `> 0.12`, contradicting the `0.33–0.75` in §3 — same threshold, two numbers, one file.
> Same class of error @Blackwellboy hit when a retracted claim survived as a restatement
> four lines below its own retraction. Adopting his rule: **when correcting a claim, grep
> the whole file for restatements, not just the sentence you flagged.**

**Correction (2026-07-26): "cap-hit = failure" was too strong.** Of the 12 cap-hit samples in
the t0.7 run, **2 were PASSES** — `HumanEval/47` hit the 16 k ceiling twice and produced
extractable, correct code both times. The model finished its answer and then kept generating
until the cap. So `finish_reason=length` is **not** by itself a failure signal; what matters is
whether code was extractable.

The narrower, defensible claim: **a cap-hit that yields no extractable code should not be
assumed recoverable with a bigger budget.** Even that is now contested — see §3a.

| cap-hit sample | bucket | problem pass_frac |
|---|---|---|
| HumanEval/47 ×2 | **PASS** | 1.00 |
| HumanEval/44, /90 | TRUNCATED | 0.67 |
| HumanEval/118 ×2 | TRUNCATED | 0.33 |
| HumanEval/76, /116 ×2, /132, /145 ×2 | TRUNCATED | **0.00** |

**6 of the 10 truncations sit on problems the model never solves in any sample.** That is
consistent with "budget won't help" but does not demonstrate it — a problem that is never
solved is also never solved *with* more budget, so the two hypotheses make the same prediction
there. The 4 truncations on *solvable* problems (`/44`, `/90`, `/118` ×2) are where the two
hypotheses actually differ, and that is the population the §3a test must target.

## 3a. Is the wedging degeneration, or plain truncation? — **[OPEN, contested]**

@Blackwellboy reports that on **Qwen** the identical symptom was **pure truncation**: raising
the budget converted **8 of 10** empty responses to valid answers at 8192, with **zero
degeneration in any tail**. Different model, but it establishes that the symptom has more than
one cause and must be checked per-model rather than assumed.

Our "degeneration loop" reading rests on compression-ratio stratification from the earlier
temp-0 K=1 leg, and an attempt to validate that threshold on a second model **failed to test
it** (that model never wedged, so there were no positives). It is `[INFERRED]`, not measured.

**ANSWERED 2026-07-26 — and by a third option neither side proposed.** @TheTom ran the budget
test on Q4_K_M (see §3): loops are **stochastic per sample**, not deterministic per problem.
Budget is not the fix, but degeneration is real. Both original hypotheses were wrong.

`HumanEval/47` is the case that proves it, now observed three ways:

| stack | draw | outcome |
|---|---|---|
| ours, Q2_K_XL / 16 k | capped ×2 | **passed both**, extractable code |
| @TheTom, Q4_K_M / 12 k | first draw | **zero code**, uniq-line ratio 0.185 |
| @TheTom, Q4_K_M / 32 k | retry draw | **passed**, 3,767 tokens, ratio 0.600 |

Same problem, three characters. Our `/47` counter-example and his `/47` looper were never in
conflict — they were two draws from a stochastic process, which is why per-model *and*
per-sample checking is required and why no single run settles it.

**Our own 48 k re-run is therefore no longer decisive** and has been dropped from the queue.
What would still be worth running here is the *retry* rule rather than the *budget* rule:
re-draw our 10 no-code truncations at identical settings and count recoveries.

## 3. An external stopping rule is the highest-value change — **[INFERRED, strongly]**

**[MEASURED]** 11 / 492 samples (2.2 %) produced no extractable code at all. Against
Puzzle-75B, the WRONG counts are near-identical (30 vs 28) — **the entire 3-point gap is
termination failure, not answering failure.**

**[INFERRED]** Laguna allocates reasoning budget rationally by difficulty (1 749 median tokens
on problems it always solves, 8 121 on problems it never solves) but has **no stopping rule**
for problems beyond its capability. It does not fail to reason; it fails to give up.

**Recommended harness behaviour — revised 2026-07-26 after @TheTom's cap-retry:**
detect degeneration mid-stream by repetition signature, abort, and **re-draw at the same
settings**. Do *not* raise the budget, and do not disable thinking as the first fallback.

**Why the revision — loops are stochastic per sample, not deterministic per problem.**
@TheTom re-issued 4 cap-hitters at 32,768 (2.7× the original ceiling). Three "converted" —
but finished at **2,153 / 3,767 / 6,985 tokens**, all *well under* the 12,288 ceiling they
had previously exhausted. **More budget cannot be what fixed them; they simply did not loop
on the new draw.** The fourth (`/145`) consumed all 32,768, returned zero code, at a
unique-line ratio of 0.086 — the lowest in his entire population.

Consequences:
- **"More budget converts cap-hitters into passes" is refuted.** The conversions did not use
  the extra budget.
- **"Cap-hitters are degeneration loops" is supported**, with `/145` as the clean case.
- **Retry-on-signature beats raise-the-budget on cost**: 2–7 k tokens per recovery versus
  32,768 spent before giving up.

**What loop recovery is actually worth: +1.2 points, and it does not change the verdict.**
Re-scoring his ON arm with the retried samples substituted: HumanEval+ 88.4 → **89.6**,
still behind OFF's 90.9. @Blackwellboy reached the same conclusion on NVFP4 by a different
route (detection rather than resampling): recovery brings ON to parity, not ahead.

**The detector signal is now three-stack convergent** — three different metrics, three
stacks, same separation:

| stack | metric | loopers | non-loopers |
|---|---|---|---|
| ours (Q2, gzip compressed/raw) | compression ratio | < 0.08 | 0.33–0.75 |
| @Blackwellboy (NVFP4, raw/compressed) | tail compression | 44–143× | 2.5–3× |
| @TheTom (Q4_K_M) | unique-line ratio | 0.086–0.32 | 0.50–0.61 |

That is enough to promote loop detection from `[INFERRED]` to a supported mechanism. What
remains unbuilt is the **online** version: all three measurements score completed traces,
and a deployable detector must score a sliding window mid-stream.

## 4. Do not use persona + tools as a thinking control — **[MEASURED]**

| system prompt | tools | thinking fired | median reasoning vs baseline |
|---|---|---|---|
| default | no | 15/15 | — |
| persona | no | 15/15 | 1.09× (no effect) |
| default | **yes** | 15/15 | 0.92× |
| **persona** | **yes** | **13/15** | **0.39×** |

Neither variable alone does anything. **Together they cut reasoning ~2.5×** — super-additive
(independent composition would predict ~1.00×), robust on 14 of 15 problems, and *not*
outlier-driven.

**This is the single most important harness fact about this model**, because it fires by
accident: every real agent pipeline has both a system persona and tool schemas. A team can
lose 60 % of the model's reasoning without changing a single sampling parameter, then conclude
the model "doesn't think."

If you want less thinking, set `enable_thinking: false` — explicit, and its cost is quantified
in §1. Do not achieve it as a side effect of your system prompt.

**Corollary that contradicts the public read:** "coding-shaped tasks" are **not** a suppressor.
Our baseline cell is maximally coding-shaped and produces the *most* reasoning of any condition.

## 5. Sampling — **[UNKNOWN]**

We have run Laguna at exactly two sampling points, both card-recommended:
`t0.7 / top_p 0.95 / top_k 20` (thinking on) and `t0.6` (thinking off).

**No sweep has been run.** No temperature curve, no top_p / top_k / min_p variation, no
`presence_penalty` arm. Any "optimal sampling for Laguna" claim sourced to this work is
fabricated. The card-recommended values are the current default because they are the
card's, not because we validated them.

## 6. Server flags — **[PARTIALLY UNKNOWN]**

`-fa on/off` was never tested on Laguna, and the two eval legs' exact server flags were not
recorded (they predate the launcher script). The config at the top of this document is the
*current* known-good launch, not a validated optimum.

---

## Scope — what this config is NOT based on

- **One benchmark.** HumanEval+ is single-turn code generation. Laguna's contested behaviour
  appears in **long agentic sessions** (100+ tool calls, hour-long runs) — a regime we have
  not touched at all.
- **One quant.** Q2_K_XL. The 2-bit tax is entangled with everything above.
- **Tools were passed but never called back.** No tool output re-entered the context. Real
  agent loops feed results back every turn; that is an untested and plausibly stronger variable
  than mere tool-schema presence.
- The 2×2 is **K=1 over 15 problems** — it sizes an effect, it does not establish a rate.

## Open questions, ranked by value

1. **Does a compression-ratio stopping rule recover the 2.2 %?** Transfers to every model with
   this failure mode, not just Laguna. Cheap on the 15-problem subset.
2. **Does tool-result feedback suppress more than tool-schema presence?** Closest thing to the
   real agent regime.
3. **Which half of the persona drives the interaction** — identity claim, or the quality demand
   ("clean, correct, production-quality")? Now worth splitting, because there is finally a real
   effect to attribute.
4. Sampling sweep. Lowest value of the four: it is the axis everyone already argues about, and
   the harness axis is where the points actually are.
