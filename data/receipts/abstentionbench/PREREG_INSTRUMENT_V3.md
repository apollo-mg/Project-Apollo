# Pre-registration -- AbstentionBench instrument v3: the judge's date pinned, and the anchors re-judged

**Registered 2026-11-02, before any v3 row.**

**Why.** The judge is Llama 3.1 8B on llama.cpp's chat path. Its template writes `date_string` into the system prompt, and
llama.cpp fills that from the clock, so every judge pass so far ran a different prompt depending on the day. A different
date flipped 4 of `L31AB`'s 1,000 verdicts (recall 0.572 to 0.568), and the subject's date drove the 708 / 1,000 answer
changes once blamed on a system update (`../abstend/llama-3.1-8b-instruct/RESULT_DRIFT_CAUSE.md`).

**Prior art checked:** `ledger_precheck.py "judge date pin instrument v3 re-judge anchors"` -> receipts found: the drift-cause
result above, which sized the effect on one arm. **What this adds:** every anchor at the pin, and the first v3 subject run.

## Instrument v3 (`data/scorecard/instruments.json`)

v2 plus:
- **The judge's date:** `date_string` pinned to `26 Jul 2024`, its template's own default. That is also what Meta's vLLM runs
  rendered, since nothing there sets the variable.
- **Prompt hashes:** every subject and judge row records `prompt_sha`, the first 16 hex characters of sha256 over the
  rendered prompt (`/apply-template`). `compare-abench` checks them.
- **Subject dates:** a subject whose template carries a date variable must pin it in every chat-path request. `abstend.py
  chain` refuses otherwise, and refuses `strftime_now`, which template kwargs cannot pin.

## Test (`rejudge_v3.sh`, `analyze_v3.py`)

One server on the 9070: the judge's file, binary and flags (`f74e2fa`, `-ngl 99 -c 32768 -np 1 -ctk f16 -ctv f16 --cache-ram 0`),
Clef paused, the judge's port.

1. **Re-judge the stored answers** of `LLAMA8`, `L31AB`, `Q27OFF`, `Q27ON`, `S25AB` and `S26AB` on the sub1000 items, at the pin,
   with prompt hashes: `raw/<ARM>.judge_v3.jsonl`, committed as `verdicts_<ARM>_v3.csv`.
2. **One v3 subject run:** `L31V3`, Llama 3.1 8B Q8_0, v2's sampler sent explicitly, neutral penalties, `date_string` pinned to
   `26 Jul 2024`, prompt hashes, then judged at the pin.

| # | claim | rule | confidence |
|---|---|---|---|
| V1 | The pinned judge is deterministic | `L31AB` re-judged equals the 10-31 pinned pass (`L31AB.judge_dpin.jsonl`) on at least 999 of 1,000 | 0.9 |
| V2 | The pin barely moves verdicts | on every anchor, at most 1.0 % of sub1000 verdicts differ from its stored pass | 0.8 |
| V3 | No card metric moves | abstention recall and precision change by at most 0.01 on every anchor | 0.75 |
| V4 | The v3 subject run is whole and close to `L31AB` | 1,000 rows, each with a `prompt_sha`; abstention recall within 0.03 of `L31AB`'s 0.572 | 0.8 |

**Reported without prediction:** flips per anchor, missing-info and false-premise recall, and the v1/v2 vs v3 card values.

## Limits

- **Only the judge's date is fixed for old anchors.** Their subject answers keep the dates they were generated on. Only the
  Llama subject's prompt depends on the date, and `L31V3` is the clean v3 Llama row.
- **Cards are not switched here.** `build_scorecard.py` keeps v1 and v2 rows; v3 rows are added once this result is in.
- **One judge file, one engine, one card.**
