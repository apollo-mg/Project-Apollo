# Perplexity says Q3 is the best model in the ladder. Every other instrument says it's the worst.

**Date:** 2026-07-14. **Source:** re-analysis of the existing ladder logs (`.194:~/quant_ladder/kld_ladder_*.log`)
— no new compute. Same five runs, same BF16 base (`Mean PPL(base) = 6.515912`, identical to six
decimals in all five logs), same corpus (wikitext-2 test, md5 7c0137fc…), `build_carveout`
(fp32-clean sm_60), 2048 ctx / 32 chunks, f32 KV, FA off. All tiers unsloth, **all sharing one
imatrix** (`unsloth_calibration_Qwen3.6-27B.txt`, 496 entries, 76 chunks).

We built the ladder on median KLD and same-top%. The same `--kl-divergence` runs also emit
perplexity, and we never read that column. It tells a different story — an *opposite* story.

## The two ladders, from the same five runs

| Tier | GiB | Same-top % | Median KLD | **Mean PPL(Q)** | **ln PPL(Q)/PPL(base)** |
|------|----:|-----------:|-----------:|----------------:|------------------------:|
| *BF16 (base)* | 50 | — | — | *6.5159* | *0* |
| Q8_0   | 27 | 99.197 | 0.000103 | 6.5334 | +0.0027 |
| Q6_K   | 21 | 98.033 | 0.000707 | 6.5679 | +0.0080 |
| Q5_K_M | 19 | 97.074 | 0.001503 | 6.5825 | +0.0102 |
| Q4_K_M | 16 | 94.917 | 0.004780 | 6.6463 | **+0.0198 (worst)** |
| Q3_K_M | 13 | **90.637 (worst)** | **0.018433 (worst)** | **6.4370** | **−0.0122 (best)** |

**Read the last two columns against the two before them.** By same-top and KLD the ladder is
perfectly monotonic and Q3_K_M is far and away the most damaged model — it loses the argmax on
9.4% of tokens and carries 180× Q8's median divergence. By perplexity, Q3_K_M is **the best model
in the ladder**: better than Q4, better than Q8, and **1.2% better than the BF16 weights it was
quantized from.**

The instruments do not merely disagree on magnitude. **They invert the ordering.**

## It is not the outlier chunk (I checked)

