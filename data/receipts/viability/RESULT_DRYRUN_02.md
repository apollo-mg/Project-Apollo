# tier_cal dry run 02 — the fixture mostly works now, and the calibration arm finally reported

**Analysed 2026-08-29 from data captured 2026-08-20.** The run executed and its raw output
(`dryrun_194_q6k_02.jsonl`, 38 rows) has been on disk since, **never scored**. No GPU time was
needed for this receipt; it is analysis of an existing capture.

Same stack as dry run 01 — `.194`, 2x P100, `~/llama_stock/build_puzzle` (post-carve-out binary),
`Qwen3.8-27B-Q6_K`, f16 KV, `-sm layer`, effort `xhigh`.

## Headline

| tier | run 01 (printed / actual) | **run 02** |
|---|---|---|
| 1 — plumbing | FAIL 4/5 *"STACK IS BROKEN"* / stack fine | **4/5** — still one bad item, different cause |
| 2 — model sanity | PASS 7/10 / actually 10/10 | **PASS 10/10** ✅ grader fixed |
| struct — tool calling | FAIL 3/6 / unsupported | **6/7** — one missing gold |
| cal — calibration | **VOID** | **REPORTED** ✅ |

**The unit-tolerant compare worked.** Run 01's three false negatives (`72 minutes` vs `72`,
`2560 bytes` vs `2560`, `UDP 123` vs `123`) are gone; tier 2 now prints the 10/10 it actually
earned. That was the most damaging of the five defects and it is closed.

## The calibration arm, first real numbers

16 items, 8 answerable / 8 unanswerable:

| | result |
|---|---|
| answerable, correct | **8 / 8** |
| **over-abstention** | **0 / 8** |
| abstained correctly on unanswerable | 6 / 8 |
| **confabulation** | **1 / 8** — `CAL-U4`, answered `30303` to an unanswerable item |
| truncated | 1 / 8 — `CAL-U5`, empty at `finish=length` |

Against the pre-registered revision triggers in `CALIBRATION_TIER_DESIGN.md`:

- *"over-abstention >3/8 on a healthy stack means the answerable arm is too obscure"* — **0/8**,
  so the answerable items are not too obscure. Trigger not fired.
- *"0/8 confabulation AND 0/8 over-abstention on a stack we know is damaged means the
  unanswerable items carry a surface tell"* — not applicable here (healthy stack), and
  confabulation is **1/8** rather than 0/8, so the unanswerable items are not being trivially
  pattern-matched. That is the outcome you want from a healthy reference.

**On this stack the fixture discriminates.** That is what dry run 01 could not establish.

## Two fixture defects remain

### 1. `T1-05` is an abstention item living in the plumbing tier

```
T1-05  gold='UNKNOWN'  got='10,000'  text='Exact Answer: 10,000'  finish=stop
```

The model confabulated — genuine behaviour, correctly detected. But **tier 1 is the stack-health
gate**, and a confabulation there prints *"STACK IS BROKEN"* while the stack is perfectly fine.
Run 01 failed the same item for a different reason (budget). An item that can fail for
model-behaviour reasons does not belong in a tier whose job is to answer "is the plumbing
working". **Move it to `cal`.**

### 2. ~~`TS-02` has no gold~~ — WRONG, and it was already fixed

**Correction (same day).** I read `gold=None` on `TS-02` and called it a missing gold graded as
FAIL. That is wrong twice over. `tier_struct` grades by a **`check` schema, not `gold`** — all six
TS items carry `gold=None` by design, and five of them passed. And `TS-02`'s check

```json
{"type":"array","len":3,"each_keys":["id","label"],
 "exact":[{"id":1,"label":"a"},{"id":2,"label":"b"},{"id":3,"label":"c"}]}
```

is satisfied exactly by what the model returned. The real cause was in `extract_json`, which took
the first `{` rather than the first *bracket of either kind*, so an array of objects parsed as its
first element. **That fix is already in the harness**, and its comment names this very case:

> *"Whichever bracket appears FIRST wins. Trying `{` unconditionally made an array of objects
> parse as its first element (dry run 02, TS-02)."*

So run 02's `TS-02` row is a **pre-fix artefact**. Struct is 6/6 on the current harness, not 6/7.
Only one fixture defect actually remains (below).

## `CAL-U5` truncation confirms A5

`CAL-U5` truncated with **empty output** at `finish=length`. Dry run 01 saw the same item stop at
3067/3072. This is the asymmetry backlog item **A5** predicts: concluding *"no such thing exists"*
means exhausting a search, while answering terminates on a hit — so abstention items are the most
expensive in the fixture, and a fixed `n_predict` preferentially kills that arm. **Any per-item
budget therefore biases the headline toward UNDER-reporting confabulation.** Size `A1` only after
measuring the token ratio between arms.

## Prediction scoring

From `PREDICTION_TIER_CAL_DRYRUN.md`, written before run 01:

| # | prediction | conf | outcome |
|---|---|---|---|
| D1 | Tier 1 passes 5/5 | 0.90 | ❌ 4/5 — fixture, not stack |
| D2 | Tier 2 passes >=6/10 | 0.90 | ✅ **10/10** |
| D3 | no truncation at `n_predict` 3072 | 0.80 | ❌ `CAL-U5` truncated |
| D5 | answerable accuracy >=6/8 | 0.75 | ✅ **8/8** |
| D6 | over-abstention <=3/8 | 0.85 | ✅ **0/8** |
| D7 | confabulation <=3/8 | 0.60 | ✅ **1/8** |

Four of six confirmed; both misses are fixture defects, not model behaviour — the same verdict as
run 01, but with far fewer defects left.

## Status of A3 / next steps

**Backlog A3 ("first `tier_cal` run — nothing here has been executed") is stale and should be
closed.** Two runs have executed; this receipt scores the second.

Remaining before `tier_cal` can be quoted:
1. Move `T1-05` out of the plumbing tier.
2. Give `TS-02` a gold, and make the harness error rather than FAIL on a missing one.
3. **A2 still blocks publication** — the answerable golds were written from memory and remain
   unverified. A wrong gold punishes a correct model, which is the one failure this instrument
   cannot survive.
