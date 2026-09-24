# Quantization does not single out hesitation tokens: their 1.2-1.4x raw KLD excess is entropy, and at matched entropy "Wait"/"But"/"Maybe" positions take LESS damage

**2026-09-24**, `.194` (4x P100, 1063 MHz / 150 W), buun `08826ad6e` `llama-perplexity`, `-c 2048 -b 512 -ub 512
-fa on`, f16 KV, `-sm layer`, identical flags on every arm. Prereg: `PREREG_HESITATION_KLD.md` (written before any
KLD pass). Registered scorer: `analyze_hes.py` (unchanged, sha256 `a4520952c30faee4...`). Raw: `raw/`.

## What the source actually says (re-read after scoring; the prereg's paraphrase drifted)

Lotfi et al., "Quantized reasoning models" (blog, shared by buun), DeepSeek-R1-Distill-Qwen-1.5B on MATH-500, BF16 vs
3-bit AWQ, both models run under identical generation prefixes:
- They average KL **per token type** (types with >= 50 occurrences) and plot the 20 highest and 20 lowest. The
  highest are overthinking markers; the lowest are math and formatting tokens. Their "~100x" is the ratio of the
  **largest value on each plot** (1.30 vs 0.015), not a ratio of class means.
- **They already attribute this to uncertainty:** position-level KL correlates with BF16 next-token entropy at
  Spearman rho = 0.92, and "quantization most affects positions where the model is already uncertain".
- Separately, a logit penalty on 50 curated markers shortens CoT by 12-23 % across 5 models.

The prereg described the claim as "~100x at hesitation markers vs math tokens" and the entropy control as something
"the source does not report". Both overstate it. The source reports the entropy correlation; what it does not
report is a **class-conditional comparison at matched entropy**, which is what this test adds. Read that way, this
result **agrees** with the source's mechanism and sharpens it.

## Setup, as run

- Reference **Qwen3.8-27B Q8_0** (29,047,086,048 B) wrote the uint16 base; each arm ran `--kl-divergence` with a
  per-position `TURBO_KLD_DUMP`.
- Corpus `corpus_reasoning.txt` (sha256 `7dcbf42b...`, 215 stock-Qwen3.8 traces): **123 chunks x 1,023 scored
  positions = 125,829 positions**, of which **945 are HES** (next token is one of the 10 registered markers).
- **The HES count was checked against the corpus before scoring.** The corpus holds 1,967 capitalized marker words
  and 945 (48 %) fall in scored positions, matching the ~50 % of tokens that are scored. Per marker: But 382/798,
  Maybe 301/614, Wait 105/206, Actually 70/158, Hmm 62/133, However 21/49, Perhaps 2/7, Alternatively 2/2;
  `Hold` and `Oh` never occur. Every marker has a single-token form in the vocab (20 token ids), so the matcher's
  single-token rule loses nothing here.

| arm | file bytes | mean KLD | HES KLD | **raw HES/OTHER** [95 % CI] | **entropy-matched** [95 % CI] |
|---|---:|---:|---:|---:|---:|
| UD-Q2_K_XL | 9,828,981,664 | 0.07380 | 0.10210 | 1.39 [1.26, 1.52] | **0.69** [0.63, 0.74] |
| UD-IQ3_XXS | 11,913,559,104 | 0.03980 | 0.04754 | 1.20 [1.07, 1.33] | **0.59** [0.53, 0.65] |
| UD-IQ4_XS | 14,252,845,984 | 0.01232 | 0.01711 | 1.39 [1.24, 1.56] | **0.67** [0.61, 0.74] |
| UD-Q4_K_M | 16,464,440,224 | 0.00585 | 0.00801 | 1.37 [1.24, 1.52] | **0.65** [0.59, 0.71] |
| Q6_K | 22,884,408,288 | 0.00110 | 0.00153 | 1.39 [1.26, 1.54] | **0.66** [0.60, 0.72] |

CIs: percentile bootstrap over chunks, 10,000 resamples, as registered. Mean reference entropy: **HES 1.611 nats,
OTHER 0.716** (2.25x).

## Scored against the prereg