Chunk 7 of wikitext is pathological for *every* tier — the running mean-KLD spikes there across the
board (Q8's jumps 11×, from 0.0019 to 0.0209). On that one chunk Q3 gets a **29% perplexity win**
(its own ln-ratio is −0.344) while Q8/Q6/Q5/Q4 all get slightly *worse* (+0.016…+0.037). That one
chunk supplies ~88% of Q3's total negative sum.

So I backed chunk 7 out of all five tiers (the per-chunk lines are running means — chunk 32's row
reproduces the final stats block exactly, so each chunk's own value is recoverable):

| Tier | mean ln-ratio (all 32) | **ex-chunk-7 (31 chunks)** |
|------|----:|----:|
| Q8_0   | +0.0027 | +0.0016 |
| Q6_K   | +0.0080 | +0.0073 |
| Q5_K_M | +0.0102 | +0.0099 |
| Q4_K_M | +0.0198 | +0.0199 |
| Q3_K_M | −0.0122 | **−0.0015** |

**The inversion survives.** Q3's margin over BF16 shrinks to ~nothing (parity), but Q3 is *still*
the best PPL in the ladder and **Q4_K_M is still the worst — 2.2% worse perplexity than the
smaller, more-damaged Q3_K_M**, outlier excluded. The Q3-beats-Q4 result is robust; the
Q3-beats-BF16 result is outlier-dependent and should be quoted as "parity with BF16," not "better."

## Corollary: *mean* KLD is tail-dominated too — we were right to use the median

The same logs show mean KLD running **5.6× to 61× the median**:

| Tier | Mean KLD | Median KLD | mean/median |
|------|---------:|-----------:|------------:|
| Q8_0   | 0.006322 | 0.000103 | **61×** |
| Q6_K   | 0.016927 | 0.000707 | 24× |
| Q5_K_M | 0.026057 | 0.001503 | 17× |
| Q4_K_M | 0.047196 | 0.004780 | 9.9× |
| Q3_K_M | 0.102555 | 0.018433 | 5.6× |

Mean KLD is almost entirely a report on the tail — at Q8 it is *sixty times* the typical token's
divergence. Anyone comparing quants by mean KLD is comparing tails while believing they're
comparing central tendency. Median + explicit percentiles (what the ladder uses) separates the two
deliberately. Both scalar summaries in common use — mean PPL and mean KLD — are outlier-driven.

## Ruled out

- **Wrong file** — GGUF metadata: `Qwen3.6-27B`, unsloth, file_type 12, composition
  `Q3_K:209, Q4_K:186, Q5_K:6, Q6_K:1`, 13.6 GB. Genuinely Q3-dominant, genuinely smaller than Q4.
- **Different base between runs** — `Mean PPL(base) = 6.515912` in all five logs, identical.
- **fp16 fog** — all runs on `build_carveout` (sm_60 carve-out), fp32-clean.
- **Corruption** — model loads, produces coherent output, scored 24/24 on the tool-call bench.

## Why (two hypotheses, one cheap experiment that separates them)

**H1 — quantization noise as regularization.** Quant noise flattens the output distribution. On
near-tied tokens the argmax shuffles (destroying same-top, inflating KLD) while the probability
mass on the *true* token barely moves — or *rises*, where the parent was confidently wrong.
Wikitext is raw prose, i.e. out-of-distribution for a heavily post-trained instruct model, and
post-training is known to make models overconfident. A flatter distribution is a *better-calibrated*
one on OOD text, and perplexity rewards calibration. **This predicts the effect is an artifact of
grading an instruct model on raw prose, and should vanish or inverse on in-distribution chat text.**

**H2 — the imatrix is fitting the eval distribution.** The importance matrix decides which weights
get the scarce bits, and its influence *grows as bits shrink* (near-zero at Q8, dominant at Q3). If
`unsloth_calibration_Qwen3.6-27B.txt` contains wiki-like prose, then the Q3 quant has been
partially *fit* to the very corpus we grade it on — and Q3 benefits most because Q3 needs the
imatrix most. This would mean **imatrix quants benchmarked on wikitext PPL are grading their own
homework**, which is close to universal community practice.

**The discriminating experiment (~1 hr, reuses the existing 16 GB base-logits file):** an imatrix
ablation at fixed recipe. Download unsloth's `imatrix_unsloth.gguf`, then run stock `llama-quantize`
from our BF16 twice at Q3_K_M — once **with** that imatrix, once **without** — so the tensor recipe
is identical and the imatrix is the only variable. Score both against the existing base logits.
- If **no-imatrix Q3 is monotonically worse** (PPL above BF16) while imatrix-Q3 is at/below it → **H2**:
  the imatrix is buying wikitext-specific perplexity. Damning for the standard benchmark.
- If **both** land at/below BF16 → **H1**: it's general quantization-noise calibration, and the
  problem is the corpus, not the imatrix. Follow-up: re-score on chat-formatted in-distribution text.

**Predictions logged before the run (Fable):** H2 primary, ~60/40. I expect no-imatrix Q3 to sit
clearly above BF16 (worse) — call it ln-ratio +0.03 to +0.06 — and the imatrix to account for most
of the ~0.03 swing. I also expect no-imatrix Q3 to lose several points of same-top vs imatrix-Q3.

## THE ABLATION RAN. H2 IS DEAD, AND MY PREDICTION WAS WRONG BY THE SIGN. (2026-07-14)

Stock `llama-quantize` from our BF16, twice at Q3_K_M, same binary
(`build_carveout/bin/llama-quantize`), same corpus, same base-logits file. **Recipe control check
passed: the tensor histograms are identical** — `F32:353, Q3_K:353, Q4_K:138, Q5_K:6, Q6_K:1` in
both — so the imatrix really is the only variable.

| | **with imatrix** | **no imatrix** | winner |
|---|---:|---:|---|
| Median KLD | 0.020908 | 0.029501 | **imatrix** (41% lower) |
| Same-top % | 89.999 ± 0.166 | 88.679 ± 0.175 | **imatrix** (+1.32 pp) |
| 99.0% KLD (tail) | 1.1915 | 2.0050 | **imatrix** (68% lower) |
| 99.9% KLD | 17.33 | 20.24 | **imatrix** |
| Mean KLD | 0.116361 | 0.156869 | **imatrix** |
| **Mean PPL** | 6.5840 | **6.2847** | **no imatrix** |
| **ln PPL/base** | **+0.0104 ± 0.0040** | **−0.0361 ± 0.0044** | **no imatrix** |

**Every fidelity metric says the imatrix helps — which is exactly what an imatrix is for. Perplexity
says the imatrix HURTS**, and crowns the no-imatrix quant the best model in the entire study: **3.5%
better perplexity than the BF16 weights it was quantized from**, at −8.1σ. That margin is an order
of magnitude larger than the chunk-7 outlier perturbation (~0.011), so it is not an outlier artifact.

**Prediction scored: FALSIFIED, sign inverted.** I called +0.03…+0.06 for no-imatrix; it came in at
−0.036. Not a magnitude miss — I had the direction backwards.

**H2 (imatrix fits the eval corpus) is dead.** The imatrix is not buying wikitext perplexity; it is
*paying* perplexity — ~4.7% of it — to stay faithful to the parent. The contamination story was
exactly backwards.

**H1 is now the leading explanation, in a sharper form than originally stated.** The imatrix
preserves the activations that matter on unsloth's (chat/instruct-like) calibration text, keeping
the quant faithful to its post-trained, *sharpened, overconfident* parent. Strip the imatrix and the
quantizer damages weights indiscriminately, the distribution flattens, the model becomes less
overconfident — and a less overconfident model scores **better perplexity on raw wiki prose**, which
is out-of-distribution for a post-trained instruct model. Fidelity and perplexity are pulling in
opposite directions because **the parent itself is miscalibrated on this corpus.**

**On this corpus, with this model, perplexity is ANTI-CORRELATED with fidelity.** Not merely noisy —
inverted. The worst model we have by every distributional measure has the best perplexity we have
ever measured.

## buun called the mechanism from first principles — and the receipts were already on disk

buun, on Discord, without having seen any of this data: *"the PPL here is mean… which means a
flattening of the tails is doing a ton of work even though every other token may be in the gutter."*

He is right, and `llama-perplexity`'s own per-token Δp distribution (Δp = p_quant − p_base on the
**true** token) proves it. From the same logs, never previously read:

| Δp percentile | STOCK-IMAT | STOCK-NOIMAT | |
|---|---:|---:|---|
| 99.9% | +90.4% | **+98.2%** | tail rescue — NOIMAT bigger |
| 99.0% | +20.0% | **+26.5%** | tail rescue — NOIMAT bigger |
| 90th | +4.63% | +5.08% | |
| **Median** | −0.001% | **−0.012%** | bulk — NOIMAT worse |
| 25th | −1.00% | **−1.47%** | bulk — NOIMAT worse |
| 10th | −4.95% | **−6.23%** | bulk — NOIMAT worse |
| 0.1% | −75.9% | −68.7% | |
| **Mean Δp** | −0.162% | **−0.170%** | NOIMAT assigns *less* mass to the true token |

**The no-imatrix quant assigns LESS probability to the true token on average (mean Δp negative) and
its typical token is worse at every bulk percentile — median, 25th, 10th. Its bulk is in the gutter.
And it still wins on perplexity.**

The resolution is the log. Perplexity is `exp(mean of −log p)`, and −log p explodes as p → 0:
- shaving a confident token from p=0.95 → 0.90 costs **0.05 nats**
- rescuing a true token the parent left at p=0.001 → 0.01 pays **2.30 nats**

**Flattening pays roughly 50:1 in log-space.** So mass moved off the peak and sprayed into the tail
improves mean-log-likelihood *even while the arithmetic mean probability and the median token both
get worse*. The extreme-tail asymmetry is the smoking gun: NOIMAT's gain/loss ratio at the 0.1%
extremes is 98.2/68.7 = **1.43**, vs IMAT's 90.4/75.9 = **1.19**. More tail rescue → better PPL.

The ablation is the controlled proof: **bulk worse + tail rescue bigger → better PPL**, with the
imatrix as the only variable.

**Self-criticism worth recording:** we had already caught this exact trap once — mean KLD runs
5.6×–61× the median, which is *why* the ladder is built on medians and percentiles. Then I read a
column of **mean** PPL and treated it as a quality signal without applying the lesson. Perplexity is
a mean of a heavy-tailed quantity. It is the same statistic we had already rejected, wearing a
different name.

## Capability tiebreaker: FAILED TO BREAK THE TIE (2026-07-14)

Tool-call bench (24 hard cases, temp 0, `--reasoning off`) on the matched pair plus a Q8 reference:

| model | same-top | median KLD | PPL | **tool-call** |
|---|---:|---:|---:|---:|
| Q8_0 | 99.20% | 0.000103 | 6.5334 | **24/24** |
| Q3 STOCK-IMAT | 90.00% | 0.020908 | 6.5840 | **24/24** |
| Q3 STOCK-NOIMAT | 88.68% | 0.029501 | 6.2847 | **24/24** |

**All three 24/24.** Prediction (NOIMAT 18–23/24) FALSIFIED. The worst model we have ever measured —
a no-imatrix Q3, 11.3% of greedy tokens flipped vs BF16 — passes every hard tool-call case. Its free
generation is also coherent and factually correct ("Hero of Alexandria described a device called the
aeolipile…"). It is not a broken model.

**This is the third consecutive ceiling.** The bench cannot discriminate, so it cannot arbitrate
between PPL and KLD. The honest statement: *we have not yet built an instrument that can see the
damage KLD says is there.* Single-turn tool-calling is not it. That is now a strong argument that
the damage — if it manifests at all — is a **multi-turn / cascade** phenomenon, which is exactly the
module-2 probe, and exactly the failure mode buun reports from lived experience.

## Confidence probe: HALF-CONFIRMS the mechanism, and Q4 breaks the clean story (2026-07-14)

Greedy generation, top-20 logprobs at each position, 400 positions/model, 5 fixed prompts.

| model | mean top-1 | entropy | ln PPL/base | same-top |
|---|---:|---:|---:|---:|
| Q3 STOCK-IMAT | 0.8226 | 0.544 | +0.0104 | 90.00% |
| Q8_0 | 0.8090 | 0.607 | +0.0027 | 99.20% |
| Q3_K_M (unsloth) | 0.8040 | 0.620 | −0.0122 | 90.64% |
| Q3 STOCK-NOIMAT | 0.7953 | 0.647 | **−0.0361** | 88.68% |
| Q4_K_M | **0.7876** | **0.673** | **+0.0198** | 94.92% |

**On the matched ablation pair the mechanism holds:** NOIMAT is measurably flatter than IMAT
(top-1 0.795 vs 0.823; entropy 0.647 vs 0.544) and it is the one with better perplexity. Strip the
imatrix → distribution flattens → tail rescued → PPL improves. Controlled, single variable, consistent.

**But Q4_K_M falsifies the general law.** Q4 is the *flattest model in the set* and has the *worst*
perplexity of all of them. So "flatter ⇒ better PPL" is FALSE in general. Flattening only pays if
the displaced mass lands on the **true** token; spread uniformly across a 151k vocab it is just
noise. Q4 flattens without rescuing.

**Honest split of the claim:**
- **buun's point is CONFIRMED and it is about the STATISTIC** — PPL is a mean of −log p, dominated
  by low-p tokens; the tail rescue carries the mean while the bulk is in the gutter. The Δp
  distribution proves this directly and needs no causal story.
- **The "flattening" gloss is only PARTIALLY supported** — correct on the ablation pair, false as a
  general rule, with Q4 as the standing counterexample. **We do not have a mechanism that explains
  all five models.** Do not publish one.

**Known flaw in this probe (flag it before someone else does):** each model generates its *own*
greedy continuation, so confidence is measured over five *different* token sequences — a model that
wanders into easy text looks confident for free. The correct measurement is **teacher-forced entropy
over a fixed token sequence** (what `llama-perplexity` computes internally but does not expose).
Treat this table as indicative only; the Δp distribution is the load-bearing evidence.

## buun's median-PPL proposal: TESTED. Falsified on wikitext — and the failure is diagnostic.

buun: *"I wonder if you can just calculate median PPL the way we do median KLD… if that gives an
accurate monotonicity from Q8 → Q2 then we have a cheaper test than KLD, since we don't need to dump
logits."* The economics are real: KLD costs a full BF16 forward pass **plus** a 16 GB logit dump tied
to one exact corpus+chunk config. Median NLL needs **only the quant and the text**.

Implemented by patching `llama-perplexity` (`~/llama_stock/tools/perplexity/perplexity.cpp`,
`build_carveout`). Smaller than expected: **the tool already fills `prob_history[i]` with
p(true token) for every position** and then discards everything but the mean. The patch is ~25 lines
of additive printing. Backup: `perplexity.cpp.apollo_bak`.

**Correction to my own claim first:** I told buun median NLL might be degenerate because "median Δp
≈ 0.000%". That was wrong — Δp is a *different quantity* (quant-vs-base probability difference,
which needs the base model). **Median NLL is a healthy 0.78 (median PPL ≈ 2.18).** Not degenerate.

### Result: NO percentile is monotonic. The whole instrument is flat on wiki.

| percentile | Q8_0 | Q6_K | Q5_K_M | Q4_K_M | Q3_K_M | mono? | ρ vs medKLD |
|---|---:|---:|---:|---:|---:|---|---:|
| Mean | 1.8770 | 1.8822 | 1.8844 | 1.8940 | 1.8621 | no | +0.000 |
| **Median** | 0.7660 | 0.7632 | 0.7681 | 0.7743 | **0.7632** | no | −0.100 |
| 25.0% | 0.0518 | 0.0514 | 0.0523 | 0.0518 | 0.0515 | no | +0.100 |
| 75.0% | 2.7410 | 2.7460 | 2.7415 | 2.7639 | 2.7525 | no | +0.800 |
| 90.0% | 5.4094 | 5.4273 | 5.4491 | 5.4730 | 5.4208 | no | +0.400 |
| 99.0% | 11.3944 | 11.4818 | 11.4967 | 11.4446 | 11.0398 | no | −0.300 |
| 99.9% | 17.3769 | 17.6229 | 17.5819 | 17.7759 | **15.6050** | no | −0.100 |

**Median NLL varies 1.4% across a range where median KLD varies 180×. Q3's median (0.7632) is
IDENTICAL to Q6's.** That is not weak signal — it is no signal. On wikitext the perplexity
instrument, at *every* percentile, is blind to five bits of quantization. "Trim the middle until it
has signal" cannot work here because **there is no signal at any percentile to trim toward.**

### The sensitivity inversion this exposes

- **Bit depth Q8→Q3:** PPL moves ~1.5% (noise-level, non-monotonic). KLD moves **180×**.
- **Imatrix on/off at fixed Q3:** PPL moves **4.7%**. KLD moves only 1.4×.

**PPL is more sensitive to the imatrix than to five bits of quantization.** Consistent with the
calibration account: the imatrix controls *which* weights are protected, hence distribution
sharpness; PPL on OOD prose measures sharpness. Bit depth, with the imatrix holding calibration
steady, barely moves it.

### Why no NLL percentile can proxy KLD in principle

On the ablation pair, **NOIMAT has lower (better) NLL at EVERY percentile** — median 0.773 vs 0.779,
90% 5.285 vs 5.471, 99.9% 14.72 vs 15.82 — while KLD says IMAT is the faithful one. Trimming to the
tail does not reverse it, because **the two metrics have different reference points**:

- **NLL (any percentile)** = distance from the **ground-truth text**.
- **KLD** = distance from the **parent model**.

When the parent is miscalibrated on the corpus, being faithful to the parent (low KLD) means being
*more wrong* about the actual tokens (high NLL). A reference-free statistic structurally cannot
proxy a reference-based one **while the parent disagrees with the corpus**.

**Which is exactly why buun's corpus point is the fix, not a footnote.** He said (same conversation)
*"wiki is not the best corpus… since we don't need logits, we can be more fancy free in our corpus
selections."* On an **in-distribution** corpus the parent is well-calibrated, so distance-from-truth
and distance-from-parent should **realign** — and only then can percentile NLL track KLD. His metric
idea and his corpus idea are the same insight from two directions.

## Corpus panel — RESULTS (buun's request: "code vs a simulated tool call chain")

Built (`~/corpora/`, builder `scratchpad/build_corpora.py`), full ladder each, reference-free:
- **toolchain** — 24 multi-turn agentic transcripts rendered with the **model's own chat template**
  (jinja2 from the GGUF), containing ground-truth tool calls + tool results + summaries.
- **code** — real llama.cpp C++ source.
- **wiki** — the existing OOD control.

**Design point that makes it valid: the ground-truth tool calls are HAND-AUTHORED from the bench
case specs, NOT generated by any model in the ladder.** Had they come from Q8, Q8 would be scored on
predicting its own output and would win by construction. Hand-authored ⇒ no tier is advantaged.

**Repetition audit (done before running):** toolchain 1.0×, code 1.0×, chat 3.5×. Chunks are
independent contexts (BOS per chunk) so cross-chunk repeats cannot be copied, but chat's *effective*
sample is ~19k tokens not 65k, so its error bars would be optimistic — **chat is excluded pending a
real dataset.** toolchain doubles as the in-distribution corpus (it is chat-templated).

### Model-format discovery that corrects this document

**Qwen3.6 does NOT emit JSON tool calls.** Its template mandates an XML form:
`<tool_call><function=NAME><parameter=P>\nVALUE\n</parameter></function></tool_call>`.
Earlier text in this file speculated that tool-call structure lives in "JSON/schema" tokens — for
this model that is **wrong**; the structural tokens are XML tags. Any tail-vs-structure argument
built on the JSON assumption needs re-checking.

### RESULTS (2026-07-15): one corpus redeems the instrument, one inverts it harder than wiki

Full ladder, 30 chunks × 2048, same flags as the wiki runs. Receipts: `.194:~/quant_ladder/corpus_{toolchain,code}_*.log`.

**Code corpus — PPL WORKS.** First reference-free statistic in the campaign to reproduce the
KLD/fidelity ordering:

| tier | mean PPL | p90 NLL | p99 NLL |
|---|---|---|---|
| Q8_0 | **1.6900** | **1.5979** | **7.9757** |
| Q6_K | 1.6907 | 1.6089 | 8.0021 |
| Q5_K_M | 1.6931 | 1.6141 | 8.0176 |
| Q4_K_M | 1.6995 | 1.6279 | 8.0229 |
| Q3_K_M | 1.7206 | 1.6899 | 8.0349 |

Mean PPL, p90 NLL, and p99 NLL are each **strictly monotone Q8→Q3** — Spearman ρ = 1.0 vs the
(wiki-measured) median-KLD ranking. Caveats stated plainly: adjacent steps (Q8 vs Q6: 0.0007 PPL)
are far inside the marginal ±0.015 error bars; the evidence is the exact monotone order appearing
in three statistics at once, and only paired per-token ΔNLL tests (dumps in flight) can resolve
the adjacent pairs properly. Note KLD was measured on wiki, not per-corpus — the reference ranking
is the bit-order, which wiki KLD happens to match monotonically.

**Toolchain corpus — a NEW inversion, worse than wiki's.** Q8_0 is **dead last at every
statistic**; Q5_K_M is best at every statistic:

| tier | mean PPL | p75 NLL | p90 NLL | p99 NLL |
|---|---|---|---|---|
| Q8_0 | 1.4733 | 0.000805 | 0.2892 | 9.569 |
| Q6_K | 1.4114 | 0.000706 | 0.2286 | 8.762 |
| Q5_K_M | **1.3479** | **0.000607** | **0.1634** | **7.428** |
| Q4_K_M | 1.4134 | 0.000775 | 0.2267 | 8.576 |
| Q3_K_M | 1.4093 | 0.000686 | 0.2134 | 8.937 |

Q5 beats Q8 by 8.5% mean PPL, **44% at p90**, 22% at p99 — the Q8−Q5 gap is ~7σ by the marginal
error bars, not noise. Spearman vs KLD ranking: **ρ = −0.5** (mean-PPL ranks Q5,Q3,Q6,Q4,Q8).
So the most faithful quant in the ladder is the *worst* predictor of hand-authored agentic
transcripts, and wiki's champion (Q3) isn't the winner here either — a *different* inversion,
which again resists any single mechanism (consistent with the Q4-counterexample stance: we do not
publish a mechanism).

**Median PPL is degenerate outside wiki.** Toolchain: median NLL ≈ 0.00002 ⇒ median PPL 1.0000 at
every tier; code: ≈ 0.0022 ⇒ 1.0022 at every tier. Templated/structured text is so predictable
that ~75% of tokens cost nothing (toolchain p75 NLL < 0.001) — the entire mean is manufactured in
the top decile. buun's "trim the middle until it has signal" is right, but the trim goes the other
way: **the usable statistics are tail percentiles (p90/p99), not the median** — the median has no
signal on any corpus tested (no ordering signal on wiki, no variance here).

**The trichotomy, stated once:**
- **wiki (OOD prose):** non-monotone, anti-correlated — Q3 "wins", flattening artifact.
- **code:** strictly monotone, ρ = 1.0 — the instrument works.
- **toolchain (chat-templated agentic):** non-monotone, ρ = −0.5 — Q8 worst, Q5 best.

Same instrument, same models, three corpora, three verdicts. PPL is not irredeemable and not
trustworthy — it is **conditional on the corpus**, and nothing in the number tells you which
regime you're in. That is the publishable finding.

**buun's resolution challenge (10:05 PM, logged verbatim):** *"I feel like they are just earning
their monoticity but that for e.g intra-codec changes (a codebook swap, alpha sweep, small
adjustments) you couldn't use it."* The dynamic-range concession is real: code-corpus mean PPL
spans **1.8%** Q8→Q3 where median KLD spans **180×** — as a raw scalar it cannot compete. The
testable part: the ±0.015 marginal error bars are the *wrong* bars, because every tier scored
identical tokens — corpus difficulty is common-mode and cancels in **paired per-token ΔNLL**. At
n≈30k tokens a paired sign test resolves a 50.29/49.71 win-rate imbalance at 2σ; whether that
beats a codebook-swap-sized effect is an empirical number — the dumps in flight measure the
actual paired noise floor, and the **minimum detectable delta** will be computed and stated.
Direct test queued (`run_nll_dump_extra2.sh`): STOCK-IMAT vs STOCK-NOIMAT on the code corpus —
a calibration-only change at fixed recipe, the nearest on-disk analog to an intra-codec tweak,
with a known KLD verdict (IMAT better: 0.0209 vs 0.0295 median). If paired code-NLL detects it
with the right sign, the instrument covers small deltas; if not, buun is right and its use ends
at coarse tier-ordering. Resolution also buys back with corpus length (√L, one forward pass per
variant, no logit dumps) — the economics stay far below KLD even at 10× corpus.

**KV-format extension (buun, 10:06 PM: "try testing this on KV formats now… I suppose it
would [work]").** Queued as the last overnight stage (`run_kv_ladder.sh`): weights pinned Q8_0,
code corpus, ctk=ctv ∈ {f16, q8_0, q5_1, q5_0, q4_1, q4_0}, **FA on** (stock requires flash
attention for quantized V; also the realistic deployment mode — geometry therefore differs from
the campaign's faoff KV KLD receipts), per-token dumps, paired vs the f16 anchor. This is the
resolution challenge at its hardest: on the patched build the fine KV rungs are 100–10,000×
smaller perturbations than weight tiers (campaign medians ~1e-6–2e-4 vs Q3's 0.018). Note
2048-token context *underexposes* KV damage relative to long-context use — a depth sweep is the
follow-up if the instrument bites at all. Predictions: **P-kv1 (80%)** paired NLL resolves q4_0
vs f16 at >3σ; **P-kv2 (65%)** q8_0 vs f16 is NOT resolvable at 30k tokens; **P-kv3 (70%)** the
rungs that do resolve order monotonically with bits. buun's "I suppose it would" is most at risk
at the q8 end.

**Predictions logged before the span-masked results (score these):**
- **P-span1 (60%):** the Q8-worst ordering does NOT persist on the `<tool_call>` spans themselves
  (the inversion lives in the filler/response tokens, not the call tokens).
- **P-span2 (70%):** span-masked NLL is also non-monotone across the ladder.
- **P-paired-code (65%):** paired per-token sign tests on code confirm even the adjacent-pair
  orderings (incl. Q8 > Q6) that the marginal error bars cannot resolve.

### OVERNIGHT RESULTS (2026-07-15, all dumps in) — predictions scored, instrument calibrated

Analysis: `analyze_dumps.py` on the 20 per-token dumps (token arrays verified identical across
tiers per corpus). Two statistics per pair: **chunk-level paired t** (30 independent contexts —
the conservative arbiter) and **token-level sign test** (which model wins the majority of tokens;
z assumes token independence, so adjacent-token correlation inflates it — direction is reliable,
magnitude is optimistic).

**1. The in-distribution reversal HAPPENED — the doc's strongest prediction is CONFIRMED.**
Toolchain: IMAT mean PPL 1.4312 vs NOIMAT 1.4561 (IMAT wins by 1.7%); token-majority z = **+37.7**
(18,228 wins / 11,704 losses — IMAT better on 61% of decided tokens, calls and filler alike).
On wiki the same pair went the other way (NOIMAT wins mean by 4.5% *while losing the bulk*).
On format-matched text, fidelity and NLL realign — and IMAT wins bulk AND mean simultaneously.
This was the falsification test of the whole calibration story, and it passed.

**2. P-span1 FALSIFIED (predicted 60% the other way): Q8_0 is worst ON THE CALL TOKENS TOO.**
Call-token mean NLL (n=5,024): Q8 0.0676 > Q4 0.0539 > Q6 0.0512 > Q5 0.0452 > Q3 0.0416. The
toolchain inversion is not a filler artifact — it is corpus-wide. P-span2 CONFIRMED (non-monotone).
Call tokens are near-free for every tier (median 2e-6; the mean is made by the ~1% of call tokens
that are real decision points). **Interpretive lesson (new):** hand-authoring the ground truth
removed self-preference bias but put the *content* off every model's manifold — in-distribution
FORMAT, out-of-distribution CONTENT — and content is what triggers the sharp-model tail penalty.
"Chat-templated" was not the right notion of in-distribution; the corpus axis decomposes into
format and content, and content dominates. (The IMAT/NOIMAT reversal in §1 is immune: same
corpus, fixed content, paired.)

**3. P-paired-code FALSIFIED, in the most instructive way possible.** Sign-test directions vs
Q8: Q6 loses (z=−3.4), Q5 loses (−8.7), Q4 loses (−6.6) — but **Q3 WINS the token majority
against both Q4 (z=+9.3) and Q8 (z=+5.9) while losing the mean decisively (chunk-t +5.85, the
worst in the ladder).** On 52.7% of decided code tokens Q3_K_M beats Q4_K_M; it loses the ladder
on the tail of the remaining 47%. The mean-vs-majority split is now a single-receipt, same-corpus,
same-pair fact: **mean NLL is a tail statistic and the sign test is a bulk statistic — they are
different instruments, both free from the same dump.** The monotone code ladder of yesterday is
monotone in mean/p90/p99 only; the bulk ordering is non-monotone even on code.

**4. buun's resolution challenge ("intra-codec changes — you couldn't use it"): the instrument
RESOLVES the imatrix toggle.** Code corpus, calibration-only change at fixed recipe (nearest
on-disk analog to a codebook swap): mean_d = −0.0069 nats (IMAT better, KLD-agreeing direction),
**chunk-t = −3.75** (clean at n=30 chunks), token-majority z = +26.0 (57.4% win rate), |Δ| ≈
1.9× the measured MDD. One forward pass per variant, no logit dumps, ten minutes a side. For
deltas of imatrix-toggle size (~1.4× median KLD), buun was wrong and the jurisdiction extends
into intra-codec territory.

**5. KV-format ladder: the floor found, and it is where predicted.** vs f16 anchor on code
(Q8_0 weights, FA on): **q8_0 KV is a dead tie** — mean_d = −0.00001 nats against an MDD of
0.00007 (P-kv2 CONFIRMED; the paired instrument can see 7e-5-nat shifts and there is *nothing
there* at 2048 ctx). q4_0 resolves clearly by token majority (z = −10.1; P-kv1 CONFIRMED on the
sign statistic, though chunk-t 1.35 does not resolve the mean). **P-kv3 FALSIFIED:** the middle
rungs are non-monotone (q4_1 mean_d +0.00022 *better* than q5_0 +0.00029 and q5_1 +0.00047).
Caveat flagged before interpreting q5 rungs: the q5_1/q5_0 cells ran ~3× slower than the others
(different FA kernel path in this build — possibly a fallback), so their tiny deltas ride on a
different code path. KV effects here are ~10× smaller than the imatrix toggle and sit at the
30-chunk floor — and 2048-token context underexposes KV damage by construction. **Depth sweep
(-c 8192+) is the required follow-up before any KV conclusion beyond "q8 KV is free at short
context."**

### buun's fraud objection (2026-07-15 midday) — one hypothesis refuted by existing receipts, one point conceded and sharpened

**buun:** *"the PPL boost is from either GPTQ (hessian dampening) or awq-pct (AWQ channel scaling)…
there are a bunch of such hacks that improve PPL… it's too easy to fraud."*

**The GPTQ/AWQ hypothesis is refuted by the ablation already on disk.** The best-PPL model in the
entire study (STOCK-NOIMAT, 6.2847, −3.5% below BF16) was produced by stock `llama-quantize` with
**no calibration data at all** — `quantize_noimat.log` contains no imatrix/dataset lines; the
no-imatrix K-quant path chooses block scales from the weights alone. No Hessian dampening, no
activation-aware channel scaling, no optimization toward any corpus. And the one activation-aware
ingredient llama.cpp *does* have (the imatrix — the AWQ-analog) moved PPL the WRONG direction for
the fraud story: it *cost* 4.7% PPL and bought fidelity. **The PPL boost requires no PPL-fitting
machinery — plain quantization noise suffices, via the tail-rescue mechanism buun himself
identified.** This makes the fraud point STRONGER, not weaker: you can "fraud" PPL by accident,
with a quantizer that has never seen a token of text.

**The corpus-sampling objection is conceded for absolute ranking, with two constructive narrowings:**
1. *Paired A/B is more robust than tier-ranking, but not corpus-free:* the IMAT/NOIMAT toggle
   resolves in the KLD-agreeing direction on code (chunk-t −3.75) AND on toolchain (z=+37.7) —
   including the corpus whose tier-ladder is scrambled — but INVERTS on wiki. 2 of 3 corpora.
   The regime problem shrinks under pairing; it does not vanish.
2. *Candidate a-priori validity criterion (hypothesis, n=3, logged not claimed):* the instrument
   was right where the parent predicts the corpus well (parent median NLL: toolchain 0.00002 ✓,
   code 0.0022 ✓) and wrong where it doesn't (wiki 0.76 ✗). If this holds, "know your corpus"
   becomes measurable from one cheap forward pass of the parent. The BF16-generated-content cell
   (queued) is the next test point: lowest possible parent NLL by construction.
3. *Self-diagnosis via statistic concordance:* one dump yields bulk (sign test) and tail (mean,
   p99) statistics. Where they agree (imatrix-on-code: all agree) confidence is earned; where
   they split (Q3-vs-Q4-on-code: bulk says Q3, tail says Q4) the split itself flags flattening
   territory → escalate to KLD. The instrument can partially announce its own regime.

**Standing division of labor (the calibrated claim):** paired NLL = the cheap inner loop for
intra-codec iteration on validity-checked corpora; KLD vs parent = the outer gate and final
arbiter, and the ONLY instrument for anything adversarial/cross-algorithm — KLD is
Goodhart-resistant for the fidelity objective by definition (optimizing toward it IS the goal);
reference-free NLL is not, as any GPTQ-style objective can chase it.

### Today's two experiments (2026-07-15, predictions logged before results)

**KV depth sweep (RUNNING):** same corpus (`code_big.raw`, 3MB of llama.cpp source) at
`-c 2048` AND `-c 8192`, × {f16, q8_0, q4_0} KV, Q8_0 weights, FA on, dumps. Note: the q5
slowness last night produced NO logged fallback — silent slow kernel path, caveat stands
softened. Predictions: **P-depth1 (60%)** q8_0 KV remains a tie at 8192 (|mean_d| < MDD);
**P-depth2 (75%)** q4_0 damage grows with depth (larger |mean_d| and |sign z| at 8192 than 2048).

**DEPTH SWEEP RESULTS (same day):** **P-depth1 CONFIRMED** — q8_0 KV is a dead tie at 8192 too
(mean_d +0.00008 vs MDD 0.00026, sign z −0.9, on 122,850 paired tokens). "q8 KV is free" now
holds at 8192; beyond (his 260k configs) remains unmeasured. **P-depth2 CONFIRMED with a
load-bearing nuance:** q4_0's mean gap doubles (+0.00077 → +0.00156) and sign z grows (−10.1 →
−12.1), but the per-token win-rate imbalance SHRINKS (5.8pp → 3.5pp decided-token margin; z only
grew via 4× n) — **the depth growth is tail-driven, not bulk-driven.** Chunk-level t never clears
the floor (+1.12, +1.87) — the sign test is the reliable q4_0 detector, means stay sub-MDD.
**Positional probe: NO monotone accumulation.** ΔNLL by in-chunk position is U-shaped at both
depths (q4_0@8192 quartiles: +0.0025, +0.0008, +0.0003, +0.0026) — earliest-context and
latest-position tokens hurt most, middle least. The "KV damage compounds with readback depth"
intuition is not visible in teacher-forced NLL at these depths — with the standing caveat that
teacher-forcing resets errors every token; closed-loop generation could still compound
(Module 2's question, again).

**Content-manifold test (queued behind it):** generate ~100k tokens with BF16 itself at
realistic sampling temperature (NOT greedy — greedy text is atypically high-probability and
degenerate for this purpose), score the full ladder on it, paired. This is the missing corpus
cell: in-distribution format AND content — self-preference is the *point*, since it aligns the
NLL reference with KLD's reference (the parent) for the first time. Predictions:
**P-content1 (65%)** mean NLL goes monotone Q8→Q3 on the parent's own text;
**P-content2 (85%)** Q8_0 is at least no longer worst. If the inversion persists even here,
the content-manifold story dies and something stranger is going on.

**CONTENT-MANIFOLD RESULTS (same day) — BOTH CONFIRMED, and it is the cleanest corpus of the
campaign.** 40/40 prompts generated (BF16, temp 0.7/top_p 0.95/min_p 0.05, 0.0% shingle-dup,
~33k tokens → 16 chunks). On the parent's own sampled text:
- **Strictly monotone mean NLL:** Q8 0.30877 < Q6 0.30952 < Q5 0.31071 < Q4 0.31745 < Q3 0.34125.
- **Every pair resolves at chunk level** — including Q6-vs-Q8 (t=+2.00, right at the floor),
  which NO other corpus could see, with only 16 chunks: Q5 +3.15, Q4 +7.10, Q3 +9.37. The
  Q3−Q8 separation (+0.0325) is ~2× code's — the parent's own text is the highest-SNR corpus.
- **Fully concordant:** Q8 wins bulk (sign tests all negative, incl. vs Q3 at z=−13.6), mean,
  and tails simultaneously — the only corpus with no bulk/tail disagreement anywhere.
- **IMAT beats NOIMAT at chunk-t=−7.52, z=+15.9** — the reversal's strongest confirmation yet.

**The corpus quartet, and the criterion refined:**

| corpus | parent medNLL | tier ladder | concordance | IMAT/NOIMAT sign |
|---|---|---|---|---|
| wiki | 0.76 | anti-correlated | discordant | WRONG |
| toolchain | 0.00002 | scrambled (Q8 worst) | discordant | right |
| code | 0.0022 | monotone (mean/tails) | discordant at Q3 | right |
| **selfgen** | 0.007 | **monotone, all pairs** | **concordant** | right (strongest) |

Refinement forced by toolchain: low parent-NLL predicts **paired-A/B validity** (3/3 low-median
corpora got the toggle right; wiki wrong) but NOT tier-ranking validity (toolchain is low-median
and scrambled — hand-authored content breaks ranking even in matched format). For **absolute
ranking**, the operational rule the quartet supports: **trust rankings only where the statistics
are concordant, and self-generated content is the one corpus class that delivers concordance by
construction.** Practical recipe for anyone: sample ~30k tokens from the parent at deployment
settings, score the ladder paired — no logit dumps, resolves even Q8-vs-Q6, cannot be gamed by
corpus choice because the model chooses. Standing caveats: n=16 chunks, one model family, one
sampling config; and self-gen measures fidelity-on-own-manifold ONLY — it structurally cannot
see QAT-style beneficial divergence (buun's task court remains separate and sovereign).

**Instrument calibration card (what to hand anyone who asks "can I use this"):** paired
reference-free NLL at 30×2048 tokens resolves mean-NLL deltas down to ~7e-5–6e-3 nats (pair-
dependent; MDD scales with the pair's tail volatility) and token-majority splits of ~51/49.
Imatrix-toggle-sized changes: clearly. Weight-tier steps at Q4 and below: clearly. Q8-vs-Q6:
direction only (sign z=3.4), mean unresolved at 30 chunks — ~3× more corpus needed. KV q8_0:
invisible (genuinely null at this context length). And the standing regime caveat survives
everything: on content the model has opinions about, *lower NLL can mean a worse model* — pair
your comparisons and know your corpus.

### Next instrument: span-masked NLL (the ceiling-proof measure)

Whole-corpus toolchain NLL is **~98% tool DEFINITIONS, ~2% actual tool-call tokens** — so it largely
measures JSON schema text. The fix: dump **per-token NLL** (`APOLLO_NLL_DUMP`) and mask to the
`<tool_call>…</tool_call>` spans, scoring only the assistant's ground-truth call tokens.

**Status 2026-07-15:** patch applied (`perplexity.cpp.apollo_bak2` backup), alignment verified
(`prob_history.resize(tokens.size())`, writes at `start + seq*n_ctx + first` ⇒ index-aligned with
the token array; unevaluated positions dump as −1 sentinel), binary rebuilt. Dump ladder running
detached on .194 (`run_nll_dump_ladder.sh`, both corpora × 5 tiers), with the **STOCK-IMAT /
STOCK-NOIMAT toolchain cells queued behind it** (`run_nll_dump_extra.sh`) — that pair tests
prediction #1 below directly.

**This is the answer to the ceiling problem that has blocked the campaign three times.** The 24/24
bench is binary and argmax is robust, so it saturates. NLL on tool-call tokens is **continuous** — it
measures probability mass on the correct tokens and therefore **sees degradation before it becomes a
failure**. Scripts: `scratchpad/patch_nll_dump.py`, `scratchpad/masked_nll.py`.

### What this predicts next (falsifiable, queued)
1. **The ordering must REVERSE on in-distribution text.** On chat-formatted text (the model's own
   post-training distribution, where it is *not* overconfident), the imatrix quant should beat the
   no-imatrix one on perplexity. **This is now the single strongest untested prediction the theory
   makes, and the cheapest way to kill it.**
2. **Median/robust NLL, not mean.** Re-derive the ladder with a robust log-likelihood statistic.
   Prediction: the imatrix quant wins on median NLL, reversing the mean. Needs per-token NLL, which
   `llama-perplexity` does not emit — small patch or a teacher-forced harness required.
3. **Full-corpus PPL (~140 chunks).** The PPL means are fragile by construction (one chunk moved the
   Q3 mean by 88% of its value). Before any of this is published, the PPL column needs the full
   corpus behind it.

## Toward the benchmark (buun, 2026-07-15: "we can make a benchmark that accurately shows quant quality… I don't think it will be cheap")

Design skeleton the campaign's receipts support — tiered so the cost lands only on finalists:

- **Tier 0 — paired NLL triage (~10 min/quant, reference-free):** per-token dumps on a
  validity-checked corpus battery → bulk (sign), tail (p99), span-masked stats + the
  **concordance flag** (bulk/tail disagreement ⇒ escalate, answer untrusted). A/B iteration only;
  never a ranking.
- **Tier 1 — distributional fidelity (~1–2 hr/quant, reference-based):** median + tail-percentile
  KLD + same-top vs parent on 2–3 corpora incl. in-distribution; parent logit dump is one-time
  per corpus. Goodhart-resistant core (optimizing toward it IS the objective).
- **Tier 2 — closed-loop capability (the irreducibly expensive truth):** multi-turn agentic runs
  with buun's seed-noise constraints (Q8-deterministic anchors, rates not flips, seed grids).
  Cost-cutter candidate replacing pass/fail: **per-turn drift rate** — generate closed-loop with
  the quant, teacher-force the parent over the quant's own trajectory, measure divergence growth
  per turn. Continuous (cannot ceiling), closed-loop (sees compounding teacher-forced NLL cannot),
  parent needed only as scorer. This is Module 2's slot; unbuilt.
- **Output is a verdict vector, not a scalar** — fidelity + capability + regime flags. Single
  scalars are how PPL lied.
- Where "not cheap" is TRUE and irreducible: Tier 2 sample counts (variance at decision boundaries
  forces seeds — his AIME lesson). Where it's beatable: gating (most quants die at Tier 0/1),
  amortized parent dumps, and P100-class hardware sufficing once arithmetic is carve-out-clean.

**Revisions after buun's 3:40 PM objections + re-reading his kv-eval-pack (2026-07-07,
`data/Apollo Docs/kv-eval-pack-20260707/`):**

1. **The drift-rate idea already exists in better form: hazard-L.** His hazard panel computes
   `L = KL / (0.5·margin²)` per token — divergence *weighted by decision margin*, so it only
   counts where it can actually flip a decision — plus `flip_excess` (net new tokens over the
   flip-hazard threshold vs anchor). Tier 2's per-turn drift becomes **per-turn flip-hazard
   rate**, margin-weighted, not raw KL drift. Credit where due: frac/flip anticipated this.
2. **The QAT objection is conceded in full — and his own INSIGHTS.md §1 states it:** "task
   accuracy is the only goodness court… a codec can beat f16 on a task while having worse
   hazard." Every fidelity-family tier is a **proxy admitted only with measured correlation to
   task truth** — his own validation is the template (median KLD vs TRUE argmax flips: ρ
   +0.82…+0.93, while the MEAN was anti-correlated at −0.39 on fine rungs). The benchmark's
   deepest structural fix: **it answers two different questions and must say which** —
   *"is this a transparent codec?"* (fidelity court — the right question for TCQ/VBR/K-quants)
   vs *"is this a good model?"* (task court — the only question for QAT/quant-finetunes, where
   beneficial divergence scores NEGATIVE on every fidelity metric by design). Conflating these
   two courts is the root confusion of all public quant discourse.
3. **His margin panel is the Tier-2 cost-cutter template — but buun's 3:51 PM objection
   restricts its jurisdiction, correctly.** "Extend the battery past NIAH" was a nice sentence
   with a broken reality: on CoT-mediated tasks (math), the final-answer logprob is conditioned
   on the generated chain — the chain IS the computation, externalized into sampled tokens — so
   the margin measures chain-consistency (a wrong chain confidently implies its wrong answer),
   not task ability. NIAH works precisely because no chain mediates: the answer is computed in
   the forward pass (attention retrieval), so its logprob measures the thing under test.
   **Admissibility rule: margin metrics are valid only for in-forward-pass tasks** (retrieval,
   recall, extraction, single-step judgment) — and the classification is itself measurable: a
   task qualifies iff its accuracy is unchanged with CoT suppressed. For CoT tasks the task
   court has no logprob shortcut; the price is buun's original constraints (parent-deterministic
   anchors, rates not flips, seed grids). Partial fidelity-court rescue enabled by the selfgen
   result: teacher-force quants over the PARENT'S OWN correct chains (on-manifold by
   construction — avoids the toolchain trap) and score margins on the chain's decision tokens.
   That measures "does the quant track the parent through the forks" — reasoning-shaped
   fidelity, NOT task ability (a differently-but-correctly-reasoning QAT scores badly by
   design). Pilot queued behind the overnight gates.
4. **Adopt his reliability discipline wholesale:** every published statistic carries same-run
   split-half ρ (his table: median/trim-1% reliable at ρ≈0.9, mean garbage at ρ≈±0.2);
   **never compare means across builds** (his receipt: a rebuild alone moved mean-KLD-excess
   sign; medians sat still). Checked against this week: all paired dump comparisons are
   same-build ✓; the corpus-panel table and dump-run logs come from different builds but agree
   to 4 decimals — do not mix them casually anyway.
5. **Convergent evidence note:** his {median, trim1%, hazard-L, true-flips} vs {mean, frac>τ}
   camp split (KV codecs, margin-validated) and this week's bulk-vs-tail split (weight tiers,
   sign-test vs mean) are the same structure found independently on different quantization
   axes. Mechanism per his data: catastrophe tokens are big-KL on big-margin tokens — they
   don't flip decisions; flips live where margins are thin.
6. **Zero-new-compute upgrade queued:** we hold the BF16 base logits file; his
   `hazard_metrics.py` extracts per-token margins from exactly that format. A small per-token
   KLD dump patch (mirror of the NLL one) makes hazard-L computable for OUR weight ladder —
   testing whether his camp structure holds on weight quants, against our same-top ground truth.

## Why this matters — the three instruments disagree by three full tiers

Put this next to the tool-call result and the campaign's real conclusion falls out:

- **Pick your quant by perplexity** → you ship **Q3_K_M**. It "beats" the BF16 original.
- **Pick your quant by KLD / same-top** → you ship **Q6_K**. That's where the tail is still contained.
- **Pick by the only *task* measurement we have** (24-case tool-call bench, full ladder, temp 0/0.4/0.7)
  → **Q3 was fine.** 24/24 every tier, 120/120 under sampling.

Three instruments, same five models, answers three tiers apart. This is the empirical core of
buun's objection — *"quants degrade in surprising and random ways… KLD is the best we can do but
it's not the full story"* — and it is now a receipt rather than an intuition. Note it did **not**
take QAT to produce a "worse KLD, better score" model: **a stock unsloth K-quant does it.**

**The load-bearing caution, including for our own published work:** a lower perplexity is *not*
evidence of a better model. Our own Q3 proves it. So any claim of the form "QAT has worse KLD but
performs better" needs a **capability** measurement to stand up — PPL cannot carry it, because PPL
demonstrably inverts. Same warning applies to every "my Q4 has lower PPL than my Q5, quantization
is free" post on r/LocalLLaMA: that is this artifact, and it is measuring the flattening, not the
model.

## PUBLICATION GATES CLOSED (2026-07-16, full-corpus wiki runs — receipts `wikifull_*.log`)

The 32-chunk PPL means were flagged as outlier-fragile (chunk 7 alone moved Q3's mean by 88% of
its value). The full corpus (~5× the chunks) answers:

| model | full-corpus PPL | ±(marginal) |
|---|---|---|
| STOCK-NOIMAT (Q3 recipe) | **6.4385** | 0.042 |
| Q3_K_M (shipped) | 6.6045 | 0.044 |
| Q8_0 | 6.6532 | 0.045 |
| **BF16 (the parent)** | 6.6644 | 0.045 |
| Q6_K | 6.6815 | 0.046 |
| Q5_K_M | 6.7039 | 0.046 |
| STOCK-IMAT (Q3 recipe) | 6.7407 | 0.046 |
| Q4_K_M | 6.7593 | 0.046 |

**Every headline claim survives, most get stronger:**
- **The inversion is not an outlier artifact.** Q3_K_M still beats BF16 (−0.9%); the no-imatrix
  stock Q3 still beats everything by a wide margin (−3.4% vs parent, ~5σ marginal); Q4_K_M is
  still dead last. Even Q8_0 edges its own parent (−0.17%, within noise but directionally
  on-theme). On the full corpus, mean PPL's two favorite models are the two most damaged ones
  in the set.
- **"The imatrix costs PPL" reproduces exactly:** IMAT 6.7407 vs NOIMAT 6.4385 = 4.7% — the
  same 4.7% as at 32 chunks. That number is now robust.
- Non-monotone throughout: full-corpus PPL ordering is NOIMAT < Q3 < Q8 < BF16 < Q6 < Q5 <
  IMAT < Q4. Anyone who ranks these eight files by perplexity ranks them nearly backwards.

With the storage-compression loose end resolved below and the base numbers now full-corpus,
the doc's publication gates are all green.

## Loose end — RESOLVED 2026-07-15: the 0.33% BF16 gap is the base file's own compression

The standalone BF16 PPL (6.5376/6.5377) vs the KLD-embedded base PPL (6.5159) discrepancy is
**not flags, not chunk count, not build drift**. Receipts, in order:
1. BF16 re-run at the EXACT KLD geometry (`wikifull_BF16_32ch_kldgeom.log`): **6.5377** — the
   standalone number reproduces across two builds two days apart, killing the build-drift
   explanation and the flags explanation simultaneously.
2. Mean true-token NLL computed DIRECTLY from the stored base-logits file
   (`kld_base_ppl_check.py`, format per buun's hazard extractor): **1.874247 nats ⇒ PPL 6.5159 —
   exact match to the KLD-embedded number.**

The `.kld` base file stores log-probs u16-quantized (per-token scale/min). That storage
round-trip lowers reconstructed mean NLL by 0.0033 nats (−0.33% PPL). **The instrument's own
storage layer moves PPL by a third of a percent — in the flattering direction.** One more entry
for "too easy to fraud": you don't even need a quantizer; the logging format does it.

Consequences audited:
- Every `Mean PPL(Q)/PPL(base)` ratio in KLD runs compares a LIVE quant against the STORED base
  ⇒ ratios were biased ~+0.33% **against** the quants. Q3-beats-BF16 therefore *strengthens*
  (ln-ratio −0.012 vs stored base → ≈ −0.015 vs live base). No finding weakens.
- IMAT/NOIMAT and every quant-vs-quant comparison shared one base file ⇒ deltas unaffected.
- KLD values themselves inherit a small storage-noise floor, equal for all tiers scored against
  the same file ⇒ orderings unaffected; absolute medians near 1e-6 should be read as
  floor-adjacent. Rule adopted: **never mix live and file-reconstructed PPLs in one comparison**
  (the cross-pipeline analog of buun's never-compare-means-across-builds).
