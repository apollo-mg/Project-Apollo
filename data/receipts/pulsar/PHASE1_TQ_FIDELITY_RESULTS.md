# TurboQuant weights lose to k-quants on fidelity-per-bit — first measurement

**2026-08-04.** Node `.73`, build `d0e2a8b64` (Phase-0 validated: `test-backend-ops` MUL_MAT
1344/1344, 3/3 backends, 278 TQ cases, 0 FAIL, 0 NaN). Single P100, `-ngl 99`.

Base: `unsloth/Qwen3.5-4B-GGUF` → `Qwen3.5-4B-BF16.gguf` (8,424,393,632 B, `qwen35`, 426 tensors,
249 BF16 + 176 F32, vocab 248,320). Every arm produced **by us** from that one file with
`llama-quantize --pure`, **no imatrix on any arm**.
Corpus: `wikitext-2-raw` `wiki.test.raw`, `-c 512 --chunks 20` → **5,100 scored tokens**, identical
across arms (paired comparison). Reference KLD file 2,532,945,780 B.

## Results

bpw is **measured from tensor offsets**, not from labels:

| arm | measured bpw | Mean KLD | **Median KLD** | 99% KLD | Max KLD | Same top-1 | PPL(Q)/PPL(base) |
|---|---|---|---|---|---|---|---|
| TQ3_1S | **4.00** | 0.2185 | **0.1381** | 1.6417 | 13.26 | 77.90 ± 0.58 % | 1.1366 ± 0.0124 |
| IQ4_XS | **4.25** | 0.0612 | **0.0343** | 0.4099 | 5.88 | 87.49 ± 0.46 % | 1.0087 ± 0.0061 |
| Q4_K_S | **4.50** | 0.0512 | **0.0288** | 0.4193 | 11.08 | 89.29 ± 0.43 % | 1.0431 ± 0.0063 |
| **TQ4_1S** | **5.00** | 0.0538 | **0.0276** | 0.3300 | **19.35** | 89.33 ± 0.43 % | 1.0478 ± 0.0054 |
| Q5_K_S | **5.50** | 0.0172 | **0.0073** | 0.1090 | 9.25 | 94.04 ± 0.33 % | 1.0222 ± 0.0032 |

Reference PPL(base) = 10.139 ± 0.392.

## Headline: TQ sits *above* the k-quant curve at both bit budgets

Fitting ln(median KLD) against bpw through the k-/i-quant points and interpolating to 5.00 bpw
(between Q4_K_S 4.50 → 0.0288 and Q5_K_S 5.50 → 0.0073) gives an expected **0.0146**.
TQ4_1S measures **0.0276** — **1.9× worse than a conventional quant at the same bit budget**.

Read the other way: TQ4_1S at **5.00 bpw** delivers the median KLD a k-quant reaches at
**≈4.53 bpw**. **TQ costs about 0.47 bpw (~10%) for equal fidelity.**

TQ3_1S is worse still. At **4.00 bpw** its median KLD is **4.0×** that of IQ4_XS at 4.25 bpw, with
same-top-1 **9.6 points** lower (77.9% vs 87.5%) and perplexity **13.7%** above the reference — a
visibly degraded model, where IQ4_XS at only 0.25 bpw more is near-lossless on PPL (+0.87%). No
conventional point below 4.25 bpw was measured, so a bpw-equivalent cannot be estimated for
TQ3_1S — but the gap is far larger than 0.25 bpw could explain.

## This was TQ's best case

`quantize_tq4_1s()` opens with `GGML_UNUSED(imatrix);` — **TQ cannot use importance calibration.**
So every arm here ran uncalibrated, which is the comparison most favourable to TQ: its premise (WHT
rotation → near-Gaussian → Lloyd-Max levels) is purely distributional and needs no calibration,
while k-/i-quants are designed expecting one and were denied it.

**TQ lost anyway.** Adding an imatrix (Phase 2) can only move the conventional quants further ahead.

## Where TQ *does* look good, and why it doesn't rescue the result

