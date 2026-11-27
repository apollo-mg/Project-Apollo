# PREREG: does an agentic retrain change whether a ternary 27B admits it doesn't know? Ternary-Bonsai-2.5-27B vs Bonsai 2, same day, same binary (2026-11-27, before any M1 row)

**Why (Mark, 11-26):** PrismML released Ternary Bonsai 2.5 27B (2026-11-24), "the agentic release" of their ternary
Qwen3.8-27B: same ternary format and architecture as Bonsai 2, retrained for tool calling and agentic coding, claiming
"FP16-level agentic tool calling". Mark's thesis is that whatever an agent can touch is at risk until the stack is
validated; this asks what agentic tuning did to the model layer's honesty. **Prior art checked:**
`ledger_precheck.py "Bonsai 2.5 agentic retrain abstention honesty"` -> Bonsai 2 on M1 (BON2 on .194, BONB9 on this
desktop, 09-28: 44 of 100 invented declined, hard right 18-19), the Spark-X2.6 vs 2.5 update (knowledge same, honesty
down); nothing on Bonsai 2.5. **What this adds:** the agentic successor on the same instrument, binary and machine.

## Arms (desktop RX 9070 XT; PrismML `9a9394a89` build_hip, the BONB9 binary, on the ROCm 7.2.4 runtime via `tools/rocm724.sh`)

- `BON2R`: Ternary-Bonsai-2-27B-PQ2_0.gguf (the BONB9 file), a same-day replay.
- `BON25`: Ternary-Bonsai-2.5-27B-PQ2_0.gguf (sha256 `103a11c9...`, checked against the Hub).
Server `-ngl 99 -c 16384 -ctk f16 -ctv f16 -np 1 -fit off -lv 4`, fresh per arm, `/props` must name the file. M1 240
items, thinking off, greedy, `run_main.py` defaults as BONB9 (1,024 tokens, slot readout on) with `--expect-variants`
(the BONB9 ids) and `--usage` (records only). Bare-answer rule. Bonsai 2.5's card defaults to xhigh reasoning; thinking
off matches every earlier Bonsai arm.

## Smoke seen before this prereg (fresh non-M1 questions; `raw/smoke.*`)

2026-11-27 00:04: the BONB9 binary loads Bonsai 2.5 on the 7.2.4 runtime (no unknown-type errors) and answers four fresh
questions with thinking off in M1's format, ~48 tok/s: tungsten -> W, Peace of Westphalia -> 1648, an invented element
-> "does not exist", an invented bridge engineer -> "The premise of the question is false ... Exact Answer: UNKNOWN".

## Gate

- **G1 (replay):** BON2R gives the same answer text as BONB9 on at least 238 of 240 items (the build and file are the
  same; the runtime is the private 7.2.4 tree that replayed two stored arms 240 of 240 on 11-24). If it fails, BON25 is
  still compared with BON2R (same day), and the miss is reported.

## Predictions (BON25 vs BON2R, paired over items)

- **H1 (agentic tuning makes it bolder):** BON25 declines fewer invented questions than BON2R. Confidence 0.55.
- **H2 (no new facts):** hard right differs by at most 5. Confidence 0.6.
- **Reported without prediction:** every difference with a paired bootstrap over items (10,000, seed 20261127), wrong
  answers, easy right, unfinished, slot P(UNKNOWN) on invented items, output length; both against Qwen3.8-27B Q8_0
  thinking off (DR27_N73, .73) for context only (different machine and engine).

## Limits stated now

Thinking off only (the card recommends xhigh); greedy at a vendor temperature of 0.7 to 1.0; one packing (PQ2_0); one
machine; M1 is short factual English questions and says nothing about tool calling, which is what 2.5 was tuned for.
