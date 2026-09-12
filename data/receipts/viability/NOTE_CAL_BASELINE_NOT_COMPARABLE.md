# Note — the Q6_K CAL baseline (11/24) was measured at half the context, and is not a clean comparator

**2026-09-12, ~02:00. Found by Mark asking for an apples-to-apples check** on why tonight's Q6_K arm
was failing ~3/17 when the historical baseline failed 11/24.

## The difference

`run_fixture_structfix.py` sets the escalated-retry budget to `min(n_predict * 2, n_ctx - 1024)`
(line 222). Each row records the budgets it used, so the server's context is recoverable from the
data:

| dataset | attempts recorded | implied `n_ctx` |
|---|---|---|
| `card_xhigh_rep{1,2,3}.jsonl` (the 11/24 baseline) | `(6144, 7168)` | **8192** |
| tonight's `overthink/` (IQ3_M) and `overthink_q6k/` | `(6144, 12288)` | **16384** |

## Why it changes the number

The baseline's 11/24 is **6 ANSWERED-WRONG + 5 NO-STOP/REC**. NO-STOP means the model hit its cap on
the first attempt *and again* on the retry. At `n_ctx` 8192 that retry was 7,168 tokens; tonight it
is 12,288. A generation that runs 8–12k tokens is scored NO-STOP in the baseline and completes
tonight.

**So roughly half the baseline's failure count is a context-budget artifact, not a model property.**
The WRONG component (6/24) is the part that transfers.

## What this invalidates

- **P-Q1 in `RESULT_OVERTHINK_INJECTION_IQ3M.md`** — scored FALSIFIED on "IQ3_M arm A fails 4/24 vs
  the Q6_K baseline's 11/24". That compared **IQ3_M at 16k against Q6_K at 8k**. The direction may
  still hold on the WRONG component alone (IQ3_M 3/24 vs Q6_K 6/24), but it is no longer a clean
  falsification and should not be cited as one.
- **The power calculations in both preregs**, which assumed an 11/24 baseline rate. The real rate at
  matched context is lower, so both designs were even more underpowered than stated.
- **Any future comparison against `card_xhigh_rep*`** without matching `-c 8192`.

## What it does not invalidate

- **The within-run arm contrasts.** A vs B vs C inside `overthink/` and inside `overthink_q6k/` are
  internally matched — same server, same context, same session.
- **`RESULT_SWIFT_BREVITY_TAX.md`**, which compares SWIFT to BASE arm A, both from tonight at
  `-c 16384`.

## Still open: P-Q4 vs P-Q5 has its own confounds

The bet compares tonight's IQ3_M run to tonight's Q6_K run. Context now matches (16384 both), but
three other things do not:

| | IQ3_M run | Q6_K run |
|---|---|---|
| node | RX 9070 XT, single GPU | `.194`, 2× P100 |
| KV cache | `q8_0` | `f16` |
| split | none | tensor |

KV quantisation is not a free variable here — `kv-fidelity/RESULT_U5_FIDELITY.md` puts `q8_0` at
R = 10.5 against f16, and the whole campaign is about what precision costs. **A clean settlement of
P-Q4/P-Q5 needs IQ3_M re-run on `.194` under the Q6_K server's exact configuration**, leaving bit
depth as the only variable. That is the next run, and until it exists the bet is unresolved rather
than decided.

## Lesson for the fixture

The runner records enough to recover `n_ctx` after the fact, which is the only reason this was
findable months later. **Server context belongs in the receipt explicitly**, not implicitly in an
escalation budget — it is a first-class experimental variable for any fixture that can hit a cap.
