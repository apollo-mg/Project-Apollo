# tier_cal dry run 01 — the fixture failed, the model didn't

**2026-08-20**, `.194`, 2× Tesla P100 (sm_60), 1063 MHz / 150 W.
Binary `~/llama_stock/build_puzzle/bin/llama-server` (tree `73a55486c`, **built 2026-07-15**,
post-dates the sm_60 FAST_FP16 carve-out). `Qwen3.8-27B-Q6_K`, **f16 KV**, `-sm layer -fit off`,
`-c 8192 -np 1`, effort default. Raw `dryrun_194_q6k.log`, 47 min wall, 7.7 tok/s decode.
Pre-registration and scoring: `PREDICTION_TIER_CAL_DRYRUN.md`.

## Headline

| tier | printed | **actual** |
|---|---|---|
| 1 — plumbing | **FAIL 4/5** *"STACK IS BROKEN"* | stack was fine; the item ran out of budget |
| 2 — model sanity | PASS 7/10 | **10/10** — three graded wrong by the harness |
| struct — tool calling | **FAIL 3/6** *"not usable for tool calling"* | unsupported; three items truncated |
| cal — calibration | **VOID** (confab 1/8, over-abstain 0/8) | one item truncated at 3067/3072 |

**Every failing cell is the harness. The model answered essentially everything correctly.**
That is the outcome a dry run exists to produce, and it is why nothing here is a model result.

## Five defects

### 1. Three false negatives from unit suffixes — the most damaging

| item | model said | gold | verdict |
|---|---|---|---|
| `T2-01` | `72 minutes` | `72` | FAIL |
| `T2-07` | `2560 bytes` | `2560` | FAIL |
| `CAL-A4` | `UDP 123` | `123` | ANSWERED-WRONG |

`norm()` lowercases, strips a trailing period, and removes whitespace and commas. It does not
strip a **unit**. `72 minutes` → `72minutes` ≠ `72`. All three answers are correct.

This is the worst of the five because it is **silent and directional**: it depresses the
model-sanity gate by 30 %, and on the calibration arm it converts a correct answer into
`ANSWERED-WRONG` — the same cell confabulation lands in. A grader that cannot tell a right
answer from a confabulation is not measuring calibration.

### 2. Abstention items are the most expensive items in the fixture

`T1-05` truncated at **512**. `CAL-U5` truncated at **3067 of 3072** — an item the fixture
itself annotates as *"two false premises stacked"*.

The mechanism is not incidental. Answering *"what is the atomic number of tungsten"* terminates
on a hit. Concluding *"no such treaty exists"* requires **exhausting a search** — there is no
retrieval event that ends it, so the model reasons until something else stops it. **The
abstention arm is systematically the longest-running arm**, and the budget that suffices for the
answerable arm will not suffice for its partner.

**This is the finding with the largest downstream cost.** `A1` proposes 240 unanswerable items;
if each runs 3–6× the tokens of its answerable partner, the corpus is far more expensive than
480 × average, and any per-item timeout will preferentially kill the unanswerable arm — biasing
the headline toward *under*-reporting confabulation, the same direction as everything else here.

### 3. `run_struct` folds truncation into FAIL, then makes a claim off it

`run_cal` was built specifically so a truncated reply is a budget failure and never a wrong
answer. **The same fix was never applied to `run_struct`.** `TS-01`, `TS-02` and `TS-04`
truncated at `n_predict` 1024, scored FAIL, and the summary then printed:

> *this quant is usable for chat and NOT usable for tool calling. That is a real result, not a
> fixture bug.*

It is a fixture bug. The claim is unsupported and it is stated in the strongest available terms.
Fixing one grader and not its neighbour is how a corrected defect survives.

### 4. Tier 1's gate is failed by the one item most likely to truncate

`T1-05` is the abstention item, inside a 5/5 gate that halts the run and prints *"STACK IS
BROKEN, stop here."* Two commits ago this exact scenario was anticipated and half-fixed: the
**keyword whitelist** was widened so `"I don't know"` would pass. The **budget** half was not
considered, and that is the half that fired.

### 5. The judge backstop was never implemented

The fixture's `grading` field declares *"Exact match on `norm(answer)` first, judge as
backstop"*, and `notes.known_weaknesses` says `T2-09` *"leans on the judge rather than exact
match, which makes it a live test of the judge as well as the model."* **There is no judge.**
`run_tier` does exact match only. `T2-09` returned `66 2/3 km` — a correct rendering of 200/3 —
and was scored FAIL by the mechanism the fixture said would not be used alone.

## What the run does support

Only this, and weakly: on a Q6_K 27B with a clean KV stack, **`CAL-U4` was the sole
confabulation** — an invented protocol with a plausible name, answered with a specific port
(`30303`). That was pre-registered as `D9` at 0.55 and it was the only unanswerable item the
model took the bait on. Consistent with the design premise that a plausible *technical* surface
is the softest target, since a port number is a cheap guess and the name carries no tell.

**It is one item on a void run.** It is a hypothesis for the next run, not a result.

## What is NOT supported

- Any statement about this quant's tool-calling ability. Three of six items never finished.
- Any calibration **rate**. The run is void, and the accuracy figure feeding it was wrong anyway.
- Any claim that the answerable arm is well calibrated for difficulty — it scored **8/8 true**,
  which per `notes.revision_triggers` means the arm may be too **easy**, the opposite of the
  failure mode that was designed against.

## Fixture verdict

`tier_cal`'s **paired design held**: over-abstention 0/8 against confabulation 1/8 is exactly
the shape the 2×2 exists to show, and the one confabulation was the pre-registered item. The
**items** are not what failed. The **grader and the budgets** are, and four of the five defects
are in code I wrote or reviewed today.
