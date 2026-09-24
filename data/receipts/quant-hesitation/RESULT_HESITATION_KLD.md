# Quantization does not single out hesitation tokens: the 1.4x raw excess is entropy, and at matched entropy "Wait"/"But"/"Maybe" positions take LESS damage

**2026-09-24**, `.194` (4x P100, 1063 MHz / 150 W), buun `08826ad6e` `llama-perplexity`, `-c 2048 -b 512 -ub 512
-fa on`, f16 KV, `-sm layer`, identical flags on every arm. Prereg: `PREREG_HESITATION_KLD.md` (written before any
KLD pass). Registered scorer: `analyze_hes.py` (unchanged, sha256 `a4520952c30faee4...`). Raw: `raw/`.

Source claim (Lotfi et al., shared by buun): under GPTQ/AWQ/FlatQuant, per-token KL at hesitation markers is ~100x
the KL at math tokens, and this drives overthinking at low bits. The prereg's question: is that about the words, or
about the uncertainty that sits where the words are?

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
registered threshold. The reading table has no row for H2 *reversing*; that part is an unregistered observation,
reported below as such.

## Exploratory (not registered): is the reversal a matching artifact?

`explore_hes.py`, run after scoring. It recomputes the same float64 entropy (the decile edges reproduce the
registered ones exactly) and saves per-position entropy and reference top-1 probability
(`raw/EXPLORE_hes.{H,P1}.npy`), so every number here can be recomputed without the 62 GB base.

**E1. The registered deciles match well except at the top.** Within deciles 2-9, HES and OTHER mean entropy differ
by at most 0.03 nats. In the top decile (2.03-6.9 nats, where 300 of the 945 HES positions sit), HES averages
2.37 nats against 2.64 for OTHER. The coarse top bin flatters OTHER a little.

**E2/E3/E5. Tightening the match moves the ratio from ~0.66 to ~0.71. Nothing crosses 1:**

| arm | deciles (registered) | 50 bins | 100 bins | **20 nearest neighbours in H** | top-1-prob deciles | top-1-prob 50 bins |
|---|---:|---:|---:|---:|---:|---:|
| UD-Q2_K_XL | 0.69 [0.63, 0.74] | 0.71 [0.66, 0.77] | 0.71 [0.66, 0.77] | **0.72 [0.66, 0.79]** | 0.71 [0.65, 0.76] | 0.71 [0.65, 0.76] |
| UD-IQ3_XXS | 0.59 [0.53, 0.65] | 0.62 [0.57, 0.68] | 0.63 [0.58, 0.68] | **0.64 [0.59, 0.69]** | 0.60 [0.55, 0.66] | 0.61 [0.55, 0.67] |
| UD-IQ4_XS | 0.67 [0.61, 0.74] | 0.70 [0.64, 0.77] | 0.71 [0.65, 0.77] | **0.73 [0.66, 0.80]** | 0.69 [0.62, 0.75] | 0.69 [0.63, 0.75] |
| UD-Q4_K_M | 0.65 [0.60, 0.72] | 0.69 [0.63, 0.75] | 0.69 [0.63, 0.75] | **0.71 [0.65, 0.78]** | 0.67 [0.61, 0.73] | 0.67 [0.61, 0.73] |
| Q6_K | 0.66 [0.60, 0.72] | 0.69 [0.64, 0.75] | 0.69 [0.64, 0.76] | **0.73 [0.67, 0.79]** | 0.67 [0.61, 0.73] | 0.67 [0.61, 0.74] |

- Bin CIs: chunk bootstrap, 2,000 resamples. Nearest-neighbour CIs: 500 resamples over a fixed match set.
- Nearest-neighbour matching is near-exact: the mean |dH| between a HES position and its matches is 0.0003 nats.
- **Best estimate: hesitation positions take ~27-36 % less KLD than positions of the same entropy.** That holds in
  every arm and under every matching scheme, including matching on top-1 probability instead of entropy.

**E4. The source's own comparison class does not reproduce ~100x here either.** Positions whose next token is a
digit (8,510 of them, mean entropy 0.22 nats):

| arm | KLD at HES | KLD at digit | HES / digit |
|---|---:|---:|---:|
| UD-Q2_K_XL | 0.1021 | 0.0467 | 2.19 |
| UD-IQ3_XXS | 0.0475 | 0.0425 | 1.12 |
| UD-IQ4_XS | 0.0171 | 0.0102 | 1.67 |
| UD-Q4_K_M | 0.0080 | 0.0049 | 1.65 |
| Q6_K | 0.0015 | 0.0011 | 1.36 |

"Math tokens" in the source may be a broader class (operators, LaTeX) and was measured during generation, so this is
a partial reconciliation. But on GGUF imatrix quants of Qwen3.8, even the raw gap against low-entropy numeric
tokens is 1.1-2.2x, two orders of magnitude below the reported ~100x.

## What it means

1. **At these positions, quantization damage follows the reference model's uncertainty, not the word.** The raw
   1.4x excess at hesitation positions is fully explained by their 2.25x higher entropy, with room to spare.
2. **Hesitation positions are, if anything, protected.** At equal entropy they take about 30 % less KLD. One
   untested guess: a sentence-initial branch point spreads its mass over a few well-separated discourse tokens
   ("But", "So", "Wait"), which a small logit perturbation reshuffles less than diffuse uncertainty. The top-1-prob
   match gives the same answer, so it is not just the top-1 margin.
3. **The shape of the damage does not depend on bits.** The raw ratio is 1.20-1.39 and the matched ratio
   0.59-0.69 across a **67x** range in mean KLD (Q2_K_XL 0.0738 -> Q6_K 0.0011). Fewer bits scale the damage up
   uniformly; they do not redistribute it toward hesitation.
4. **For the fix Mark asked about ("protect uncertain positions"):** the target is entropy, not a word list. A
   marker-targeted logit penalty (plan step 2) is not supported by this data. Anything that helps should key on
   the model's own uncertainty at the position.

## Not delivered from the prereg

- **Top-1 agreement at HES positions** (a registered descriptive): the per-position dumps hold KLD only, so it was
  not computed.
- The UD-IQ2_M arm (optional, disk-gated) was not run.

## Not established

- One model family (Qwen3.8-27B), one packager (Unsloth UD) plus one Q6_K.
- Teacher-forced; the source measured during generation, where a changed token changes everything after it.
- Traces from the stock model at mixed quants; plain-text formatting instead of the chat template.
- Whether any of this affects overthinking is a separate, generative test. This result removes the motivation for
  a marker-specific version of that test; an entropy-keyed version would still be open.
- The positions scored are the second half of each 2,048-token chunk (the llama-perplexity convention).

## Files

- `PREREG_HESITATION_KLD.md`, `PLAN.md`, `corpus_reasoning.txt`, `run_hes.sh`, `analyze_hes.py` (registered),
  `explore_hes.py` (exploratory).
- `raw/RESULT_hes.json` (registered output), `raw/EXPLORE_hes.json`, `raw/EXPLORE_hes.{H,P1}.npy`,
  `raw/dumps/*.kld.bin` (per-position KLD, 5 arms), `raw/logs/` (llama-perplexity logs, home paths redacted).
- The 62 GB Q8_0 uint16 base is not committed; it regenerates from `run_hes.sh REF` in about 30 min.
