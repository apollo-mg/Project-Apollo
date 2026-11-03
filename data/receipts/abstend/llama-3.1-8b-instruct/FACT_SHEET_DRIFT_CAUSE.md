# Fact sheet: the "system update drift" was a date in Llama 3.1's prompt

For Mark to write from. Every number is in `RESULT_DRIFT_CAUSE.md`, `RESULT_llama-3.1-8b-instruct.md` (its correction block) and
`../../abstentionbench/RESULT_INSTRUMENT_V3.md`. ASCII only.

## The short version

1. We reported that a system update (kernel, GPU firmware, mesa, LLVM) changed Llama 3.1 8B's outputs. It did not.
2. Llama 3.1's chat template writes today's date into the system prompt, and llama.cpp fills that date from the clock on every
   chat request. So the prompt changes at midnight, and so do sampled answers.
3. With the date pinned, the post-update machine reproduces the pre-update run exactly: 1,000 of 1,000 answers and 1,000 of
   1,000 judge verdicts.
4. The judge is the same Llama 3.1 file, so it read the date too. Pinning it is now part of the instrument (v3).

## What happened, in order

- 10-23 to 10-24: the reference AbstentionBench run (`LLAMA8`) ran across midnight.
- 10-27: system update. Kernel, firmware 20261019, mesa, LLVM.
- 10-28: the pipeline's run of the same model (`L31AB`): 708 of 1,000 answers differed from the reference, and 2 of 292 greedy
  judge verdicts flipped. We attributed this to the update and wrote that it "changed the arithmetic".
- 10-31: a baseline replay registered with an expected result (R0) failed: 3 of 20 matched on the same boot, kernel, firmware
  and binary. That failure exposed the date. Same day: pinning the date reproduced both runs.
- 11-01: everything moved into a new case, and the kernel went from 7.3.0-4 to 7.3.1-1. A pinned replay still matched (30 of 30
  and 20 of 20).
- 11-02: instrument v3 shipped with the judge's date pinned.

## The mechanism

- Template line: `Today Date: {date_string}` in the system prompt.
- llama.cpp `common/chat.cpp` sets `date_string` from the clock on the chat path.
- `chat_template_kwargs: {"date_string": "..."}` in the request overrides it (`chat.cpp:1367`). It does not reach templates that
  call `strftime_now`; those need the prompt rendered by hand.
- Swapping one date for another keeps the token count. Our "not the prompt" check compared token counts, so it could not see
  this.

## Results

| test | rule set before running | result |
|---|---|---|
| reference run, all answers, date pinned | at least 995 of 1,000 equal | 1,000 of 1,000 |
| reference run, all judge verdicts | at least 998 of 1,000 equal | 1,000 of 1,000 |
| pipeline run, 30 items at its own date | at least 29 equal | 30 of 30 |
| full comparison tool on the pinned rerun | | 0 missing, 0 answers differ, 0 verdicts differ |

- Bit-exact across eight days and a kernel, firmware, mesa and LLVM update.
- The midnight split falls out of timing alone. Walking back from the run's finish time puts midnight at row 1,472 of 2,004;
  the first row that needed the next day's date is row 1,474, finished at 00:00:09. Every later row matches at the next date
  (98 of 98 run separately to close it).

## The judge

- Two word-identical answers whose verdicts flipped between runs follow the date on command: 2 of 2 each way.
- Pinned, the judge reproduces a stored pass: 1,000 of 1,000.
- At v3's pin (26 Jul 2024, the default in Meta's template), verdicts flip on 0.4 to 1.8 percent of items across six reference
  setups. Precision drops on all six, by up to 0.039. Recall moves by 0.009 at most.
- Of the 71 flips, 48 go from "not an abstention" to "an abstention". 15 of the 71 are QASPER (questions about scientific
  papers). They are not concentrated in the time-sensitive question sets.

## What changed in the pipeline

- Under v3, every subject and judge row carries a hash of its rendered prompt. Prompts are compared by content, never by token
  count.
- The chain refuses to run a model whose template reads the date unless the recipe pins it.
- Instrument v3 is the AbstentionBench instrument with the judge's date pinned. The scorecards show v3 rows beside the older
  ones and label which version each number comes from. Versions are never compared with each other.
- Of the models run so far, only Llama 3.1 has a date in its template. Nanbeige, Spark, Phi and Granite do not.

## What is NOT claimed

- Not that updates can never change outputs. One model, one binary, one card.
- Not that the date matters for every model. Only templates that render it are affected.
- The judge effect is sized at one pinned date. Whether a different date tips the same borderline answers is untested (a
  second-date control would take about six minutes per setup).

## What was retracted

- "The update changed the arithmetic."
- "Bit-exact reproduction is only defined on one (build, kernel, firmware)."
- Phi "surviving the update" as evidence of a path-specific effect. Phi's template has no date.
- The planned rollback experiment and its firmware analysis as a route to a cause.

## How the error got through, and what caught it

- "Not the prompt" rested on equal token counts.
- The self-replay ran the same night, so it could not see a date change.
- The rule of thumb from that shaped the next test. It failed only because a baseline run was registered in advance with an
  expected result, and the result did not match.
