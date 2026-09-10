# REAM-60Pct: knowledge intact, answer-termination gone — 1/5 vs control 5/5

**2026-09-02.** `.194`, 4x P100 sm_60 @ 150 W. `mradermacher/Qwen3.8-Flash-Next-REAM-60Pct-i1-GGUF`
@ i1-Q2_K (expert_count **308** of 512, expert_used_count 10 unchanged) versus the unpruned
`Qwen3.8-Flash-Next-UD-Q2_K_XL` control. Identical flags, prompts, sampling, same session.

Required a metadata repair to load at all — see `RESULT_REAM60_METADATA_BUG.md`.

## Sampling — corrected mid-experiment

The first pass used `temperature=0`, which is **contraindicated** for this family. Unsloth
specifies thinking mode as `temperature=1.0, top_p=0.95, top_k=20, min_p=0.0,
presence_penalty=0.0, repetition_penalty=1.0`. Greedy decoding on a reasoning model can lock into
a high-probability groove and never sample the token that closes `</think>`, which would make a
zero-output result a **sampling artifact rather than pruning damage**.

Mark caught this. Everything below is at the recommended parameters, `max_tokens=4096`.
(For the record, temp-0 gave pruned **0/5** — the correction moved it to 1/5, so the objection was
real but not sufficient.)

## Result

| prompt | pruned | control |
|---|---|---|
| factual | `length` 4096 tok, **0 content**, 19,298 chars reasoning | `stop` 221 tok, 388 content |
| arithmetic | `length` 4096, **0 content**, 14,221 reasoning | `stop` 465, 1,019 content |
| logic puzzle | `length` 4096, **0 content**, 18,320 reasoning | `stop` 664, 566 content |
| format (3 bullets) | `length` 4096, **0 content**, 21,939 reasoning | `stop` 248, 373 content |
| no-repeat | **`stop` 762, 354 content** ✅ | `stop` 289, 931 content |

**Pruned 1/5. Control 5/5.** The control completes in 221–664 tokens; the pruned model exhausts
4096 and stops only at the ceiling.

## Mechanism: a question-restatement loop in the reasoning channel

3,171 words of "reasoning" on *what is the capital of France*:

```
x20   "and name two events that made it historically"
x19   "capital of France and name two events that"
x16   "of France and name two events that made"
```

It re-reads the prompt, emits a fragment (*"French Revolution"*, *"Battle of Paris"*), restarts.
At the token cap it is still restating the question.

**Knowledge and expression are intact.** The one completed answer is correct and well-formed:
*"quantizing changes exact numeric values into discrete levels, and that rounding changes the
model's output... errors introduced are not evenly distributed across levels."*

So pruning 512 -> 308 experts did not remove what the model knows. It removed whatever governs
**stop analysing, start answering** — and the failure presents as degenerate repetition *inside
the thinking block*, where a grader that inspects `content` sees only an empty string.

## Prediction scoring

| # | claim | conf | outcome |
|---|---|---|---|
| P1 | grammatical text | 0.90 | partial — grammatical but looping |
| P2 | correct factual recall | 0.80 | ❌ |
| P3 | survives multi-step | 0.55 | ❌ |
| **P4** | **no degenerate repetition** | **0.70** | **❌ — 20x repeated 8-gram** |
| P5 | worse than control | 0.75 | ✅ 1/5 vs 5/5 |
| P6 | worth the 16.8 GiB saving | 0.40 | ❌ |

**P4 is the instructive miss.** I checked `content` for repetition, found it empty, and reported
"no degenerate repetition, reasoning is coherent." The degeneracy was in `reasoning_content`
throughout. Same defect that nearly misfiled the archaeology arm as `EMPTY` this morning — and I
had already fixed the automated grader for exactly this, then eyeballed it manually anyway.

**Rule, again: scan every text-bearing field. An empty `content` is a finding, not an absence.**

## Limits

- One quant (i1-Q2_K), 5 prompts, K=1. No KLD, no perplexity.
- mradermacher's recipe differs from Unsloth's UD: `ffn_down_exps` is 12.69 GiB here vs 21.09 in
  the control, so this is **pruning plus a harder quant on that group**. The two causes are not
  separated by this test. A REAM build at a matched recipe would be needed to attribute cleanly.
- Says nothing about REAP/REAM in general, or about the 288/384-expert variants.

## Practical

The residency prize that motivated this — experts 42.9 -> 27.5 GiB, potentially fitting two P100s
with no MoE offload — is not collectable from this artifact. It does not answer.