TQ4_1S has the **best 99% KLD (0.330)** and **lowest RMS Δp (5.94%)** of the sub-5.5 bpw arms, and
edges Q4_K_S on median KLD (0.0276 vs 0.0288) — so its error distribution is tighter through the
body. But it needed **11% more bits** (5.00 vs 4.50) to achieve that near-tie, and it posts the
**worst maximum KLD of any arm (19.35)**. Tight in the body, worse in the extreme tail.

## Two methodological notes worth keeping

**1. PPL ranks differently from KLD, and KLD is right.** IQ4_XS has the *best* PPL ratio of any arm
(1.0087, better even than Q5_K_S at 1.0222) while sitting 4th of 5 on median KLD. PPL only scores
the true token's log-probability; KLD scores the whole distribution. A quant can preserve the
target token while distorting everything else. **Anyone ranking quants by perplexity alone would
conclude IQ4_XS beats Q5_K_S, which the distributional evidence contradicts.**

**2. `--pure` makes Q4_K_S and Q4_K_M bit-identical.** Both produced 2,380,008,352 bytes with the
*same md5 over the entire tensor-data region*; they differ only in the `general.file_type` KV
(14 vs 15), at byte 10,942,832. The S/M/L distinction is entirely about which tensors get bumped to
Q5_K/Q6_K, which `--pure` disables by definition. The Q4_K_M arm was dropped as a duplicate.
**A `--pure Q4_K_S` vs `--pure Q4_K_M` comparison measures one metadata byte.**

## Scoring the pre-registration (`PHASE1_LADDER_PREDICTIONS.md`)

- **P-F1 (0.6) — technically confirmed, substantively misleading.** TQ4_1S does edge `--pure` Q4_K
  on median KLD (0.0276 vs 0.0288). But the prediction assumed Q4_K_M ≈ 4.85 bpw; under `--pure` it
  is **4.50**, so TQ4_1S won a near-tie while spending **11% more bits**, not 3%. Counted as a win
  for the letter of the prediction and a loss for its reasoning.
- **P-F2 (0.55) — CONFIRMED, and by far more than expected.** TQ3_1S loses to IQ4_XS: 4.0× the
  median KLD, 9.6 points of same-top-1. I predicted a narrow loss; it is a rout.
- **P-F3 (0.7) — CONFIRMED.** TQ4_1S loses to Q5_K_S (0.0276 vs 0.0073, 3.8×).
- **P-F4 (0.85) — FALSIFIED.** Measured **per-type** bpw is *exactly* nominal on every arm
  (4.00 / 4.25 / 4.50 / 5.00 / 5.50). The intuition held only at whole-file level, which is not what
  was measured or what the plot's x-axis uses.
- **P-F5 (0.75) — CONFIRMED.** All arms quantized without error.

First session where the predictions were mostly right; the one that mattered (P-F2) was right for
weaker reasons than the size of the effect warranted.

## Limitations — stated because this is a negative result about someone's work

