# Protocol — Evaluating Reasoning Models Across Thinking Modes

**Status:** v1, 2026-07-25. Worked example: Laguna-S-2.1-UD-Q2_K_XL on HumanEval+ (complete, 984 samples).
**Problem it solves:** a reasoning model run in an off-spec harness produces **false negatives that look like
model or quant limitations**. Every such failure this lab has investigated turned out to be a harness artifact
until proven otherwise. This protocol makes the mode axis explicit and measurable instead of implicit.

---

## 0. The failure this exists to prevent

> A model scores badly. The score is attributed to the model (or its quant). The real cause was a harness
> setting the model was never meant to run under.

Instances observed in this lab:
- **Bit Laguna v1 "86%"** — an 8k-per-slot context guillotined coherent answers. Mirage.
- **My own "Q2 tax" headline** — both models run at temp 0 (greedy), a known loop-inducer, penalising the model
  designed for temp 0.7. Retracted; correct sampling was worth **+6.05 points** and cut truncations **5×**.
- **AgentWorld `__pycache__` probe** — a real blind spot, but the neighbouring `ls -la` "blind spot" was a
  2048-token truncation artifact of a 7,743-token response.

The through-line: **an unmeasured harness variable becomes a model claim.**

---

## 1. Mandatory reporting: three metrics, never one

A single number cannot describe a model that has modes. Report all three, always labelled:

| Metric | Definition | What it answers |
|---|---|---|
| **Per-mode pass@1** | pooled `passing_samples / (N*K)`, per mode | *What do I actually get if I deploy in this mode?* (the honest headline) |
| **Best-of-modes envelope** | solved by ≥1 sample in **any** mode | *Capability ceiling if each problem were routed to its best mode* |
| **Recovery matrix** | per problem × mode → bucket | *Which failures were mode artifacts vs genuine misses?* |

**The envelope is not a deployment number and must never be quoted as one.** In the worked example the
envelope is **97.0%** against a best per-mode pass@1 of **90.85%** — a 6-point gap that exists only because
it is effectively pass@6 across mixed modes. Quoting it as "the model scores 97%" would be benchmaxxing.

---

## 2. Required controls

1. **K ≥ 3 at any temp > 0.** One pass at temp>0 is a single draw from a distribution. K=3 minimum, 5 preferred.
   Report per-sweep **mean ± std** alongside pooled, plus the **flaky count** (problems solved sometimes).
2. **Control for flakiness before crediting a cross-mode recovery.** A failure may be a bad sample, not a mode
   fault. `pass_frac` from K≥3 supplies this. Never attribute a recovery without it.
3. **Re-test only the failing task_ids in other modes** (`HEP_ONLY`). Cheap: you re-run the misses, not all 164.
4. **Selected subsets regress to the mean.** If you re-run "the problems that wedged", they will wedge less
   *with no intervention at all*. Any such re-run needs a **no-treatment control arm in the same session**.
5. **Discover modes from the chat template, do not hardcode.** Grep the served template for `default(...)`
   booleans. Laguna's `laguna_glm_thinking_v8` exposes `enable_thinking` (default **true**) and
   `preserve_thinking` (default **false**).
6. **Do not pad the matrix with inert modes.** `preserve_thinking` governs retention of *prior-turn* thinking;
   on a single-turn benchmark there is no prior thinking, so it is inert. Verify before counting a mode.
7. **Record hardware state with every receipt.** GPU clock/power changes benchmark numbers. All runs below:
   **P100 @ 1063 MHz SM / 715 MEM / 150 W cap / persistence on.** After a reboot, clocks come up at
   boot defaults (1189 MHz / 250 W) until the efficiency unit applies — **verify before launching.**
8. **Preflight the mode switch itself.** Prove `enable_thinking:false` actually empties `reasoning_content`
   before committing hours to a run, or you risk labelling thinking-ON data as thinking-OFF.

---

## 3. Harness requirements

- **Extract from `content`, then fall back to `reasoning_content`.** Code stranded in a think block is a
  harness miss, not a model miss. Record which source was used (`src`) — it is itself a measurement.
- **Always set a token cap.** This is not merely a safety limit: **a cap converts an unbounded hang into a
  countable data point.** Uncapped, the same failure is a process that never returns (observed externally:
  a 30-turn agent probe wedged ~91 min). Capped, it is a `TRUNCATED` bucket you can put in a table.
- **Bucket explicitly:** `PASS / WRONG / TRUNCATED / NO_ANSWER / EXEC_TIMEOUT`. Collapsing TRUNCATED into
  WRONG destroys the only signal that distinguishes a harness artifact from a capability miss.
- **Single in-flight request** (`-np 1`, one worker) to avoid batch nondeterminism confounds.
- **Log the full sampling config in the results JSON** — temp, top_p, top_k, min_p, mode flags, K.

---

## 4. Sampling config: use the model's own declaration

"Creator-recommended" must come from an authoritative source, in this order:
1. **GGUF embedded metadata** (`/props` → `default_generation_settings`) — what the file itself declares.
2. `generation_config.json` shipped with the weights.
3. The model card prose.

