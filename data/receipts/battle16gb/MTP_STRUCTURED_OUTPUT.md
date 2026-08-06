# Where MTP's nondeterminism lands: prose drifts, tool calls hold, code breaks

RX 9070 XT 16 GB, `llama_cpp_turboquant` (TheTom), `Qwen3.6-35B-A3B-UD-IQ2_M`.
Arms differ **only** by `--spec-type draft-mtp --spec-draft-n-max 2`. `temperature 0`,
`cache_prompt:false`, `-np 1`, f16 KV, `-c 65536`. Date 2026-07-29.
Companion to `MTP_DETERMINISM.md`, which established MTP is nondeterministic at temp 0.

## The question

Mark, on seeing MTP flip "Key **Aspects** to Cover" → "Key **Areas** to Cover":

> *"replacing synonymous words in natural language is inherently innocent, not so in tool
> calls and coding."*

If the flips come from float-reduction reordering under batched verification, they can only
move positions where the argmax margin is tiny. Prose synonym slots are exactly that. The
open question is whether structured output — where a single token changes *meaning* — is
protected by its own low entropy, or merely luckier.

## Result

| class | base | MTP | |
|---|---|---|---|
| prose (free explanation) | **1 variant / 6** | **3 variants / 6** | unstable, as expected |
| tool call, args given | 1 / 6 | **1 / 6** | **stable** |
| tool call, args **computed** | 1 / 6 | **1 / 6** | **stable, and correct 6/6 both arms** |
| **code** | **1 / 6, correct** | **1 / 6, raises ValueError** | **stable within arm, differs across arms** |

**Each arm is internally stable on structured output. The arms disagree on code, and the
disagreement is semantic.**

## The mechanism, quantified: acceptance tracks entropy

Draft acceptance rate by output type, same model and settings:

| prompt type | draft acceptance |
|---|---|
| prose | **0.620** |
| mixed reasoning + structured | 0.781 |
| tool call | **0.857** |
| code (thinking disabled) | **0.864** |

Acceptance rises as output becomes more constrained. High acceptance and stability are two
readings of one property — **low next-token entropy**. Where the model is confident, the
draft head predicts correctly *and* there is no near-tie for reduction-order noise to flip.
Prose synonym slots are where both conditions fail at once.

Supporting detail: the tool-call acceptance figure was byte-identical across draws
(`0.85691`, 533 accepted / 622 generated, three times), so the accept/reject *pattern* is
stable, not just the final string.

## Where Mark's concern is confirmed: the `T` separator

Task: `parse_iso8601_duration(s)`, e.g. `'P3DT4H5M6S'` → seconds. Both arms stable across
6 draws (2 instances × 3), both `finish_reason: stop`, code taken from `content`.

```python
base  pattern = r'^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$'
mtp   pattern = r'^P(?:(?:(\d+)D)?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)$'
```

**MTP dropped the `T` separator.** Everything else differs only cosmetically (comment
wording, `match.groups()` unpacking vs four `match.group(n)` calls). Executable result:

| case | base | MTP |
|---|---|---|
| `P3DT4H5M6S` (the example in the prompt) | 273906 | **ValueError** |
| `PT30S` | 30 | **ValueError** |
| `PT2H` | 7200 | **ValueError** |
| `P1D` | 86400 | 86400 |

**base 6/6 correct on all four cases; MTP 6/6 failing three of four**, including the string
from its own docstring. In prose a synonym swap costs nothing. In a regex, one dropped
character is the difference between a working function and one that throws on its primary
input. That is the distinction Mark drew, reproduced on hardware.

## Direction test: 6 tasks, executable ground truth — the ISO case is the exception

`mtp_code_multi.sh`, 6 independent tasks × 2 instances × 2 draws per arm, each scored by
running the function against hand-written cases.

| task | base | MTP | code |
|---|---|---|---|
| iso (ISO-8601 duration) | **4/4 correct** | **0/4 — raises** | differs |
| semver | 4/4 | 4/4 | **identical** |
| csvq (quoted CSV) | 4/4 | 4/4 | **identical** |
| ipv4 | 4/4 | 4/4 | differs |
| roman | 4/4 | 4/4 | **identical** |
| pathnorm | 4/4 | 4/4 | differs |
| **total** | **24/24** | **20/24** | 3 identical / 3 differ |

Every arm was internally stable (1 variant per 4 draws, all 12 cells).