1. **One model, one size, one corpus — and it is not a vanilla transformer.** Qwen3.5-4B on
   wikitext-2 test. The tensor list shows it is an **attention/SSM hybrid**: alongside `attn_qkv`
   and `attn_gate` every block carries `ssm_a`, `ssm_alpha`, `ssm_beta`, `ssm_conv1d`, `ssm_dt.bias`,
   `ssm_norm`, `ssm_out`. State-space weights may have different distributional character from
   attention/FFN weights, and TQ's rotate-to-Gaussian premise is distribution-sensitive by
   construction. **A pure-transformer replication is therefore not optional** — it is running on
   Llama-3.2-3B (Stage D of `~/tq_chain.sh`), at 60 chunks (~15,400 scored tokens, 3× Phase 1,
   affordable because Llama's 128,256 vocab halves the per-token logits cost). Curve *shape* at 27B
   is separately unverified (Phase 3).
2. **5,100 scored tokens** — modest. Mitigated by pairing (identical tokens, identical reference for
   every arm), but the absolute KLD values are less stable than a 100k-token run would give.
   Constrained by disk: the KLD file stores the full 248,320-entry vocab as 16-bit log-probs,
   ~497 kB **per token**.
3. **`--pure` is not what ships.** It forces `token_embd` and `output` to the target type for every
   arm. Applied equally, so the ranking is fair, but absolute damage is larger than shipped mixes.
   ⚠️ **This is the most important untested confound**: if TQ handles embeddings especially badly,
   `--pure` penalises it more than its rivals. The clean control — pin `--token-embedding-type` and
   `--output-tensor-type` to Q8_0 on *all* arms and vary only the body — is cheap and should be run
   before this result is published.
4. Quantizer correctness itself is untested. Phase 0 validated the *inference* path
   (`test-backend-ops`); it does not prove `quantize_row_tq4_1s_ref` is optimal or bug-free. The
   results are consistent with a working-but-uncalibrated method rather than a broken one, but
   "TQ's quantizer has a bug" is not excluded.

## ✅ CONTROL PASSED — the result is about formats, not embedding handling

The load-bearing confound: `--pure` forces `token_embd` (635,699,200 elements ≈ 16% of parameters)
to the target type, so a format that handles embeddings badly is penalised beyond its true cost.

Control: identical ladder with `--token-embedding-type Q8_0 --output-tensor-type Q8_0` on **every**
arm, so only body tensors vary. Same base, same reference logits, same 5,100 scored tokens.

| arm | body bpw | median KLD (control) | median KLD (`--pure`) | same top-1 (control) | (`--pure`) |
|---|---|---|---|---|---|
| TQ3_1S | 4.00 | 0.093465 | 0.138079 | 80.863 % | 77.902 % |
| IQ4_XS | 4.25 | 0.024227 | 0.034307 | 90.098 % | 87.490 % |
| Q4_K_S | 4.50 | 0.021333 | 0.028840 | 90.627 % | 89.294 % |
| **TQ4_1S** | **5.00** | **0.019986** | 0.027565 | 90.333 % | 89.333 % |
| Q5_K_S | 5.50 | 0.005746 | 0.007343 | 94.667 % | 94.039 % |

**Every arm improved and the ordering is identical.** Protecting the embedding lifts all formats by
a similar factor rather than rescuing any one of them.

Re-deriving the headline on control numbers — interpolating ln(median KLD) between Q4_K_S (4.50 →
0.021333) and Q5_K_S (5.50 → 0.005746) predicts **0.01108** at 5.00 bpw; TQ4_1S measures
**0.019986**:

| | `--pure` | **control** |
|---|---|---|
| TQ4_1S vs k-quant curve at 5.00 bpw | 1.89× worse | **1.80× worse** |
| bpw TQ gives up for equal fidelity | ~0.47 | **~0.45** |
| TQ3_1S (4.00) vs IQ4_XS (4.25), median KLD | 4.02× | **3.86×** |

The confound accounts for **~0.02 bpw of a ~0.45 bpw effect.** The Phase 1 conclusion stands.

## ✅ REPLICATED on a second architecture — Llama-3.2-3B

`unsloth/Llama-3.2-3B-Instruct-BF16.gguf` (6,433,687,744 B), **pure transformer**, vocab 128,256.
Same method, same corpus, `--pure`, no imatrix — but **60 chunks ≈ 15,400 scored tokens, 3× the
Qwen run**, affordable because the smaller vocab halves the per-token logits cost (reference file
3,924,878,900 B).

| arm | bpw | median KLD | mean KLD | 99 % KLD | same top-1 |
|---|---|---|---|---|---|
| TQ3_1S | 4.00 | 0.208178 | 0.326034 | 2.286328 | 74.359 % |
| **IQ4_XS** | **4.25** | **0.032446** | 0.051846 | 0.369308 | 88.908 % |
| **TQ4_1S** | **5.00** | 0.035231 | 0.055477 | 0.393210 | 88.431 % |
| Q4_K_S | 4.50 | 0.039861 | 0.063499 | 0.454613 | 88.190 % |
| Q5_K_S | 5.50 | 0.009022 | 0.014742 | 0.102816 | 93.837 % |

Interpolating the k-quant curve (Q4_K_S 4.50 → 0.039861, Q5_K_S 5.50 → 0.009022) gives **0.018972**
expected at 5.00 bpw against TQ4_1S's measured **0.035231**.

| | Qwen3.5-4B (control) | **Llama-3.2-3B** |
|---|---|---|
| architecture | attention/SSM hybrid | **pure transformer** |
| vocab | 248,320 | 128,256 |
| scored tokens | 5,100 | **15,400** |
| TQ4_1S vs k-quant curve @ 5.00 bpw | 1.80× worse | **1.86× worse** |
| bpw TQ gives up | ~0.45 | **~0.42** |

**The effect replicates across architecture, tokenizer, size and token count.**

Sharper still on Llama: **IQ4_XS at 4.25 bpw beats TQ4_1S at 5.00 bpw outright** (0.032446 vs
0.035231) — TQ losing to a format spending **15 % fewer bits**, without any imatrix on either side.

Note the k-/i-quant ordering itself is *not* architecture-stable: on Qwen, Q4_K_S (4.50) beats
IQ4_XS (4.25); on Llama the order reverses. That such rankings move between models while **TQ's
deficit stays put (1.80× / 1.86×)** makes the TQ result more credible, not less.

⚠️ Two reporting caveats. The chain logged `(32.00 bpw)` for every Llama arm — a bug in the label
extraction (it grabbed the first `B per 32` line, an F32 tensor), not a data problem; bpw is a fixed
property of each format and was measured directly on the Qwen arms. And the Llama arms were deleted
after scoring to bound disk, so their bpw was **not** independently re-measured.

## Phase 2 — what calibration is worth, and the practical gap

imatrix generated from `wiki.train.raw`, 100 chunks (`llama-imatrix`, 3,626,496 bytes). Same base,
same reference logits, same 5,100 scored tokens, all `--pure`.

| arm | bpw | median KLD, no imatrix | median KLD, **with imatrix** | improvement |
|---|---|---|---|---|
| IQ4_XS | 4.25 | 0.034307 | **0.025361** | −26.1 % |
| Q4_K_S | 4.50 | 0.028840 | **0.018978** | −34.2 % |
| Q5_K_S | 5.50 | 0.007343 | **0.004992** | −32.0 % |
| TQ4_1S | 5.00 | 0.027565 | *impossible* | — |
| TQ3_1S | 4.00 | 0.138079 | *impossible* | — |

**Calibration is worth ≈0.30 bpw.** A ~32 % median-KLD reduction against the fitted k-quant slope
(≈1.37 ln-KLD per bpw) converts to `ln(0.68)/1.37 ≈ 0.28–0.30 bpw` of equivalent fidelity, obtained
for free from a corpus pass.

### The practical comparison (Q-B): what you should actually download

**Q4_K_S with an imatrix, at 4.50 bpw, beats TQ4_1S at 5.00 bpw by 1.45× on median KLD**
(0.018978 vs 0.027565) — while using **10 % fewer bits**.

Stacking the two deficits: ~0.45 bpw of format disadvantage (control-corrected) plus ~0.30 bpw of
forgone calibration ≈ **0.75 bpw total** versus a shipped k-quant. At these bit budgets that is
substantial.

### ✅ TQ provably ignores the imatrix — verified by bytes, not by reading the source

Quantized `TQ4_1S` twice from the identical base, once with `--imatrix` and once without:

```
with imatrix : 2,642,807,968 B   data_start 10,968,224   46 KVs
without      : 2,642,807,712 B   data_start 10,967,968   42 KVs
KV delta     : quantize.imatrix.{file,dataset,entries_count,chunks_count}
```

The **256-byte** file-size difference is *exactly* the header shift from those four KVs. Comparing
each tensor's real byte range, aligned to each file's own data-section offset:

| tensor | bytes | result |
|---|---|---|
| `blk.0.ffn_down.weight` | 14,745,600 | **IDENTICAL** |
| `blk.5.attn_qkv.weight` | 13,107,200 | **IDENTICAL** |
| `blk.10.ffn_gate.weight` | 14,745,600 | **IDENTICAL** |
| `token_embd.weight` | 397,312,000 | **IDENTICAL** |

Supplying an imatrix to TQ changes four metadata strings and nothing else.

⚠️ **Correction:** the automated first pass (`~/tq_chain.sh` stage B1) reported *"data regions
DIFFER → TQ DOES use it; source read was wrong."* **That verdict was an artefact of my own test.**
It compared both files from a fixed byte offset (`tail -c +12000000`), which the 256-byte header
shift misaligns — guaranteeing a hash mismatch regardless of content. Tooling: `~/cmp_tensor.py`,
which resolves each file's data-section start and each tensor's offset before hashing. The lesson
generalises: **any byte comparison across GGUFs must align to the data section**, because optional
KVs move it.

## Is the TQ quantizer immature, or just differently designed?

Asked because a negative result should distinguish "the idea is weaker" from "the implementation is
unfinished." Evidence says **competently implemented, weaker objective**.

### It is not naive

`quantize_row_tq4_1s_ref` (`ggml/src/ggml-turbo-quant.c`) does:

1. forward RHT over the 32-element block
2. per-half RMS (two scales `d0`, `d1` per block)
3. **a 9-point scale search** (`0.6 … 1.5 × rms`)
4. **6 iterations of alternating refinement** — re-assign to centroids, least-squares update the
   scale, repeat

That is structurally the same family as k-quants' `make_qkx*_quants`. "Not optimized at all" is not
supported.

### But its objective is weaker, at two levels

TQ minimises **unweighted** squared error: `err += diff*diff`.

`quantize_row_q4_K_ref` — the path used when **no imatrix is supplied** — does:

```c
for (int l = 0; l < 32; ++l) weights[l] = av_x + fabsf(x[32*j + l]);
scales[j] = make_qkx2_quants(32, 15, x + 32*j, weights, L + 32*j, &mins[j], Laux, -1.f, 0.1f, 20, false);
```

i.e. **magnitude-weighted** error with a **20-step** search. So the importance gap is *two* levels
deep, not one:

| | external calibration (imatrix) | internal weighting (free, from the data) |
|---|---|---|
| k-quants | yes (when supplied) | **yes — `av_x + \|x\|`, always** |
| TQ | **no — `GGML_UNUSED(imatrix)`** | **no — unweighted MSE** |

In fairness to the design: RHT is orthogonal, so MSE is preserved under rotation, and the rotation's
purpose is precisely to spread outliers so that no element needs prioritising. TQ is making a
deliberate bet that **rotation substitutes for weighting**. The measurements say the bet does not
fully pay at these bit budgets.

### Direct reconstruction error (`test-quantize-fns -v`)

| type | bpw | absolute quantization error | **dot product error** |
|---|---|---|---|
| q6_K | 6.56 | 0.000261 | 0.000211 |
| q5_K | 5.50 | 0.000531 | 0.001038 |
| q4_K | 4.50 | 0.000982 | 0.002318 |
| iq4_xs | 4.25 | 0.001256 | 0.002499 |
| **tq4_1s** | **5.00** | 0.001615 | **0.009869** |
| **tq3_1s** | **4.00** | 0.003371 | **0.034097** |

TQ4_1S at 5.00 bpw reconstructs worse than IQ4_XS at 4.25, and its dot-product error is **4.3×**
q4_K's and **9.5×** q5_K's. TQ3_1S is **14.7×** q4_K's.

**`reference implementation error` is 0.000000 for every type**, so the SIMD/optimised paths match
their scalar references exactly — this is not an optimised-path bug.

⚠️ **Heavy caveat — this benchmark is structurally unfair to TQ.** Its test signal is
`dst[i] = 0.1 + 2*cosf(i + offset)`: a deterministic sinusoid, which is **arcsine-distributed**
(U-shaped, mass concentrated at the extremes) — nearly the opposite of Gaussian. TQ's premise is
*rotate toward Gaussian, then apply Lloyd-Max levels optimal for a Gaussian*, while k-quants'
min/max scaling suits bounded data well. These numbers should be read as **directional
corroboration only**, not as the primary evidence.

The two measurements together tell a consistent story: on synthetic anti-Gaussian data TQ is far
behind (expected, unfavourable), and on **real transformer weights — its favourable case — the gap
narrows to ~1.9× at equal bits but does not close.**

## Practical reading

On this evidence, **for weights**, TQ is not a fidelity win: at equal bits it is ~1.9× worse in
median KLD than k-quants, and TQ3_1S at 4.00 bpw is not a usable operating point (77.9% same-top).
This does **not** speak to TQ for **KV cache**, which is where its published wins are and where the
error budget and access pattern are entirely different.

The constructive reading is the imatrix gap: TQ discards calibration information its competitors
exploit. **TQ + imatrix is unimplemented**, and is the obvious place to look for the missing bits.
