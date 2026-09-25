# Pre-registration -- the marker penalty on Bonsai 2 27B (ternary): does it cut the long thinking loops of a very low-bit model?

**2026-09-25, before any generation.** Follow-up to `RESULT_MARKER_PENALTY.md`, prompted by buun: "Q6 is completely
the wrong thing to test this with -- it's for quants that are so low bit that they fall into long thinking loops --
needs to be tested on bonsai 1bit!" Our own result pointed the same way: 0.86x at Q6_K (p = 0.32), 0.77x at
IQ3_XXS (p = 0.008).

**Prior art checked:** `ledger_precheck.py "logit bias penalty hesitation markers"` ->
- `marker-penalty/RESULT_MARKER_PENALTY.md` (Q6_K, IQ3_XXS);
- Bonsai 2 background: `lowbit-ladder/ANALYSIS_BONSAI_V1_VS_V2.md` (same base as Qwen3.8-27B; KLD valid);
  `agentic-ladder/RESULT_PA0_GATE.md` (Bonsai 2 PQ2_0 KLD 0.358, the most damaged arm, temp-0 byte-stable);
  `agentic-ladder/FINDING_BONSAI_TEMPLATE_DEFECT.md` (only `high` errors; `xhigh` and `medium` render
  byte-identically to stock); `lowbit-ladder/FINDING_BONSAI_SPEED.md` (PQ2_0 and PTQ1_0 agree to 3.2e-5; PQ2_0 is
  2.92x faster).

**What this adds:** the penalty on the regime the source targets, a model damaged enough to loop.

## Instrument (as `PREREG_MARKER_PENALTY.md` except the model and binary)

- **Model: `Ternary-Bonsai-2-27B-PQ2_0.gguf`** (7,206,168,928 B, sha256 `3907dc1658db1f78...`). It is the same ternary
  model as `PTQ1_0` (the "1-bit" container; the two agree to 3.2e-5 KLD), in the container that decodes 2.92x faster.
- **Binary:** the PrismML fork (`PrismML-Eng/llama.cpp` @ `prism`), `.194`'s fresh sm_60 build. The exact path and
  commit are recorded in `RUNLOG` at launch.
- `.194` as two 2-GPU testers, `-ngl 99 -c 16384 -np 1 -fa on --kv-unified -ctk f16 -ctv f16 -sm tensor --jinja`,
  `GGML_CUDA_ALLREDUCE=internal`. **Items are split between testers:** A1-A4 and U1-U4 on GPUs 0,1; A5-A8 and
  U5-U8 on GPUs 2,3. Every arm of an item runs on the same tester, so each paired comparison stays within one
  device-count-2 instrument.
- CAL tier, card sampling, `--effort xhigh`, `n_predict` 6144, 3 reps (seeds 1001-1003), arm order rotated per
  (rep, item).
- **Arms:** A = no penalty; B = `logit_bias` -2; C = -4 on the same 20 marker tokens (`marker_ids.json`; the token ids
  are shared with Qwen3.8, since Bonsai 2 uses the same tokenizer, and this is verified at launch).

## Predictions

| # | claim | test | conf |
|---|---|---|---:|
| B1 | C shortens Bonsai's thinking | arm C / arm A geometric-mean per-item thinking < 0.80, exact sign-flip p < 0.05 over 16 items | 0.60 |
| B2 | C cuts runaways | NO-STOP (`finish == length`) count in C < A (descriptive: counts too small to test) | 0.50 |
| B3 | no calibration cost | answerable correct >= A - 2 (of 24), unanswerable WRONG + NO-STOP <= A + 2 | 0.60 |
| B4 | the source's accuracy gain appears | answerable correct in C >= A + 2 (they report +14 pts on MATH-500 at 3-bit AWQ) | 0.30 |

Same scorer as the Q6_K/IQ3_XXS run (`analyze_marker.py`, adapted to one model), with the same NO-STOP sensitivity
reported alongside.

**Reading:**
- B1 true with B3 true -> buun's reading holds: a free length control for very low-bit models.
- B1 false -> the penalty does not reach Bonsai's loops.
- B4 true -> the source's accuracy claim transfers to ternary weights.

## Not established by design

16 items, `xhigh` only, one very-low-bit model, and PQ2_0 as a stand-in for PTQ1_0 (equal fidelity per the
lowbit-ladder receipt).
