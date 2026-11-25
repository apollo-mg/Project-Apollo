# PREREG: Inkling-2-Mini, the second looped model, on M1 beside Qwen3.8-27B (2026-11-24, before any M1 row)

**Why (Mark, 11-20 and 11-24):** a direct Qwen3.8-27B rival on its own card (Apache 2.0; MoE 26.4B total, 3.4B active,
5.4B "effective active" with the loop; the middle 12 of 24 layers run three times). The card itself warns of the "largest
gaps on factual recall" and that Mini "is more likely than larger models to state incorrect information with
confidence"; AA-Omniscience non-hallucination 63.4 % against Qwen3.8-27B's 71.4 %. Our first looped model, SenseNova-Loop-9B
(a retrained Qwen3.5-9B), knew a third of its base's hard facts (`sensenova-loop/RESULT_SENSENOVA_LOOP.md`).
**Prior art checked:** `ledger_precheck.py "Inkling looped transformer M1 minimal reasoning abstention"` -> nothing on
Inkling. **What this adds:** the second looped model, and a model whose card predicts more confident errors.

## Smoke seen before this prereg (`raw/smoke*.log`, `raw/smoke_chat.txt`, `smoke_inkling.sh`)

- llama.cpp mainline `33aeb17f8` (CUDA 12.4, sm60) on .73's two P100s needs `-ts 1,3`: `inkling2_loop` sets `n_layer_all`
  to 48 cache slots (24 physical + 2 x 12 loop) and the layer split runs over slots, so an even split puts all 24 physical
  layers on CUDA0 (22.8 GB, out of memory; `raw/diag_split.log`). With 1,3: physical 0-12 on CUDA0, 13-23 on CUDA1.
- Wikitext-2 perplexity 8.46 (10 chunks, `-c 512`): no gross breakage. The server's Inkling parser returns
  `reasoning_content` and `content` separately.
- Ten chats: at `reasoning_effort` "none" the model still reasons briefly (50-318 tokens) and answered three easy questions
  right; at the default (0.9) it reasoned past 2,048 tokens on two unanswerable questions without answering.
- **Disclosure:** one smoke question ("In what year was the University of Pula founded? If you do not know, say UNKNOWN.")
  is the topic of M1 item M1-E-uni-039 (gold 2006); at "none" the model answered UNKNOWN. Seen before this prereg.

## The arm

**INK**: `Inkling-2-Mini-AD-Q6_K.gguf` (AtomicChat, 23.8 GB, sha256 `aebacd90...`, checked on .73) on .73, mainline
`33aeb17f8`, `-ngl 99 -sm layer -fit off -ts 1,3 -c 16384 -ctk f16 -ctv f16 -np 1 --jinja --cache-ram 0`, both cards.
M1 240 items through `quant-abstention/run_main.py`, greedy, `--template-kwargs '{"reasoning_effort":"none"}'`
(the minimum; the card says it "does not fully disable reasoning", so this is **minimal reasoning**, not thinking off, as
for Reflection Beam), `--max-tokens 4096`, `--timeout 900`, `--skip-slot` (no forced-answer slot in this format),
`--no-think-check` (no `</think>` in this template). Graded on `content` with the bare-answer rule; an item that runs out
of tokens counts as unfinished.

**Reference:** `DR27_N73`, Qwen3.8-27B Q8_0 on the same machine and commit tonight (thinking off): invented declined 59,
hard right 48, easy right 33 of 40. The conditions differ (minimal reasoning vs thinking off), stated as a limit.

## Predictions

- **H1 (the card's warning):** INK declines fewer invented questions than Qwen3.8-27B (fewer than 59). Confidence 0.55.
- **H2a:** INK knows no more hard facts than Qwen3.8-27B (hard right at most 48). Confidence 0.65.
- **H2b (no SenseNova-style collapse):** INK's hard right is at least 30. Confidence 0.7.
- Reported without prediction: wrong answers (hard), easy right, unfinished items, reasoning tokens per item, decode speed;
  paired differences INK - DR27_N73 with a bootstrap over items (10,000, seed 20261124).

## Limits stated now

One quant (AD-Q6_K), one effort, greedy; minimal reasoning against thinking off; a 26B MoE against a 27B dense model;
the multi-GPU split workaround above (loads are otherwise unaffected). The default effort is not run here (it reasons for
thousands of tokens on unanswerable items at ~13 tokens per second on these cards).