| # | registered claim | result | verdict |
|---|---|---|---|
| H1 | raw HES/OTHER > 3 in every arm, CI lower bound > 1 | 1.20-1.39; every CI lower bound > 1, but no arm is near 3 | **FALSE** |
| H2 | entropy-matched ratio > 1.5 in the two lowest-bit arms, CI lower bound > 1 | 0.69 and 0.59, **CI entirely below 1** in every arm | **FALSE, reversed** |
| H3 | raw ratio at Q2_K_XL > at Q6_K (difference CI excludes 0) | 1.39 vs 1.39, difference CI [-0.118, +0.107] | **FALSE** |
| H4 | HES-KLD separation (Q2_K_XL / Q6_K) > mean-KLD separation | 66.73 vs 66.92 (no CI registered) | **FALSE** (equal) |

**Registered reading:** H1 false -> "the source's effect does not transfer to imatrix GGUF quants" at the
registered threshold. Given the section above, the better wording is: *the word-specific version of the effect,
which the prereg attributed to the source, does not exist here.* The reading table has no row for H2 *reversing*;
that part is an unregistered observation, examined below.

## Exploratory (not registered)

`explore_hes.py` and `explore2_hes.py`, run after scoring. The first recomputes the same float64 entropy (its decile
edges reproduce the registered ones exactly) and saves per-position entropy and reference top-1 probability. The
second exports the token ids and class masks (`raw/hes_tokens.npz`). With those and `raw/dumps/`, every number here
reproduces without the 62 GB base: checked on the desktop from `raw/` alone (n_hes 945, Q2_K_XL raw 1.3874,
entropy-matched 0.6855, identical to the registered output).

### E1. How good is the registered entropy matching?

Deciles are numbered 1-10 below (decile 1 holds no HES).
- In deciles 2-9, HES and OTHER mean entropy differ by at most 0.03 nats. In deciles 5, 7, 8 and 9 HES entropy is
  slightly *higher*, so the registered match is conservative there.
- In the top decile (2.03-6.9 nats, 300 of the 945 HES), HES averages 2.37 nats against 2.64 for OTHER. OTHER's
  higher entropy there inflates its KLD and pushes the ratio **down**. That is why tighter matching moves it up.

### E2/E3/E5. Tighter matching: ~0.66 -> ~0.71, and nothing crosses 1

| arm | deciles (registered) | 50 bins | 100 bins | **20 nearest neighbours in H** | top-1-prob deciles | top-1-prob 50 bins |
|---|---:|---:|---:|---:|---:|---:|
| UD-Q2_K_XL | 0.69 [0.63, 0.74] | 0.71 [0.66, 0.77] | 0.71 [0.66, 0.77] | **0.72 [0.66, 0.79]** | 0.71 [0.65, 0.76] | 0.71 [0.65, 0.76] |
| UD-IQ3_XXS | 0.59 [0.53, 0.65] | 0.62 [0.57, 0.68] | 0.63 [0.58, 0.68] | **0.64 [0.59, 0.69]** | 0.60 [0.55, 0.66] | 0.61 [0.55, 0.67] |
| UD-IQ4_XS | 0.67 [0.61, 0.74] | 0.70 [0.64, 0.77] | 0.71 [0.65, 0.77] | **0.73 [0.66, 0.80]** | 0.69 [0.62, 0.75] | 0.69 [0.63, 0.75] |
| UD-Q4_K_M | 0.65 [0.60, 0.72] | 0.69 [0.63, 0.75] | 0.69 [0.63, 0.75] | **0.71 [0.65, 0.78]** | 0.67 [0.61, 0.73] | 0.67 [0.61, 0.73] |
| Q6_K | 0.66 [0.60, 0.72] | 0.69 [0.64, 0.75] | 0.69 [0.64, 0.76] | **0.73 [0.67, 0.79]** | 0.67 [0.61, 0.73] | 0.67 [0.61, 0.74] |

- Bin CIs: chunk bootstrap, 2,000 resamples. Nearest-neighbour CIs: 500 resamples over a fixed match set.
- Nearest-neighbour matching is near-exact: mean |dH| between a HES position and its matches is 0.0003 nats.
- **Best estimate: hesitation positions take ~27-36 % less KLD than positions of the same entropy**, in every arm
  and under every matching scheme, including matching on top-1 probability.

