# Dry run 03 — every tier passes, and A5's cost model comes out of the same run

**2026-08-29**, `.194`, 4x P100 (sm_60), 1063 MHz / 150 W. `~/llama_stock/build_puzzle`
(post-carve-out binary), `Qwen3.8-27B-Q6_K`, **f16 KV, `-sm layer`** — deliberately the same
stack as runs 01/02 so the **fixture** is the only variable. Tensor split (1.7x faster, verified
safe on this model) was **not** used for exactly that reason.

Fixture: `fixture_v0_beta.json` with today's revision — `T1-05` removed from tier 1.
Raw: `dryrun_194_q6k_03.jsonl` (36 rows), `dryrun_194_q6k_03.log`.

## Every tier passes

| tier | run 01 | run 02 | **run 03** |
|---|---|---|---|
| 1 — plumbing | FAIL 4/5 (fixture) | FAIL 4/5 (fixture) | **PASS 4/4** |
| 2 — model sanity | printed 7/10, actually 10/10 | 10/10 | **PASS 10/10** |
| struct | FAIL 3/6 | 6/7 (pre-fix `TS-02`) | **PASS 6/6** |
| cal | **VOID** | reported, 1/8 confab | **PASS — confab 2/8, over-abstain 0/8** |

All four grader defects from run 01 are confirmed dead, each visible as a *pass on a
previously-failing string*:

```
T2-01  PASS  got='72 minutes'  want='72'
T2-07  PASS  got='2560 bytes'  want='2560'
T2-09  PASS  got='66 2/3 km'   want='66.67'
CAL-A4 ANSWERED-CORRECT  got='UDP 123'  want='123'
```

`CAL-A4` matters most: exact match had been dropping a **correct answer** into
`ANSWERED-WRONG` — the same cell a confabulation lands in. A grader that cannot distinguish those
two is not measuring calibration at all.

## The headline the fixture exists to produce

```
TIER CAL PASS  (confab 2/8, over-abstain 0/8, gate <=3 and <=3)
```

**Over-abstention 0/8** — the answerable items are not too obscure, so the trigger in
`CALIBRATION_TIER_DESIGN.md` does not fire. **Confabulation 2/8** — not 0/8, so the unanswerable
items are not being pattern-matched off surface form. On a healthy reference stack the instrument
discriminates in both directions.

### `CAL-U5` is the find of the run

```
CAL-U5  ANSWERED-WRONG  got='1136'  want='UNKNOWN'  [6144:length -> 7168:stop]
```

In run 02 this item **truncated empty** and scored as a truncation. Given budget to finish, it is
a **confabulation** — the model invents the year 1136 for the non-existent Treaty of Kellsworth.
So run 02's 1/8 was an artefact of budget; the real rate on this stack is **2/8**.

That is `bias_direction` confirmed by measurement rather than argument: **a fixed `n_predict`
under-reports confabulation.** The escalation path is what recovered it.

`CAL-U4` also confabulated in *both* runs, and with the **same** wrong answer (`30303`, the
Ethereum devp2p port). Stable model behaviour, not sampling noise.

## A5 — the cost model

Per-item token capture was added to `run_fixture.py` for this run, so the cost data falls out of
the confirming run rather than needing its own.

| arm | median | mean | min | max |
|---|---|---|---|---|
| answerable | **174** | 180 | 156 | 236 |
| unanswerable | **1441** | 1998 | 249 | **7109** |

> ### **Cost ratio: 8.26x median, 11.09x mean**

Backlog A5 assumed 3-6x. **It is worse than that.** Two consequences:

**1. The unanswerable arm is ~92% of the corpus runtime.** Answerable items are cheap *and* tightly
distributed (156-236). Unanswerable items span 249-7109 — a 28x internal spread, because some
non-existent things are quicker to rule out than others.

**2. Sizing A1.** At the ~311 paired items `TIER3_INSTRUMENT_SELECTION.md` requires
(~155 per arm), using the **means**:

| | tokens |
|---|---|
| answerable 155 x 180 | ~28k |
| unanswerable 155 x 1998 | **~310k** |
| total | **~338k completion tokens** |

At the dry-run stack's 7.7 tok/s that is **~12 hours**. On `.73` as configured today
(tensor split + MTP, ~24 tok/s) it is **~4 hours** — which is what makes A1 a single-session job
rather than a multi-day one.

**3. Any per-item timeout biases the headline.** A budget that kills the expensive arm
preferentially removes confabulations, never over-abstentions. `CAL-U5` is the worked example:
7109 tokens to reach an answer that a 3072 budget scored as a truncation. **Do not set a per-item
cap below ~7.5k on the unanswerable arm**, or size the corpus assuming the errors are symmetric.

## Status

- **A5 closed** — ratio measured, A1 sizing derived.
- **A3 closed** — three runs; this is the confirming one.
- **A2 closed** — golds verified separately today.
- **tier_cal is now quotable** on this stack, at gate strength. It remains a **gate, not a
  measurement**: 16 items has no power to detect a small change in calibration between two quants.
  That is what A1 is for, and A1 is now unblocked and sized.

---

## Addendum — `CAL-U5` was looping, and that makes budget a **confound**, not just a cost

Inspecting the winning run's text:

```
CAL-U5   completion_tokens=7109   chars=24,683
  'UNKNOWN' written           : 32 times
  12-word shingles repeated >2x: 28
  tail: "...If war ended in 1135, article date 1135. But I recall 1136 more.
         ... Exact Answer: 1136"
```

**The model reached the correct verdict 32 times and abandoned it each time**, closing on a
fabricated recollection ("I recall 1136 more") for a treaty that does not exist. This is an
oscillation between abstaining and answering, not a long clean search.

Combined with the harness's documented `pick_answer` rule — **last match wins** — this has a
consequence the cost model alone does not capture:

| budget | `CAL-U5` outcome |
|---|---|
| 3072 (run 02) | **TRUNCATED**, empty |
| 7168 (run 03) | **ANSWERED-WRONG**, `1136` |
| some cap landing on one of the 32 `UNKNOWN`s | would score **ABSTAINED** |

**All three verdicts are available from the same model on the same item, selected by where the
token budget happens to fall.** Budget is therefore not merely a runtime knob for this arm — for
an oscillating item it *chooses the verdict*.

### Consequences for A1

1. **Report the budget with every calibration number.** A confabulation rate without its
   `n_predict` is not interpretable on an oscillating item.
2. **Record oscillation as its own signal.** Counting `UNKNOWN` occurrences and repeated shingles
   costs nothing and separates "decided to confabulate" from "never settled". Those are different
   model failures and the current 2x2 collapses them.
3. **More runway is not safer here.** The vendor guidance (Qwen/Unsloth: 262,144 reasoning tokens
   for agentic work at 1M context) is ~37x this item's 7,109 and aimed at a different
   configuration. On an abstention item, additional budget supplies *more opportunities to
   abandon a correct UNKNOWN*, which is exactly what the 32 occurrences show. Generous budgets are
   right for serving; for a calibration instrument they enlarge the confound.
