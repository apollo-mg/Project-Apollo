# Pre-registration -- two candidate loop detectors, fixed before any new trace exists

**2026-09-26 ~00:30.** `RESULT_LOOP_LOGITS.md` found no logit-level signal separating Bonsai's 3 capped loops from
long-but-healthy traces. It found one post-hoc statistic that did separate them in-sample. This file fixes two
detectors and their thresholds now, so that the next traces test them rather than refit them.

**Prior art checked:** `ledger_precheck.py "thinking loop stop probability end of think logits runaway"` -> L46 (a
bare cap removes the tail), L47 (thinking length flags confabulation on CAL), and `loop-logits` (this campaign).

## Detectors (text-only; computed on the reasoning as it streams)

- **D1, "Let" share.**
  - *Denominator:* lines of the reasoning (split on newline, blank lines dropped) after the first 1,000
    characters.
  - *Numerator:* the fraction of those lines that begin with `Let` (case-sensitive, after stripping leading
    whitespace and list bullets).
  - *Flag:* D1 >= **0.21**, evaluated over a rolling window of the last 40 lines once at least 40 lines exist.

  In-sample (a line-level proxy of the boundary statistic): LOOP 0.23-0.33, LONG-OK 0.12-0.19, SHORT 0.05-0.15.
  The 0.21 threshold sits between the groups and was chosen on these same traces, which is why it has to be tested
  on new ones.
- **D2, reopened drafts.**
  - *Counts:* how many times a line containing `Exact Answer: <value>` (a concrete value, not `<your answer>`) is
    followed by more reasoning rather than the end of thinking.
  - *Flag:* D2 >= **3**.

  In-sample, D2 does **not** separate: loops 0-1, healthy 0-1. It is registered as the obvious content detector,
  with a threshold above anything seen, so that its failure or success on new data is informative.

## Test set (the next traces, whichever comes first)

- The same 16 CAL items at `reasoning_effort` **medium** on Bonsai 2 (3 reps).
- Or SWE-bench-style problem statements at `xhigh`, on Bonsai 2 **and** on Qwen3.8-27B. That supplies the
  "legitimately long" traces buun described.

**Label:** a trace is a LOOP if it hits the escalated cap (NO-STOP). Everything else is healthy, whatever its
length.

**Reported:** for each detector, its true- and false-positive counts, and the token position of the first flag
relative to the trace's total length. A detector is only useful if it flags early (before about half of the
eventual cap) and rarely flags healthy long traces.

| # | claim | test | conf |
|---|---|---|---:|
| E1 | D1 flags most loops | flags >= 2/3 of NO-STOP traces | 0.40 |
| E2 | D1 rarely flags healthy long traces | flags <= 20 % of terminating traces longer than 4,000 tokens | 0.40 |
| E3 | D2 at >= 3 flags few healthy traces | <= 10 % of terminating traces | 0.60 |

**Not established by design:** these are text detectors over one model family's style. A detector tuned to "Let"
is a detector for Bonsai's (and Qwen-family's) register, not a general one.
