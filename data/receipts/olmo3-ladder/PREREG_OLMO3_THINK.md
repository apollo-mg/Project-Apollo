# PREREG: the reasoning branch of the same model -- Olmo 3 7B Think after SFT, after DPO, after RL (2026-11-25, before any M1 row)

**Why (Mark, 11-25):** the Instruct ladder (`RESULT_OLMO3_LADDER.md`) found the RL stage left declining where DPO put it,
and DPO's largest change was a format habit (a trailing "UNKNOWN" line on 119 of 240 items). AllenAI publishes the
reasoning branch from the same base too: Think-SFT, Think-DPO, Think (RL). Mark: "let's grab the others and do it."
**Prior art checked:** `ledger_precheck.py "thinking model training stages SFT DPO RL abstention reasoning ladder"` ->
the Instruct ladder (today) and reasoning raising declining on this instrument (Qwen3.5-9B 0.68 -> 0.94,
`quant-abstention/RESULT_SAGE.md`; Qwen3.8-27B 59 -> 88, `inkling-mini/RESULT_Q27_LOW.md`); no stage-by-stage
measurement of a reasoning model. **What this adds:** the same stages on a reasoning branch, and whether DPO's habit
recurs there.

## Smoke seen before this prereg (six fresh non-M1 questions; `raw/smoke_think.*`, `raw/smoke_reasoning_format.jsonl`)

- The template opens `<think>` itself and ignores `enable_thinking`. llama.cpp `33aeb17f8` does not split the reasoning
  out (`reasoning_content` empty with `--reasoning-format` none or deepseek); the output is reasoning, `</think>`, then
  "Exact Answer: ...". `run_main.py --split-think` (added for this, default off) splits at the last `</think>` the way
  the server does for templates it parses, so grading works as in every earlier thinking arm: the answer comes from the
  text after `</think>`; an output that never closes its reasoning has empty content and counts as unfinished.
- All three checkpoints, 18 answers (21:38-21:48): every one ended its turn, closed its reasoning exactly once and gave an
  "Exact Answer:" line; 150 to 4,950 tokens (the longest on an invented element), so the 16,384 cap leaves room. All
  three got the four real questions right. On the invented element Think-SFT answered "51"; Think-DPO and Think said
  UNKNOWN. All three said UNKNOWN for an invented bridge engineer. (Two invented questions; no M1 item.)

## Arms (desktop RX 9070 XT; mainline `33aeb17f8` on ROCm 10.1 with Arch's HIP runtime, `tools/rocm101arch.sh`)

`TH_SFT`, `TH_DPO`, `TH_RL`: Olmo-3-7B-Think-SFT, -Think-DPO, -Think, each converted to Q8_0 by `convert_olmo3.sh`
(sha256 in `raw/convert.log`). Server `-ngl 99 -c 32768 -ctk f16 -ctv f16 -np 1 --jinja --cache-ram 0`, fresh per arm.
M1 240 items, greedy, `run_main.py --max-tokens 16384 --thinking --split-think --skip-slot --no-think-check --usage
--timeout 1800`. Bare-answer rule. The vendor samples at temperature 0.6; greedy is this instrument's rule for every arm
and may provoke repetition loops (Inkling-2-Mini: 22 of 240), counted as unfinished.

## Predictions

- **T1 (RL changes little outside its reward, replicated on the reasoning branch):** |TH_RL - TH_DPO| invented declined
  <= 0.05. Confidence 0.5 (the Think RL stage is longer than the Instruct one).
- **T2 (the reasoning branch declines more):** each Think stage declines more invented questions than the matching
  Instruct stage (TH_SFT > OL_SFT 17, TH_DPO > OL_DPO 27, TH_RL > OL_RL 29). Confidence 0.7. This compares two training
  branches, not one model with thinking switched on and off.
- **T3 (no stage adds facts):** hard right differs by at most 5 between TH_SFT and TH_RL. Confidence 0.6.
- **Reported without prediction:** every pairwise difference (bootstrap over items, 10,000, seed 20261125); wrong
  answers, easy right, unfinished, tokens spent (median, and per item group); the trailing-UNKNOWN count per arm and item
  group by `hedge_counts.py`'s rule as committed (`df386734`; an `--arms` option added since, rule unchanged and its
  Instruct output reproduced byte for byte), now registered for these arms, applied to the text after `</think>`; and
  whether the three Think templates render M1's prompt to the same token count (Think-SFT's template comes from its
  tokenizer config, the other two from `chat_template.jinja`).

## Limits stated now

No base anchor; one family at 7B; greedy at a vendor temperature of 0.6; one quant; a 16,384-token cap (the vendor's
generation config allows 32,768); M1 is short factual English questions.

## Amendment 1 (2026-11-27 ~14:00 EST, after the registered results, before any row of the new arm; Mark's OK)

`RESULT_OLMO3_THINK.md` found Think-SFT's own template carries a different default system message from Think-DPO and
Think (19 tokens shorter, no "function-calling" wording or no-functions line, cutoff "December" vs "November 2024"). New
arm `TH_SFT_T`: Think-SFT served with the Think-DPO template file (`olmo3_think_dpo_template.jinja`, byte-identical to
Think's), everything else as `TH_SFT`. **Gate:** its prompt token counts equal TH_DPO's on 240 of 240 items.
**Prediction A1 (the system message is not what moved SFT -> DPO):** |TH_SFT_T - TH_SFT| invented declined <= 0.05.
Confidence 0.6. **Reported without prediction:** the paired difference (bootstrap as registered), loops to the cap,
finished-only declining, and TH_DPO - TH_SFT_T as the system-message-matched DPO step.