### E7. About half of that is "sentence start", not "hesitation word" (confound check)

91 % of HES positions follow a sentence or line end. SSTART = the 5,644 **non-HES** positions whose context token
ends a sentence or line and whose next token starts with a capital letter. Their mean entropy (1.607 nats) is
almost exactly HES's (1.611).

| arm | (a) SSTART vs OTHER, matched on H | (b) **HES vs SSTART**, matched on H |
|---|---:|---:|
| UD-Q2_K_XL | 0.83 [0.78, 0.89] | **0.83 [0.77, 0.89]** |
| UD-IQ3_XXS | 0.74 [0.70, 0.79] | **0.81 [0.74, 0.87]** |
| UD-IQ4_XS | 0.80 [0.74, 0.87] | **0.85 [0.76, 0.94]** |
| UD-Q4_K_M | 0.78 [0.72, 0.85] | **0.85 [0.76, 0.94]** |
| Q6_K | 0.81 [0.76, 0.87] | **0.83 [0.77, 0.90]** |

20 nearest neighbours in H, chunk bootstrap 500 (mean |dH| 0.0005 and 0.003 nats).
- **(a) Sentence starts in general are protected**, ~17-26 % below other positions of the same entropy.
- **(b) Hesitation markers are protected even among sentence starts**, ~15-19 % below them. Every CI excludes 1.
- The two compound to the overall ~0.7 (e.g. Q2_K_XL: 0.83 x 0.83 = 0.69).

### E6. The source's own statistic on this data

Mean KLD per next-token type, 333 types with >= 50 occurrences, top 20 vs bottom 20:

| arm | largest high | largest low | ratio | markers in top 20 | marker ranks (of 333) |
|---|---:|---:|---:|---:|---|
| UD-Q2_K_XL | 0.221 (` e`) | 0.0103 | 21x | **1** (` Maybe`, #19) | ` Actually` 38, ` Hmm` 43, ` But` 68, `But` 93, ` Wait` 151, `Maybe` 158 |
| UD-IQ3_XXS | 0.185 (`stead`) | 0.0053 | 35x | **0** | ` Maybe` 34, ` Hmm` 53, ` Actually` 64, ` But` 86, `But` 110, `Maybe` 113, ` Wait` 227 |

On this model and corpus the top of the ranking is **not** dominated by overthinking markers. It holds generic
connective and instruction words (` use`, ` ensure`, ` The`, ` So`, `Thinking`) and word fragments. The bottom is
deterministic subword continuations. The range ratio (21-35x) is below the source's ~100x, but the corpus, model
size and codec all differ, so the size of that gap is not a finding.

### E4. HES vs digit tokens (class means)

| arm | KLD at HES | KLD at digit (8,510 positions, mean H 0.22) | HES / digit |
|---|---:|---:|---:|
| UD-Q2_K_XL | 0.1021 | 0.0467 | 2.19 |
| UD-IQ3_XXS | 0.0475 | **0.0425** | 1.12 |
| UD-IQ4_XS | 0.0171 | 0.0102 | 1.67 |
| UD-Q4_K_M | 0.0080 | 0.0049 | 1.65 |
| Q6_K | 0.0015 | 0.0011 | 1.36 |

This is a class-mean ratio, not the source's statistic (that is E6).

**Retracted (same day): "IQ3_XXS has a codec-specific digit weakness".** An earlier version of this receipt said so,
because IQ3_XXS's digit KLD is 91 % of Q2_K_XL's at 54 % of its mean KLD. Normalizing digit KLD by each arm's own
mean KLD removes it:

| | Q2_K_XL | IQ3_XXS | IQ4_XS | Q4_K_M | Q6_K |
|---|---:|---:|---:|---:|---:|
| digit KLD / arm mean KLD | **0.63** | 1.07 | 0.83 | 0.83 | 1.02 |
| digits' share of the arm's total KLD (6.8 % of positions) | 4.3 % | 7.2 % | 5.6 % | 5.6 % | 6.9 % |

IQ3_XXS matches Q6_K. The outlier is Q2_K_XL, which is unusually light on digits. What remains is a per-token
oddity, not a class effect: IQ3_XXS ranks `9`, `7` and `8` in its E6 top 20 (`9` at 3.5x its mean). No other
arm has more than one digit there. That could be a handful of positions and has no CI.

### E8. How concentrated is the damage in uncertain positions?

Share of each arm's total KLD carried by the most uncertain positions (by reference entropy):

| arm | top 5 % | top 10 % | top 20 % | top 30 % | top 50 % |
|---|---:|---:|---:|---:|---:|
| UD-Q2_K_XL | 15.9 % | 27.4 % | 48.5 % | 66.7 % | 90.7 % |
| UD-IQ3_XXS | 17.6 % | 28.6 % | 48.9 % | 66.6 % | 91.0 % |
| UD-IQ4_XS | 17.1 % | 28.9 % | 50.4 % | 68.3 % | 92.7 % |
| UD-Q4_K_M | 17.3 % | 29.0 % | 50.8 % | 69.3 % | 94.2 % |
| Q6_K | 17.4 % | 29.2 % | 51.3 % | 69.6 % | 94.0 % |

Concentrated, but not sharply: shielding the most uncertain 20 % of positions would address about half the
damage, and every arm has the same curve. Any "protect uncertain positions" scheme should be priced against this.

## What it means

1. **Quantization damage follows the reference model's uncertainty, not the word.** This agrees with the source
   (rho = 0.92). The raw 1.2-1.4x excess at hesitation positions is fully explained by their 2.25x higher entropy.
2. **At equal entropy, hesitation positions take ~30 % less damage.** About half of that is a sentence-start
   effect shared by every capitalized sentence opener; the rest is specific to the markers (E7b). One untested
   guess: a sentence-initial branch point splits its mass over a few well-separated discourse tokens, which a small
   logit perturbation reshuffles less than diffuse uncertainty does.
3. **The pattern does not depend on bit count.** Raw ratio 1.20-1.39 and matched ratio 0.59-0.69 across a **67x**
   range in mean KLD (Q2_K_XL 0.0738 -> Q6_K 0.0011). Fewer bits scale the damage up without moving it toward
   hesitation. IQ3_XXS is the lowest arm in every ratio column; nothing here explains why.
4. **For the "protect uncertain positions" question:** the mechanism to key on is the model's own entropy at the
   position. The source's marker penalty (12-23 % shorter CoT) works on the symptom, and nothing here argues
   against it as a length control. What this removes is the rationale that markers are a quantization weak spot:
   they are the opposite.

## Not delivered from the prereg

- **Top-1 agreement at HES positions** (a registered descriptive): the per-position dumps hold KLD only, so it was
  not computed.
- The UD-IQ2_M arm (optional, disk-gated) was not run.

## Not established

- One model (Qwen3.8-27B), one packager (Unsloth UD) plus one Q6_K; imatrix k-/i-quants only (the source used AWQ).
- Teacher-forced on fixed text; the source compared distributions under shared generation prefixes, which is
  close, but its text came from generation on MATH-500.
- Traces from the stock model at mixed quants; plain-text formatting instead of the chat template.
- Whether any of this changes overthinking is a separate, generative test.
- Scored positions are the second half of each 2,048-token chunk (the llama-perplexity convention).

## Files

- `PREREG_HESITATION_KLD.md`, `PLAN.md`, `corpus_reasoning.txt`, `run_hes.sh`, `analyze_hes.py` (registered),
  `explore_hes.py` and `explore2_hes.py` (exploratory).
- `raw/RESULT_hes.json` (registered output), `raw/EXPLORE_hes.json`, `raw/EXPLORE2_hes.json`,
  `raw/EXPLORE_hes.{H,P1}.npy` (per-position entropy and top-1 prob), `raw/hes_tokens.npz` (token ids and class
  masks), `raw/dumps/*.kld.bin` (per-position KLD, 5 arms), `raw/logs/` (llama-perplexity logs, home paths
  redacted).
- The 62 GB Q8_0 uint16 base is not committed. Everything above reproduces from `raw/`; the base regenerates from
  `run_hes.sh REF` in about 30 min.
