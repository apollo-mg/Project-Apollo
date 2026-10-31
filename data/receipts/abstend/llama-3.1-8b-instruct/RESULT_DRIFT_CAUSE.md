# RESULT: the 10-27 system update changed nothing; the date in Llama 3.1's system prompt did

**Prereg:** `PREREG_DRIFT_CAUSE.md` (Addenda 1-4). **Run:** 2026-10-31 on the RX 9070 XT, kernel 7.3.0-4, firmware 20261019, llama.cpp
`f74e2fa` `build_rocm` (sha256 `6330bdf8...`), `Meta-Llama-3.1-8B-Instruct-Q8_0.gguf`. No system change was made. **Numbers:** `date_replay.txt`,
`date_judge.json`, `date_full.json`, `date_tail.json`. Answers stay in the gitignored `raw/`; these files hold flags and counts only.

## The result

Llama 3.1's template writes `Today Date: {date_string}` into the system prompt, and `common/chat.cpp` fills `date_string` from
the clock on every chat request. So this model's prompt changes at midnight. Pinning the date on the **post-update** machine
reproduces the **pre-update** run exactly:

| test | rule | result |
|---|---|---|
| pre-update `LLAMA8`, all answers | at least 995 of 1,000 equal | **1,000 of 1,000** |
| pre-update `LLAMA8`, all judge verdicts | at least 998 of 1,000 equal | **1,000 of 1,000** |
| post-update `L31AB`, 30 items at `28 Oct 2026` | at least 29 equal | 30 of 30 |
| `abstend.py compare-abench LLAMA8 LLAMA8R`, the gate run 2 failed | | **0 missing, 0 answers differ, 0 verdicts differ** |

That is bit-exact across eight days and a kernel, firmware, mesa and LLVM update.

**The split falls at midnight, from timing alone.** `LLAMA8` ran across midnight and recorded no per-row date. Walking back from
the file's finish time through each row's own `s` puts midnight at row 1472 of 2,004. The first row that needed `24 Oct` is row
1474, finished at 00:00:09. Every sub1000 row from there on equals `LLAMA8` at `24 Oct`: the 164 that failed at `23 Oct`, and the
other 98 run separately to close this (98 of 98). Every row before it matched at `23 Oct`.

## The judge

The judge is the same file on the same path, so it has been reading the date too.

- The two word-identical answers whose verdicts flipped between 10-24 and 10-28 follow the date on command: 2 of 2 each way.
- `chat_template_kwargs` pins it: `L31AB` re-judged at `28 Oct 2026` equals its stored verdicts, 1,000 of 1,000.
- **Size of the effect, one arm:** at `26 Jul 2024`, 4 of 1,000 verdicts flip, recall 0.572 to 0.568. Small, but "frozen" was not true.
- Spark 2.5 and 2.6 were both judged on 10-29, so that comparison is not confounded.

## Predictions

| # | claim | result |
|---|---|---|
| D1, D2, D3 | case move, firmware alone, reversibility | **not run.** R1-R5 were cancelled, as registered, when D6 held |
| R0 | same machine state equals `L31AB`, 30 of 30 | **FAILED: 3 of 20 sensitive items.** This is what exposed the error |
| D4 | raw prompt equals the chat path | held, 30 of 30 |
| D5 | the date explains R0 | held, 30 of 30 |
| D6 | the date explains the "update" effect | held, 20 of 20 |
| D7 | the date flips the two verdicts | held, 2 of 2 each way |
| D8 | the kwarg pin works on the answer path | held, 5 of 5 |
| D9 | the pin reproduces a stored judge pass | held, 1,000 of 1,000 |
| D10 | the date is the whole of the 708 | held, 1,000 of 1,000 |
| D11 | the dates split at midnight | printed "held" on a check too weak to fail; replaced by D13 and the timing above |
| D12 | the whole gate passes | held, 0 verdicts differ |
| D13 | every row after midnight is a 24 Oct row | held, 98 of 98 |

## What this corrects

`RESULT_llama-3.1-8b-instruct.md` said the update "changed the arithmetic". It did not. These fall:

- "Bit-exact reproduction is only defined on one (build, kernel, firmware)."
- Phi "surviving the update" as evidence of a path-specific effect: its template has no date.
- The rollback experiment built on that claim, including its firmware blob analysis as a route to a cause. The blobs did change;
  nothing measured here depends on them.

**How it got through.** "Not the prompt" rested on identical token counts, and swapping one date for another keeps the count. The
self-replay ran the same night, so it could not see a date. A rule of thumb came out of that, and the next test was designed around
it. It failed only because a baseline run was registered with an expected result.

## What changes in the pipeline

- **Compare prompts by content, never by token count.** A hash of the rendered prompt per row would have shown this on 10-28.
- **Pin the date.** `chat_template_kwargs: {"date_string": ...}` overwrites the clock (`chat.cpp:1367`). It does not reach
  `strftime_now`, so a template using that needs its prompt rendered by hand. `judge_abench.py --date` and `run_abench.py
  --template-kwargs` carry it. Instrument v3 pins the judge at `26 Jul 2024`, the default in Meta's template.
- **A diagnostic replay must cross a date boundary,** or pin the date.
- Of the recipes so far, only Llama 3.1 carries a date. Nanbeige, Spark, Phi and Granite do not. New recipes need the check.

Chains keep logging kernel, firmware and driver. That is a record, and today it is what ruled them out.

## Limits

- **One model, one binary, one card.** This shows that update did not change these outputs. It does not show that no update ever can.
- **The judge's effect is sized on one arm and one pair of dates,** and earlier arms were judged on different days.
