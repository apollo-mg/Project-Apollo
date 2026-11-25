# PREREG: Qwen3.8-27B with thinking on at low effort -- the same-condition reference for Inkling-2-Mini (2026-11-25, before any row)

**Why (Mark, 11-25):** Inkling-2-Mini at minimal reasoning declined 78 of 100 invented questions where Qwen3.8-27B with
thinking off declined 59 (`RESULT_INKLING_MINI.md`), but Inkling cannot switch reasoning off, so the gap may be the
reasoning, not the model. "Qwen 27B w/thinking on low is probably a data point worth having." **Prior art checked:** no
stored M1 arm of Qwen3.8-27B with thinking on (header search of `quant-abstention/raw/main_*.jsonl`); on AbstentionBench,
thinking on made Qwen3.8-27B abstain slightly LESS (INDEX, recall 0.520 -> 0.476), while on M1 thinking made Qwen3.5-9B
refuse invented items more (0.68 -> 0.94, `quant-abstention/RESULT_SAGE.md`). **What this adds:** Qwen3.8-27B reasoning on
M1, matched to Inkling's setting as closely as the two templates allow.

## The arm

**Q27LOW**: Qwen3.8-27B Q8_0 (sha256 `a680f44a...`, the file behind DR27_N73, on .73's HDD), .73 both P100s, mainline
`33aeb17f8`, server flags exactly as DR27_N73 (`-ngl 99 -sm layer -fit off -c 16384 -ctk f16 -ctv f16 -np 1 --jinja
--cache-ram 0`). `run_main.py --thinking --template-kwargs '{"reasoning_effort": "low"}' --max-tokens 4096 --timeout 900
--skip-slot --usage`, greedy; graded on `content` with the bare-answer rule, as INK.

The template's "low" (its lowest level; supported are xhigh, medium, low) injects a system sentence: "Reasoning effort is
set to low. Keep your thinking brief and focused, moving directly to the conclusion without unnecessary elaboration."
**Preflight:** `/apply-template` with `enable_thinking: true, reasoning_effort: "low"` must contain that sentence and must not
end in a closed (empty) think block, which is what thinking off renders; logged, and the run stops otherwise.

## Predictions

- **Q1:** reasoning raises Qwen's declining: Q27LOW declines more invented questions than DR27_N73 (more than 59).
  Confidence 0.65.
- **Q2:** Inkling's caution is not only its reasoning: Q27LOW declines fewer invented questions than INK (fewer than 78).
  Confidence 0.5.
- Reported without prediction: hard right / wrong / declined, easy right, unfinished, reasoning tokens per item; paired
  differences Q27LOW - DR27_N73 and INK - Q27LOW (bootstrap over items, 10,000, seed 20261125).

## Limits stated now

The two models' lowest settings are not the same thing (Inkling "none" emits a system line "Thinking effort level: 0";
Qwen "low" an instruction to keep thinking brief); greedy only; one run.