**"MTP degrades code" is NOT supported.** The entire 24-vs-20 gap is the single ISO task; on
the other five MTP is 20/20. Of the three tasks where the arms produced different code, MTP
was worse on **1** and equal on **2** — never better, but n=3 differing tasks cannot
establish a direction. The script's own auto-verdict ("suggests MTP degrades code quality")
overreads its evidence and is recorded here as wrong.

**What IS supported, and matters more for practice:**

1. **MTP changed the emitted program on 3 of 6 tasks (50 %)** while leaving it byte-identical
   on the other 3. Enabling a "transparent speedup" silently changes which program you get,
   half the time.
2. **When it changed the program, it broke it once in three.** The ISO regression is real,
   reproducible (0/4 across two instances), and semantic — a dropped `T` in a regex.
3. **Two of the three changes were harmless** (ipv4, pathnorm: different code, same
   correctness), which is precisely why this is dangerous — the failure is occasional, not
   systematic, so it will not show up in a smoke test.

## Three harness defects caught before they became findings

1. **Loop-variable shadowing.** `run_instance()` used `for i in $(seq 1 180)` without
   `local i`, clobbering the caller's instance counter — both MTP instances wrote to
   `mtp_i2_*` and overwrote each other. The run reported **3 draws as 6**, the exact sample
   size that already fooled this campaign once in `mtp_ab.sh`. `local i` is load-bearing.
2. **Token budget scored as a quality difference.** The first structured run reported
   *"toolcalc: base correct 0/6, mtp correct 3/3"*. Base was not wrong — it looped inside
   `<think>`, hit `finish_reason: length` at 900 tokens, and never emitted the call, while
   MTP escaped the same cap **because it is ~25 % faster per token**. Published as-is it
   would have read as MTP *improving* correctness. A `finish_reason: length` guard now
   flags truncated draws instead of scoring them.
3. **Void extraction scored as STABLE.** With thinking enabled, both arms burned 900 → 2000
   → 4000 tokens entirely inside `<think>` and emitted zero content, so the code extractor
   returned the placeholder `<NO CODE BLOCK>` every time — which compares equal to itself
   and scored as "1 variant / 6, STABLE". A stable *nothing*. The analyser now reports VOID
   when every draw is a placeholder.

Defect 3 also has a model finding inside it: the model writes complete, working code inside
its reasoning block and then keeps deliberating — a 13,859-char trace ending
*"But regex is more Pythonic for this"*. **A stopping-rule failure, not a capability
failure**, the same family as the Puzzle-75B HumanEval+ result. Disabling thinking cut the
per-instance time from ~4 minutes to ~15 seconds and produced correct code immediately.

## What this means

- **MTP is safe for interactive prose and for tool calls** on this model: +24 % decode, and
  tool-call arguments — including *computed* ones — were byte-stable and correct in 12/12
  draws across both arms.
- **MTP is not safe for reproducible code generation.** Each arm is self-consistent, so the
  hazard is not flakiness but that **enabling MTP silently changes which program you get** —
  on 3 of 6 tasks — and one of those changes was a correctness regression.
- **For benchmarking, MTP must be treated as a different configuration**, never as a
  transparent speedup. A suite run with MTP on is not comparable to one run with it off.

## Limits

- One model, one `n-max` (2), one backend. Acceptance and stability will vary with
  `--spec-draft-n-max` and with the model's own confidence profile.
- 6 draws per class per arm establishes stability *on these prompts*; it does not quantify a
  flip rate.
- **Direction is unresolved.** 6 tasks, 3 of which differed between arms: MTP worse on 1,
  equal on 2, better on 0. Suggestive of a downward tilt, nowhere near enough to establish
  one. "MTP changes code" is proven; "MTP makes code worse" is not.
- All 6 tasks are short single-function problems with crisp edge cases, chosen because a
  dropped token there is visible. Longer or more open-ended code may behave differently.
- Correctness is judged by 3–5 hand-written cases per task, not an exhaustive suite; a
  subtler defect could pass as "correct" in both arms.
- Prose/code classes originally ran truncated (see defects) — only the final run, with
  thinking disabled and budgets clearing the reasoning block, is scored.

## Provenance

- `~/projects/HermesAgent-20/mtp_structured.sh` → `mtp_structured/` (4-class run)
- `~/projects/HermesAgent-20/mtp_code.sh` → `mtp_code/` (code class, thinking disabled)
- `~/projects/HermesAgent-20/mtp_code_multi.sh` → `mtp_code_multi/` (6-task direction test)
- `mtp_structured_toolsvalid/` preserves the tool-class draws whose validity was confirmed
  independently (`finish_reason: tool_calls`, 12/12 correct)
- Determinism basis: `MTP_DETERMINISM.md`
