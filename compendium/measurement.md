# Measurement: lessons that changed a published number or came back more than once

Read this before designing a test or trusting a comparison. Rules of procedure (preregister, prior-art check) are in
`AGENTS.md`; these are the facts behind them. Line rules: `compendium/README.md`.

## The server and the engine

- **Restart the server before every benchmark leg and record its uptime.** A llama-server that had been up about 14
  hours took 48.3 s for a 24-token reply; after a kill and an identical relaunch, 0.3 to 0.7 s. (measured 2026-08-28;
  `data/receipts/FAILURE_MODES.md` AFM-26)
- **Temperature 0 is only repeatable under conditions.** Concurrent batched decoding changes temperature-0 output, in
  upstream llama.cpp too, so `-np 1` is the control; prompt-cache reuse changes it as well, so send
  `"cache_prompt": false`. Scope: byte-for-byte comparisons on .73 (2x P100) and the 16 GB desktop card. (measured
  2026-07-27 and 2026-07-30; `data/receipts/hermesagent20/DETERMINISM_ROOT_CAUSE.md`,
  `data/receipts/battle16gb/MTP_CACHEPROMPT_FALSIFICATION.md`)
- **A health check does not prove the right thing is running.** `/health` 200 and a correct model path both passed
  while a no-speculation arm was measured against a speculating server; nine rows were mislabelled. Assert the property
  you are measuring (there, `draft_n` in the response). (measured 2026-09-22;
  `data/receipts/mtp-transfer/RESULT_MTP_HEAD_TRANSFER.md`)
- **The binary is part of the instrument.** Reconfiguring an existing llama.cpp build directory recompiled the server
  at the same commit; a replay was byte-identical (240 of 240), but the old binary's hash had never been recorded.
  Record a frozen instrument's sha256; `build_engine.sh` refuses an existing directory without `REBUILD=1`. (measured
  2026-11-11; `data/receipts/abstend/NOTE_ROCM_REBUILD_2026-11-11.md`)

## Prompts and files

- **The prompt can change with the calendar.** Llama 3.1's chat template writes today's date into the system prompt;
  that alone changed the answers on 708 of 1,000 AbstentionBench items at temperature 0.8, and with the date pinned the
  run reproduced 1,000 of 1,000. Equal token counts had hidden it. Compare prompt content, and pin `date_string`.
  (measured 2026-10-31; `data/receipts/abstend/llama-3.1-8b-instruct/RESULT_DRIFT_CAUSE.md`)
- **A quant label is not a spec.** Files labelled "3-bit" hold a median 3.5 real bits per weight and the label spans
  26%; compare by scored bytes or at matched precision, never by label. A fine-tune's drop in refusal held at matched
  precision (-0.19, both files one packager's Q6_K). (measured 2026-09-19 and 2026-11-09;
  `data/receipts/lowbit-ladder/FINDING_LABEL_VS_REAL_BPW.md`, `data/receipts/quant-abstention/RESULT_SAGE_MATCHED.md`)
- **Answers without "I don't know" are enough to remove it, and freezing the end layers does not stop that.** A LoRA
  on Granite 4.1 3B's own correct answers took refusal of invented items from 81 of 100 to 20, 3 or 0 depending on the
  training seed; with the adapter kept off the last 10 of 40 layers, to 18, 5 or 2. To keep abstention through a
  fine-tune, put "I don't know" examples in the data, and expect some real questions declined as the cost.
  Compare fine-tunes over several training seeds, not one. (measured 2026-10-17 and 2026-11-23;
  `data/receipts/idk-lora/RESULT_IDK_LORA.md`, `data/receipts/frozen-layers/RESULT_FROZEN_LAYERS.md`)
- **A perplexity gap to another model is not an implementation check; the reference implementation is.** SenseNova-Loop-9B
  read 2.07x Qwen3.5-9B's wikitext perplexity on a new llama.cpp port, which looked like a broken port; SenseTime's own
  code gave the same number to 0.1 % on the same chunks. Models trained away from English web text legitimately score
  high there. To vet a new port, score the same chunks with the reference code (tokens checked identical first).
  (measured 2026-11-23; `data/receipts/sensenova-loop/RESULT_SENSENOVA_LOOP.md`)
- **Change one dial at a time: thinking, sampling and the system message are separate.** A first Sage comparison moved
  all three together, so it showed the package and not thinking. Measured apart on Qwen3.5-9B (Q8_0, 100 invented
  items): thinking moved refusal of invented items 0.68 to 0.94 and left hard recall at 0.38 to 0.39; greedy against
  sampled with thinking off moved refusal by 0.03. (measured 2026-10-25 and 2026-11-10;
  `data/receipts/quant-abstention/RESULT_SAGE.md`, `data/receipts/sci-distill/RESULT_SCI_DISTILL.md`)

## Grading

- **Grade the outcome, not the route.** An upstream rename broke a grader that matched tool names (6 tasks per run
  graded wrong) and left one that checked the resulting state untouched. The same holds for an agent's own exit codes:
  pilot agents piped a failing test run through grep, which exits 0. (measured 2026-09-08 and 2026-11-16;
  `data/receipts/FAILURE_MODES.md` AFM-33, `data/receipts/agentic-gaming/REVIEW_2026-11-16.md`)
- **Format graders miss bare answers; read the unparsed rows of every arm early.** 13 answers per arm that were the
  bare word UNKNOWN were graded as no answer on Sage. On a distilled 9B, counting bare refusals turned a strict
  over-refusal figure upside down, and showed an abstention adapter refusing 38% and 69% of REAL hard facts that the
  strict metric had hidden. Apply the lenient reading to every item group or to none. (measured 2026-10-25 and
  2026-11-10; `data/receipts/quant-abstention/RESULT_SAGE.md`, `data/receipts/sci-distill/RESULT_SCI_DISTILL.md`)

- **When most models agree on the same wrong answer, check the key before the models.** In M1, the items where at
  least 6 of 20 models gave one answer against the key held two keying errors (one graded 59 arms wrong for a right
  answer), five questions with two defensible answers and one that tested the training cutoff. Read every such item
  before a corpus is frozen. (measured 2026-11-17; `data/receipts/m1-item-audit/AUDIT_M1_ITEMS.md`)

## Agents

- **A loop is not always the same call twice.** In a 51-episode pilot (three 27B models, temperature 0, 30 steps), all
  13 episodes that ran out of budget were loops, but an exact-match detector saw 8: the other 5 re-issued one command
  with one more line appended each step. (measured 2026-11-09, corrected 2026-11-16;
  `data/receipts/agentic-gaming/RESULT_PILOT_v0.md`)
- **Seeds must change what the model sees.** The pilot's three seeds per cell changed only hidden grading cases, so
  each cell was one task run three times; rates over seeds overstated n. (measured 2026-11-09;
  `data/receipts/agentic-gaming/RESULT_PILOT_v0.md`)

## Seen, not yet measured

- Mark, 2026-11-16: has met the "same command plus a little more each step" loop in other harnesses before.
- Mark, 2026-11-10: adding temperature is his first fix for a runaway. One counter-case is on record: the science
  distill ran to the token cap on 19% of replies with sampling already on
  (`data/receipts/sci-distill/RESULT_SCI_DISTILL.md`); how often temperature rescues a runaway has not been measured.
