# Qwen3.8-27B

The dense 27B that anchors the scorecard (its Q8_0 is the "ceiling" other files are compared with) and serves the
daily on .73. The rows below span several files, so every line names its quant. The live serving settings are in
`STATUS.md` and are not repeated here. Line rules: `compendium/README.md`.

## Honesty and knowledge (the vocabulary test, M1)

- **The Q8_0 anchor, thinking off:** hard facts right 0.50, easy facts right 0.85, invented questions refused 0.60.
  Scope: Q8_0 (sha256 `a680f44a...`), 240 items, greedy, a two-P100 lane on .194. A same-day replay matched the
  stored arm byte for byte, 240 of 240.
  (measured 2026-11-08; `data/receipts/arete/RESULT_ARETE.md`)
- **Fine-tunes of it refuse less and know no more.** Arete-27B against this base, both Q8_0, prompts token-identical:
  hard 0.50 against 0.50, invented refused 0.48 against 0.60 (-0.12 [-0.18, -0.06]). It was the fifth fine-tune in the
  catalogue to cut refusal with no gain in knowledge. (measured 2026-11-08; `data/receipts/arete/RESULT_ARETE.md`)
- **Quantizing it moves the threshold, not the ranking, and the direction belongs to the file.** 23 files at 2.5 to 4.5
  scored bits per weight kept the ranking of answerable against unanswerable items (within 0.03 of Q8_0 in 19 of 20
  post-training quants) while shifting how readily the model says "I don't know", some files up and some down. Do not
  carry a refusal rate from one quant of this model to another. (measured 2026-09-27;
  `data/receipts/quant-abstention/RESULT_MAIN.md`)
- **An older, smaller model recalls more obscure facts.** Llama 3.1 8B beat the Q8_0 anchor on hard recall by 0.14
  [0.04, 0.24]. Size and date do not order models on this test. (measured 2026-10-31;
  `data/receipts/abstend/llama-3.1-8b-instruct/RESULT_llama-3.1-8b-instruct.md`)

## Thinking and effort

- **`enable_thinking: false` still switches thinking off,** although the template's dial moved to `reasoning_effort`:
  thinking fired on 0 of 492 requests with it false and 492 of 492 with it true. Scope: IQ2_M. `--reasoning-budget 0`
  does NOT stop this template thinking. (measured 2026-08-17 and 2026-09-11;
  `data/receipts/qwen38-hep-thinking/PREDICTION_Q6K_THINKOFF.md`,
  `data/receipts/svgbench-pelican3/RESULT_LOCAL_VLM_GRADER.md`)
- **`xhigh` effort is worse than `medium` at knowing when to stop.** At the model's published sampling, on 24
  unanswerable items: made-up answers 6 against 3, replies that never stopped 5 against 0; answerable items 24 of 24
  either way. Published hallucination figures for this model do not state the effort they used. (measured 2026-09-07;
  `data/receipts/viability/RESULT_A6_EFFORT_NOT_SAMPLING.md`)

## As an agent

- **In a 51-episode pilot it took no shortcut and never stopped on its own.** Scope: Q8_0, thinking off, temperature
  0, a 30-step budget, two task shapes shared with two of its fine-tunes (three models on two tasks, so a hint and not
  a rate). It solved the easy task in five calls, failed the hard one (two incomplete solutions, one loop), and on the
  impossible task looped until the budget ended in 3 of 3 episodes. (measured 2026-11-09, corrected 2026-11-16;
  `data/receipts/agentic-gaming/RESULT_PILOT_v0.md`)
- **Whether its MTP head helps or hurts agent outcomes is unsettled: two runs disagree.** Scope: IQ3_XXS, 40 agent
  items, 3 seeds. Prompt cache off: 75.0% without MTP against 69.2% with (-5.8 points, p = 0.12). Prompt cache on:
  +9.2 points for MTP (p = 0.0098) and tasks finished 17% faster. Neither supersedes the other. (measured 2026-09-24;
  `data/receipts/mtp-agentic/RESULT_MTP_AGENTIC.md`, `data/receipts/mtp-agentic/RESULT_MTP_AGENTIC_SPEED.md`)

## Other uses

- **It is a repeatable local vision grader.** With `mmproj-F16` on the desktop card, thinking off, temperature 0: 15 of
  15 images scored identically across three repeats, about 1.0 s per grade. (measured 2026-09-11;
  `data/receipts/svgbench-pelican3/RESULT_LOCAL_VLM_GRADER.md`)
