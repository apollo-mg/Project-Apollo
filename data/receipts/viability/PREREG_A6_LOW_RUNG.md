# PREREG — completing the effort ladder at card sampling: the `low` rung

**Written 2026-09-07, before the run.** Scored honestly afterwards, including misses.

## Why this rung is not simply "less than medium"

`RESULT_EFFORT_IS_A_PROMPT_EDIT.md` and `CARD_CROSSCHECK.md` established that the template
has **no `medium` branch** — medium validates, falls through, and injects **nothing**. `low`
*does* inject an instruction. So the implemented ordering is not the card's documented
ordering: medium is "no instruction", and low is **more** interventional than medium, not
less. A monotonic xhigh → medium → low trend is therefore not the default expectation.

Existing data (card sampling, 3 reps, 24 items/arm, `.194`/Q6_K, chars not tokens):

| | xhigh | medium |
|---|---:|---:|
| answerable correct | 24/24 | 24/24 |
| unanswerable abstained | 13/24 | 21/24 |
| confabulated | 6/24 | 3/24 |
| NO-STOP | 5/24 | 0/24 |
| unanswerable chars median | 5,829 | 1,052 |

## Matched conditions

Binary `~/llama_stock/build_puzzle/bin/llama-server` (tree `73a55486c`, built 2026-07-15) —
the same binary as the 08-21 arms. `Qwen3.8-27B-Q6_K`, `-ngl 99 -c 8192 -sm layer`, f16 KV,
`.194` 4× P100 at 1063 MHz / 150 W. `--tier cal --sampling card`, seeds 1001–1003, matching
the existing reps so the three efforts are paired by seed.

`n_ctx 8192` is deliberate: it caps escalation at 7168, which is what the 08-21 arms ran under.
Raising it would make the NO-STOP counts incomparable.

## Predictions

| # | prediction | confidence |
|---|---|---|
| P1 | `low` unanswerable ABSTAINED ≥ 21/24 (at least as good as medium) | 0.55 |
| P2 | `low` NO-STOP = 0/24 | 0.85 |
| P3 | `low` answerable ANSWERED-CORRECT < 24/24 — brevity pressure costs a multi-step item | 0.45 |
| P4 | `low` unanswerable chars median < 1,052 (below medium) | 0.80 |
| P5 | The ladder is **non-monotonic** — `low` does not simply continue the xhigh→medium trend on the abstention metric, because low adds an instruction where medium removes one | 0.50 |
| P6 | `CAL-U3` fails at least once at `low` — it is the only item that failed at medium, so it is the most fragile | 0.60 |

**P1 and P5 are deliberately in tension.** P1 says low is at least as good; P5 says the trend
may break. If both resolve true, low is better *and* for a different reason than medium was —
which is the outcome that would most change how we set effort in production.

## What would falsify the headline finding

The A6 result claims effort, not sampling, governs NO-STOP. If `low` produces NO-STOP > 0/24
while medium produced 0/24, "less effort → fewer runaways" is wrong as a general statement and
the mechanism is something narrower about the medium branch specifically.

## Stopping rule

3 reps at `low`, then stop and score. Extending medium/xhigh for statistical power is a
separate decision made after these numbers exist — not folded into this run.
