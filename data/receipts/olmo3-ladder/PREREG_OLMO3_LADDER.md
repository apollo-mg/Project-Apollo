# PREREG: one model through its training stages -- Olmo 3 7B Instruct after SFT, after DPO, after RL (2026-11-25, before any M1 row)

**Why (Mark, 11-22 and 11-25):** the RL page's open question, "a model fine-tuned with examples first and RL after (does
the drop come back?)". AllenAI publishes every stage of Olmo 3 7B Instruct from one base: Instruct-SFT (supervised
fine-tuning), Instruct-DPO (plus preference tuning), Instruct (plus RL with verifiable rewards: math, code, instruction
following). Mark: tuners would "love to see how different training affects the models". **Prior art checked:**
`ledger_precheck.py "SFT DPO RL stages same model abstention ladder"` -> the seven-variant series (RL-only variants kept
refusal, SFT variants cut it; `abstend/FACT_SHEET_FINETUNE_SERIES.md`), the frozen-layers and IDK-LoRA controls; no
stage-by-stage measurement of one model. **What this adds:** the same base through SFT, DPO and RL.

## Smoke seen before this prereg (non-M1 questions; `raw/` and the session notes)

- The three Instruct checkpoints answer in M1's format (Instruct-SFT: "The capital of Australia is Canberra.", and
  "UNKNOWN" for an invented country). Their chat templates render identically without tools.
- **Not scorable, reported as observations:** RL-Zero-General (RL from the base, no SFT; an LM-judge reward on general
  chat; AllenAI calls the family experimental) never ends its turn under M1's prompt: it answered, then wrote to the
  4,096-token cap, also with `<|im_start|>` treated as end-of-turn; on an invented question it gave no answer line. The
  base (no chat template; the SFT template borrowed) does not follow the answer format and parroted the instructions.

## Arms (desktop RX 9070 XT; mainline `33aeb17f8` build on ROCm 10.1 with Arch's HIP runtime, `tools/rocm101arch.sh`)

`OL_SFT`, `OL_DPO`, `OL_RL`: each checkpoint converted to Q8_0 by the same converter (`convert_olmo3.sh`; sha256 in
`raw/convert.log`), server `-ngl 99 -c 16384 -ctk f16 -ctv f16 -np 1 --jinja --cache-ram 0`, fresh per arm; M1 240 items,
greedy, `run_main.py --max-tokens 1024 --usage --no-think-check` (these templates have no think block). Bare-answer rule.

## Predictions

- **P1 (RL changes little outside its reward):** the final RL stage moves invented-question declining by at most 5
  points against DPO: |OL_RL - OL_DPO| <= 0.05. Confidence 0.6.
- **P2:** preference tuning makes the model decline fewer invented questions than SFT alone (OL_DPO < OL_SFT).
  Confidence 0.55.
- **P3 (no stage adds facts):** hard right differs by at most 5 between SFT and the final model. Confidence 0.6.
- Reported without prediction: every pairwise difference (bootstrap over items, 10,000, seed 20261125), wrong answers,
  easy right, unfinished, output length.

## Limits stated now

No base anchor (the base cannot do M1's format), so this measures what each stage after SFT changes, not what SFT did to
the base; one model family at 7B; greedy, thinking off; one quant; M1 is short factual English questions.

## Deviation 1 (2026-11-25 ~19:30 EST; the first attempt's 55 partial rows per arm were set aside unread)

The first attempt (`raw/attempt1/`) stopped at item 55 in OL_SFT and OL_DPO: `run_main.py`'s optional slot readout (a
forced "Exact Answer:" completion read for token probabilities, not used in grading) got no `completion_probabilities`
back. OL_RL never started: llama.cpp could not parse the final model's chat template (its `tools is none` test meets
`tools` as undefined, falls into the tools branch, and `tojson` fails). Changes: every arm adds `--skip-slot`; OL_RL is
served with the SFT/DPO template file (`olmo3_instruct_sft_template.jinja`), which differs from its own only in that
tools test -- rendered with jinja2 and no tools, M1's prompt comes out byte-identical through all three templates. All
three arms rerun from scratch. Nothing else changes.
