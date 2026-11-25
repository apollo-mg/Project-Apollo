# RESULT: with both models reasoning, Qwen3.8-27B declines more invented questions than Inkling-2-Mini (88 vs 78) and knows more (44 vs 33 hard right) -- Inkling's apparent caution was the reasoning; reasoning alone moves Qwen from 59 to 88 declined

**Prereg:** `PREREG_Q27_LOW.md` (`3f0aaac5`, before any row). **Run:** 2026-11-25 10:32-12:11 EST, .73 (2x P100), mainline
`33aeb17f8`, Qwen3.8-27B Q8_0 (`a680f44a...`), thinking on, `reasoning_effort` "low", 4,096 tokens, greedy.
**Preflight passed:** the rendered prompt carried "Reasoning effort is set to low. Keep your thinking brief and focused..."
and ended in an open `<think>`. **Records:** `quant-abstention/raw/main_Q27LOW.jsonl`, `raw/state_q27low.log`,
`raw/server_Q27LOW.log`, `raw/run_Q27LOW.log`. **Analysis:** as `analyze_ink.py` (bare-answer rule; paired bootstrap over
items, 10,000, seed 20261125), numbers below.

| | invented declined | invented answered | hard right / wrong / declined | easy right | unfinished | median tokens |
|---|---|---|---|---|---|---|
| Qwen3.8-27B thinking off (DR27_N73) | 59 | 39 | 48 / 49 / 3 | 33 | 2 | 58 |
| **Qwen3.8-27B thinking low (Q27LOW)** | **88** | 12 | 44 / 48 / 8 | 34 | 0 | 190 |
| Inkling-2-Mini minimal (INK) | 78 | 6 | 33 / 43 / 18 | 33 | 22 | 350 |

Q27LOW - DR27_N73: invented declined **+0.29 [+0.20, +0.38]**, hard right -0.04 [-0.12, +0.03].
INK - Q27LOW: invented declined -0.10 [-0.20, +0.00], hard right -0.11 [-0.22, +0.00].

| prediction | result |
|---|---|
| Q1 reasoning raises Qwen's declining above 59 (0.65) | **holds:** 88 |
| Q2 Q27LOW declines fewer invented questions than INK's 78 (0.5) | **fails:** 88 |

## Reading

1. **Reasoning is the lever.** Brief reasoning took Qwen3.8-27B from declining 59 invented questions to 88 at no
   significant cost in facts (44 vs 48 hard right). On M1, as on Qwen3.5-9B before (0.68 -> 0.94), thinking makes this
   family far more willing to say "I don't know" -- the opposite of what thinking did on AbstentionBench, a broader
   benchmark.
2. **Inkling's caution was mostly its reasoning.** Matched for reasoning, Qwen declines more invented questions and knows
   more facts. Inkling still invents fewer answers (6 vs 12); its lower decline count comes from 16 invented items where
   greedy decoding sent its reasoning into a repetition loop until the cap.
3. So the Inkling card's warning, "more likely than larger models to state incorrect information with confidence", is
   not borne out against Qwen3.8-27B on made-up questions (6 vs 12 invented answers), while its "largest gaps on factual
   recall" is (33 vs 44).

## Limits

The two lowest settings differ (Qwen "low" injects an instruction to keep thinking brief; Inkling "none" a system line
"Thinking effort level: 0"); greedy decoding provokes Inkling's loops; one run each.
