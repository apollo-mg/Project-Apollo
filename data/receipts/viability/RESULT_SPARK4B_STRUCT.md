# Spark-X2.5-4B: 18/18 on JSON and tool calling — after fixing a fixture bug that penalised it for following instructions

**Date:** 2026-09-07 · **Model:** `Spark-X2.5-4B-Q4_K_M`, 2.42 GiB, arch `spark2_5`
**Engine:** `XHToken/llama.cpp` `4a3635c32`, gfx1201 · `-ngl 99 -c 32768 -np 1 -fa on`
**Harness:** `run_fixture_structfix.py` (one-line patch, see below) + `fixture_struct_fixed.json`
**Raw:** `sparktrue_rep{1,2,3}.jsonl`, `spark_truefix.log`; broken-harness runs in
`spark_struct_rep*.jsonl`, `sparkstruct_rep*.jsonl`, `sparkfix_rep*.jsonl`

## Result

| | TS-01 | TS-02 | TS-03 | TS-04 | TS-05 (tool call) | TS-06 | total |
|---|---|---|---|---|---|---|---|
| rep 1 | PASS | PASS | PASS | PASS | PASS | PASS | 6/6 |
| rep 2 | PASS | PASS | PASS | PASS | PASS | PASS | 6/6 |
| rep 3 | PASS | PASS | PASS | PASS | PASS | PASS | 6/6 |

**18/18.** Nested objects, exact-value arrays, escaped quotes inside strings, empty-array
handling, and a `get_weather(city, units)` tool call with correct nested arguments. `~11 s`
per 6-item rep.

## Speed

Median **118.6 t/s** decode (n=172 samples, min 103.8, max 127.1), prefill ~1,670 t/s,
model load **1.5 s**. For orientation, Qwen3.8-27B on this same card runs ~29–30 t/s decode
and ~25 s to load.

## The fixture bug, and why it mattered here specifically

`run_fixture.py:282` — `run_struct` calls `ask()` **without passing `prompt=`**, unlike
`run_tier` two functions below which passes `tier.get("prompt")`. So the module-level default
is applied unconditionally to every structured item:

```
{q}

Think briefly if you need to, then end your reply with exactly one line:
Exact Answer: <your answer>
```

Every `tier_struct` item says *"Reply with ONLY a JSON object"*. **The two instructions cannot
both be satisfied.**

Measured effect on this model:

| harness | result | cost |
|---|---|---|
| as-shipped | 2/6, 3/6 — **VOID on truncation** | ~8 min/rep, traces to 30,015 chars, 9.6–14.9% repeated 8-grams |
| `prompt=` passed | **6/6 ×3** | ~11 s/rep |

The truncated traces show the model reasoning explicitly about the conflict:

> *"...the intended output is just the JSON object, and the "Exact Answer" line is a standard
> footer that the system adds automatically? But we are to reply with exactly what is asked."*

It never resolved it, and looped until the token budget ran out.

## Why this bug was invisible until now

**Qwen3.8-27B scored 6/6 on the broken harness** (`RESULT_DRYRUN_02.md`). It resolved the
contradiction by emitting the JSON *and* appending the footer; `extract_json` then found the
JSON and the item passed. The contradiction cost it nothing.

So the defect **differentially penalises models by how literally they follow instructions.**
A model that treats "reply with ONLY X" as binding is punished; a model that quietly drops one
instruction is rewarded. That is precisely backwards for a fixture whose purpose is measuring
instruction adherence, and it means the metric was inverted for the failure mode it exists to
detect.

Had this run been reported without investigating the truncation, the conclusion would have
been *"a 4B cannot do reliable JSON or tool calling"* — the exact claim
`RESULT_DRYRUN_01.md` warned about when it found the **first** `run_struct` bug:

> *"this quant is usable for chat and NOT usable for tool calling. That is a real result, not a
> fixture bug." — It is a fixture bug. […] Fixing one grader and not its neighbour is how a
> corrected defect survives.*

That was written about truncation-scored-as-FAIL. This is the second defect of the same shape
in the same function, found the same way, two dry runs later.

## Scope of invalidation

Every `tier_struct` number in this corpus was measured under contradictory instructions:
`RESULT_DRYRUN_01.md` (FAIL 3/6), `RESULT_DRYRUN_02.md` (6/7 pre-fix `TS-02`),
`RESULT_DRYRUN_03_AND_A5.md` (PASS 6/6). The Qwen passes are probably robust — it resolved the
conflict and passed anyway — but they are not clean measurements and no `tier_struct` number
should be quoted as an instruction-adherence result until re-run.

**The fix has not been applied to `run_fixture.py`.** It lives in `run_fixture_structfix.py`
so historical runs remain reproducible against the instrument that produced them. Promoting it
is a decision about the fixture's version, not a bug fix to slip in.

## Limits

- 6 items × 3 reps, one model, one quant, greedy-free card sampling.
- `-c 32768 -np 1` here vs `-c 8192` on the `tier_cal` arms — needed because 4 slots sharing
  8192 under `kv_unified` cannot hold a 7,168-token generation. Not comparable to the cal arms
  on any context-sensitive metric.
- `n_predict` raised 3072 → 7168 for the same reason.
- This says nothing about multi-turn tool loops, which is where
  `RESULT_SYS02_QWEN38.md` shows even a 27B fails (0/5 process).

> **SAMPLING CAVEAT (added 2026-09-07):** this run used `top_k=20`, which is **Qwen3.8's** card value
> inherited from `run_fixture.py`'s hardcoded `card` preset. **Spark-X2.5's card specifies `top_k=-1`.**
> See `PREREG_SPARK_HERMES.md` Amendment for why this bites hardest at high-entropy positions —
> exactly where abstention is decided. Ceiling results (24/24, 18/18) can only move down; the
> `tier_cal` abstention figure is the one that needs re-running.