Prose and metadata disagree in practice. Puzzle-75B's results doc contained **both** "card wants temp 1.0"
and "temp 0.6 (card's rec)". The GGUF metadata settled it: **temp 1.0, top_p 0.95, top_k 40, min_p 0.05.**
Running 0.6 would have been an arbitrary temperature presented as a deployment test.

**`min_p` is part of some recommendations and is easy to silently omit.** If the harness cannot send it,
the run is not the card's config.

---

## 5. Worked example — Laguna-S-2.1-UD-Q2_K_XL, HumanEval+ (N=164, K=3, 984 samples)

Both arms: same weights, same server (`-c 32768 -np 1 -fa on -sm layer -ts 1,1,1,1`), same clocks.

| | thinking **ON** (t0.7/0.95/20) | thinking **OFF** (t0.6/0.95/20) |
|---|---|---|
| pass@1 pooled | **90.85%** (447/492) | 88.21% (434/492) |
| per-sweep | 90.85% ± **0.50%** | 88.21% ± **1.52%** |
| TRUNCATED | 10 | **0** |
| always-solved | **143**/164 | 131/164 |
| flaky | **11**/164 | 24/164 |
| total tokens | 1,457,555 | **173,957** |
| wall clock | 20.1 h | **2.5 h** |

**Recovery matrix:** both 123 · neither 5 · ON-only 20 · OFF-only 8.
**Of the 7 problems that truncated with thinking ON, 5 improved with it off** — `/116` went `T,T,W` → `P,P,P`.
Those were **wedges, not capability misses**. The remaining 2 (`/132`, `/145`) failed in both arms: genuine.

**Findings:**
1. Thinking buys **+2.64 points** for **8.4× the tokens** and **8× the wall clock**. That is the deployment trade.
2. Thinking **eliminates nothing and stabilises much**: it is *more* consistent (±0.50 vs ±1.52; 11 vs 24 flaky)
   **despite running at the higher temperature**. Temperature works against this result, so it is a real
   thinking effect, not a sampling artifact.
3. Turning thinking off removes **100%** of wedges but costs accuracy. It is the sledgehammer, not the scalpel.

**Scope limit:** HumanEval+ is single-turn and heavily contaminated (2021, in every training set). External
work reports thinking as *net-negative* on **held-out, multi-turn agentic** work for this same model. These are
different axes and must not be merged into one claim. A defensible hypothesis worth testing properly: *if
thinking helps on contaminated benchmarks but hurts on held-out work, it may be functioning as retrieval
scaffolding rather than novel reasoning.*

---

## 6. Cautionary tale — how to talk yourself into an intervention

Attempting to design a targeted `logit_bias` intervention, this lab computed marker densities
(`wait`/`but`/`alternatively`) **pooled per 1k words within each bucket** and produced a confident ranking:
`wait` 2.57× concentrated in wedged traces, `alternatively` "not discriminative".

**All of it was an artifact.** Two defects:
1. **The denominator was the confound.** Wedged traces are *by definition* the ones that ran to the cap.
   Markers that accumulate *during* a spiral look identical to markers that *cause* one. The metric ranked
   length-coupling, not causation.
2. **One outlier drove the result.** Per-trace `wait` density was `6.02, 13.45, **134.65**, 6.72, 9.55`.
   Strip `/44` and four of five wedged traces sit *below* the non-wedged pooled average.

Re-run **prefix-matched** (first 2,000 words only, before any spiral): `wait` fell 2.57× → **1.43×**, and
`but` — the marker slated for exclusion — became the **strongest** discriminator (1.77×). Distributions
overlapped almost completely.

**Rules adopted:**
- **Never rank on pooled statistics without per-unit variance.** Report per-trace values.
- **Prefix-match before comparing anything against a runaway-length bucket.**
- **Positional test:** a marker is only predictive if elevated *early*, before the pathology develops.
- Trace samples are small by construction (one representative failing trace per problem → n=5 here).
  **Treat single-digit n as hypothesis-generating only.**

---

## 7. Open arm

`logit_bias` on overthinking markers is the untested middle of the intervention spectrum:

| Intervention | Cost | Tokens saved | Truncation | Accuracy |
|---|---|---|---|---|
| baseline (thinking ON) | — | — | 2.03% | 90.85% |
| thinking OFF (measured) | free, instant | 88% | **0%** | −2.64 pts |
| `logit_bias` markers | free, instant | **?** | **?** | **?** |
| finetune (external: ThinkingCap) | retraining | 46–58% | 2.9%→0.4% | −0.8 pts |

Design requirements carried from §2: use the **published** marker list (our own is not supported by the data),
**`-5` not `-100`** (a hard ban made the model route around it — `wait`→`what`, testing something else), bias
**all casing/spacing variants** (`wait`/` wait`/`Wait`/` Wait` are four distinct token IDs), and include a
**no-bias control on the same subset in the same session**.
