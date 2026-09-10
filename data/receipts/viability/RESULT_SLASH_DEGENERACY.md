# Result — the runaway is 4096 `/` characters, and it latches permanently

**Date:** 2026-09-09. **Arm:** `cacheab_ctrl` (`--ctx-checkpoints 32`, the default).
**Model:** Qwen3.8-27B-GSQ-RCO-IQ3_XXS, VBR (`-ctk vbr -ctv vbr --vbr-floor t2`), `-np 1`, no MTP.
**Wire capture:** `data/receipts/viability/cache-ab/wire_ctrl.jsonl` (via `tools/llmproxy`).
**Pre-registered:** `PREREG_CACHE_REUSE_AB.md`. TREAT arm still running at time of writing.

## What the "runaway" actually is

Nobody had ever looked. It is not unbounded reasoning and it is not a failure to call tools:

```
'////////////////////////////////////////////////////////////////////  … 4096 chars … '
```

**100% forward slashes**, head, middle and tail. Top-40-char-shingle share **99.1%**.
4096 characters ≈ 4096 tokens at the `-n 4096` cap, at 26.5 tok/s — the 168 s we kept measuring.

This is degenerate token repetition — a decode-level failure, not an agent-logic one. It moves the
suspect list from prompts and stopping rules to KV cache / numerics / quantisation.

## It latches

| arm | clean tasks before onset | after onset |
|---|---|---|
| v5 | 16 | 13/13 failed, never recovered |
| cacheab_ctrl | **2** | 20/20 failed, never recovered |

`ctrl` ran clean through tasks 1-2 (`tool_calls`, `stop`, 179/45/196/467-char normal outputs,
zero slashes) and from task 3 onward **every single first call was 100% slashes**. Once it starts
it never recovers within the life of the server; a restart clears it (probe B, and tasks 1-2 here).

**The latch point varies (16 vs 2); the latch itself does not.** That is the shape of a stochastic
trigger plus a persistent corrupt state, not a deterministic input-dependent bug.

## Prediction scoring

**P-C1 — CTRL reproduces onset. 75%. CONFIRMED**, more severely than predicted: 6/6 past task 17,
and in fact 20/22 overall.

**P-C4 — runaway text is degenerate, not coherent. 50%. CONFIRMED**, unambiguously.
Logged as a coin flip because nobody had ever seen this output. It is the single most useful thing
the proxy has produced: "the model stops emitting tool calls" and "the model emits 4096 slashes"
imply completely different investigations, and until today we had only the former.

**P-C3 — `sys_sha` identical across tasks. 80%. FALSIFIED.**
**22 distinct system-prompt hashes across 44 chat requests** — one per task. The earlier receipt's
claim that the system prompt is byte-identical across tasks (asserted at 35,207 chars) is **wrong**,
and it was load-bearing for the cache-similarity mechanism.

*But the mechanism survives, narrowly.* The prompts differ by at most 28 characters
(`sys_chars` spans 17,656-17,684, 12 distinct sizes), i.e. they are ~99.8% identical — consistent
with an embedded per-task path. That is exactly why the server reports `f_sim_best = 0.992-0.997`
and picks a foreign slot. So: the premise as stated was false, the conclusion it supported is not
yet damaged. Both facts belong in the record.

**P-C2 — TREAT suppresses it. 45%. PENDING**, arm running.

## Open — the proxy is a confound and has NOT been excluded

`ctrl` latched at task 3 where v5 latched at task 17, and `ctrl` is the first run to go through
`tools/llmproxy`. Arguments that the proxy is not the cause:

- A corrupting proxy should fail from task 1; tasks 1-2 were clean, with correct tool calls.
- The end-to-end validation task passed through the proxy earlier the same evening.
- Measured overhead is 0.2% and chunks are forwarded before they are parsed.
- The parser only *reads* `delta.content`; it cannot manufacture slashes that did not cross the wire.

None of these is proof. **Required control: run the first ~6 tasks against the server directly,
no proxy, and see whether the latch still occurs.** Until that runs, every conclusion here is
conditional on the proxy being transparent.

## Why this matters more than the timeout finding

"An agentic benchmark times out" is a harness story. "This model on this build emits 4096 `/`
tokens and never recovers until restart" is a concrete inference bug, and it is the kind of thing
worth reporting to buun/turboquant once the proxy is excluded and the TREAT arm is in.
