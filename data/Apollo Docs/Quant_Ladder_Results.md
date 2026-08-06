# The Qwen3.6-27B Quant Ladder — quality vs true full precision (BF16)

**Date:** 2026-07-13. **Rig:** 4× Tesla P100, `.194`. **Build:** `build_carveout` (stock 9967
`4f37f5197`, sm_60 carve-out — fp32-clean arithmetic). **Reference:** BF16 native weights (not a
Q8 proxy), truth base PPL 6.5376. **Protocol:** wikitext-2 (md5 7c0137fc…), 2048 ctx, 32 chunks,
f32 KV, FA off, `-ub 128`. All tiers unsloth. **Receipts:** `.194:~/quant_ladder/kld_ladder_*.log`.

## The ladder (every tier vs BF16 truth)

| Tier | GiB | Same-top % | Median KLD | 99.0% KLD | 99.9% KLD | PPL | ln PPL/base |
|------|----:|-----------:|-----------:|----------:|----------:|----:|------------:|
| *BF16 (base)* | 50 | — | — | — | — | *6.5159* | *0* |
| Q8_0   | 27 | **99.197** | 0.000103 | 0.0104 | 0.895 | 6.5334 | +0.0027 |
| Q6_K   | 21 | **98.033** | 0.000707 | 0.0440 | 3.93 | 6.5679 | +0.0080 |
| Q5_K_M | 19 | **97.074** | 0.001503 | 0.1118 | 7.35 | 6.5825 | +0.0102 |
| Q4_K_M | 16 | **94.917** | 0.004780 | 0.3362 | 10.14 | 6.6463 | **+0.0198** |
| Q3_K_M | 13 | **90.637** | 0.018433 | 1.0482 | 15.24 | **6.4370** | **−0.0122** |

(Max KLD is ~24–29 flat across all tiers — every quant has ~1 pathological token it butchers;
that's token/model-inherent, not a quant signal. The 99.0/99.9 percentiles are the tail signal.)

> ⚠️ **The PPL column inverts this table.** By perplexity, Q3_K_M is the *best* model in the ladder
> — better than Q4, better than Q8, at parity-or-better with the BF16 it was quantized from — while
> by every distributional metric it is by far the most damaged. This is not the chunk-7 outlier
> (the inversion survives excluding it) and not a file mix-up (both ruled out). Read
> **`Instrument_Disagreement_PPL_vs_KLD.md`** before quoting any number from this document. A lower
> perplexity is not evidence of a better model, and our own Q3 is the proof.

## Finding 1 — the same-top curve has a knee at Q5→Q4

Per-step same-top drop: Q8→Q6 −1.16, Q6→Q5 −0.96, Q5→Q4 **−2.16**, Q4→Q3 **−4.28**. The cost
per tier roughly *doubles* below Q5. Median KLD is even sharper — it ~quadruples per step at the
low end (Q6 0.0007 → Q5 0.0015 → Q4 0.0048 → Q3 0.0184). Bits get expensive fast below Q5.

## Finding 2 — writing and agentic are DIFFERENT curves, and the tail is ~10× steeper

This is the quantified "Q4 feels lossless but breaks tools":
- **Writing proxy (same-top / bulk):** Q8 99.2% → Q4 94.9% — a gentle ~4-point slide over the
  whole range. Q4 keeps ~95% of greedy tokens, which is why prose *feels* fine.
- **Agentic proxy (99.0% KLD — the hardest 1% of tokens, where JSON/schema structure lives):**
  Q8 0.010 → Q4 0.336 — a **32× explosion** over the same range; Q8→Q3 is a **100× blowup**.

The identical quant step that costs ~4 points of writing quality costs 32× on the structural-token
divergence. The tokens that carry tool-call structure are exactly the low-confidence tail tokens
quantization damages first. Same model, two metrics, opposite-severity stories.

## Finding 3 — the two floors, located (Mark's thesis, measured)

- **Writing floor ≈ Q4.** Same-top still 94.9%, prose-tolerable; the bulk distribution holds.
- **Agentic floor ≈ Q6.** The tail (99.0% KLD) is gentle only Q8→Q6 (0.010→0.044); it starts
  climbing hard at Q5 (0.112) and is 8× the Q6 value by Q4 (0.336). If a single mangled structural
  token kills a tool call and cascades context, Q6 is where the tail is still contained. This
  matches the well-informed-user consensus ("Q6, maybe Q5 on better models") — now with a curve
  under it instead of vibes.

## Finding 4 — Q8_0 is NOT lossless vs true precision

Q8 loses **0.8% of greedy tokens vs BF16** (99.197% same-top). By median KLD (0.000103) it's
near-perfect, but 1-in-125 greedy tokens still flips vs full precision. Consequence: the earlier
W1 / publisher-panel numbers scored *against a Q8 reference* were measuring against a base that
itself sits 0.8% off truth. It barely moved Q4 (94.86% vs Q8 → 94.917% vs BF16 — Q4's own error
dwarfs Q8's 0.8%), but it means "vs Q8" understates Q6/Q8's true distance. The BF16 base is the
honest reference and retroactively justifies building it.

## Predictions scored (logged pre-run)

- Same-top values: Q4 94.7% pred → **94.9%** (spot on); Q5 97.5 → 97.1 (close); Q3 89 → 90.6
  (under 1.6); Q6 99 → 98.0 (over 1); **Q8 99.8 → 99.2 (WRONG by 0.6 — I overrated Q8's
  losslessness; see Finding 4).** Net: good on the middle, wrong that Q8≈perfect.
- **Shape (knee at Q5→Q4): CORRECT.**
- **Tail degrades faster than same-top: CORRECT, and stronger than expected** (~10× the relative
  rate — 32× tail explosion vs 4-point bulk slide across Q8→Q4).

## Tool-call floor — MEASURED, and it's below Q3 for greedy single-turn (2026-07-14)

Ran an in-house function-calling benchmark (v2: 24 hard cases — mandatory-use w/ distractors,
near-identical function disambiguation, nested/complex args, parallel multi-calls; objective
AST-style scoring; per-category) across the full ladder, served on .194 (build_puzzle,
`--reasoning off`, temp 0). **Result: ALL FIVE TIERS 24/24 (100%), every category, Q3 included.**

| tier | overall | mandatory | disambig | nested | parallel |
|---|---|---|---|---|---|
| Q3_K_M | 24/24 | 6/6 | 7/7 | 6/6 | 5/5 |
| Q4_K_M | 24/24 | 6/6 | 7/7 | 6/6 | 5/5 |
| Q5–Q8 | 24/24 | 6/6 | 7/7 | 6/6 | 5/5 |

**Prediction FALSIFIED** (I bet nested/parallel would degrade at Q4/Q3). And it overturns the
KLD-tail hypothesis: Q3's 99.0%-KLD tail is ~100× Q8's, yet tool-calling is untouched. Why —
**tool-call tokens are the high-confidence, argmax-stable subset.** The tail damage lands on
low-confidence tokens (prose, reasoning), which is why same-top drops to 90.6% at Q3; but the
function name and required arg values are high-confidence, so at temperature 0 the argmax holds
even with a mangled tail. The 9% of flipped tokens simply aren't the tool-call tokens.

**This does NOT contradict the well-informed "Q5-Q6 agentic floor" intuition — it locates where
that floor actually lives.** It is NOT in single-turn greedy call *structure*. It is in the
regime this test didn't sample:
- **Temperature > 0** — real agents sample (0.6-0.7); sampling can *hit* the damaged tail, where
  greedy argmax dodges it. A temp sweep is the direct test.
- **Multi-turn cascades** — the "1% lows" compound over a 20-step trajectory; one clean call ≠ a
  session. Single-turn can't see this.
- **Weaker/smaller base models** — Qwen3.6-27B is a strong tool-caller; a 7B or a brittle quant
  family may show degradation these 24 cases can't elicit here.

**Honest limitation: the test hit a ceiling (all 100%) → it cannot *locate* a floor, only bound
it below Q3 for this regime.** Same ceiling problem as v1, one level up: even "hard" single-turn
cases are quant-robust. Also possible: llama.cpp grammar-constrained tool decoding guarantees
valid JSON *structure* regardless of quant — but the disambiguation/arg-value cases test the
model's *choices* (not grammar-forced), and those pass at Q3 too, so the decision-making is
genuinely robust, not just the structure.

**Verdict for deployment:** for greedy, single-turn, well-specified tool calls, **even Q3 is
safe** on this model — a stronger statement than "Q6 floor." The agentic risk is real but lives
in sampling temperature and trajectory length, not single-call fidelity. Next probe to actually
find the floor: temperature sweep (0/0.4/0.7) at Q3/Q4, and/or a multi-turn trajectory harness.
Receipts: `.194:~/quant_ladder/bench_*.json`, benchmark `scratchpad/toolcall_bench.py` (reusable —
module 1 of the in-house suite).

## Temperature sweep — tool-calling robust even under sampling (2026-07-14, Gemini-run/Fable-verified)

Swept temp {0.0, 0.4, 0.7} × tiers {Q3, Q4, Q8_0 control}, tool-call bench, temp>0 at 5 reps
(stochastic → pass-rate). **Result: ALL 9 configs 24/24 or 120/120 = 100%, every category, incl.
Q3 at temp 0.7 over 120 samples.** Prediction (Q3/Q4 degrade at 0.7) FALSIFIED.

**Validity check (Fable, essential for a "too-clean" all-100% result): temperature IS honored.**
A controlled variance probe on Q4 — free-gen at temp 0.0 vs temp 1.8 (min_p=0, top_k=0) —
returned a coherent sentence at 0.0 and **degenerate token-soup at 1.8**, the unmistakable
signature of real high-temp sampling. So the null result is genuine, not a param-ignored artifact.

**Precise finding + the caveat that bounds it:** at realistic agent sampling (temp 0.4-0.7 with
llama-server's **default min_p=0.05**), tool-call reliability is quant-robust to Q3. Two reasons,
and the second is a real limit on the claim: (1) tool-call tokens are high-confidence/peaked, so
temperature barely moves them; (2) **default min_p=0.05 prunes the low-prob tail** — the very tail
KLD said is ~100× worse at Q3 — before temperature can sample it. So this is "robust under
*realistic* sampling," NOT "robust under fully-open (min_p=0) sampling," which the variance probe
showed reaches the tail (garbage). Most agent frameworks send temp with server-default samplers,
so the finding is agentically relevant; a min_p=0 config would be more aggressive than typical use.

**Verdict on the single-turn agentic floor: there isn't one down to Q3, even under realistic
sampling.** The KLD tail exists in the logits but does not manifest as tool-call failures. If an
agentic floor exists, it is a **multi-turn / cascade** phenomenon (errors compounding over a
trajectory) — the one regime this whole tool-call arc has not tested. That is the next module.
Receipts: `.194:~/quant_ladder/temp_sweep/sweep_*.json`; variance probe `scratchpad/variance_check.py`.

## Caveats
- Same-top/tail are corpus-general (wikitext) proxies for agentic failure, not tool-call success
  itself. The direct measurement is BFCL across the ladder (W3 toolchain) — this predicts its shape.
- Single model (Qwen3.6-27B), single quant family (unsloth K-quants). The *method* axis (dynamic
  vs static, KronQ-class) moves these curves — see the publisher panel (static Q4 was 2.17 pp worse).
