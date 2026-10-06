# Result -- Aleph Alpha's Kolibri-1 (78B-A3.46B MoE) runs on 4x P100 through the unofficial Hob-forge llama.cpp port: coherent bilingual answers, 39.7 tok/s decode fully VRAM-resident at Q4_K_M; but wikitext-2 PPL 28.4 misses the registered "not broken" bar (< 15), and whether that is the port or the model is open

**2026-10-06.** Pre-registration `PREREG_KOLIBRI_194.md` (`1b7cf797`), no deviations.
- **Chain:** `kolibri_chain.sh`, plus `strata-194/kit/run194.sh` for the speed arms.
- **Raw:** `raw/` (prep log with the sha check, server logs, `props.json`, `sane.json`, `ppl.txt`, LMX JSON, proxy
  captures, GPU clocks).

## Setup

- **Model:** `Hob-forge/Kolibri-1-GGUF` @ `47fb91b2`, `Kolibri-1-Q4_K_M.gguf`, 47,454,113,472 B. sha256
  `c2ac1301…6062e`, `sha256sum -c` OK on .194.
- **Engine:** upstream llama.cpp `836d571` + the repo's `kolibri1-llama.cpp.patch`.
  - 4 commits, HEAD `60d1d51cc`; read before building (model code, converter, vocab, one test).
  - Built for sm_60 with CUDA 12.4 and gcc-13 as host.
- **Host:** .194, 4x P100, SM clock 1,063 MHz busy (`clocks_*.csv`).
- **Placement:** `-ngl 99 -sm layer -fa on -fit off -c 8192 -np 1`, f16 KV, `--jinja --reasoning off`.
  - Log: "offloaded 51/51 layers to GPU"; 176 MiB CPU-mapped.
  - VRAM 10.9-12.3 GB per card.

## Results

| arm | result |
|---|---|
| **K_load** | loads. The template has an `enable_thinking` switch; with `--reasoning off` no reasoning tokens were produced. |
| **K_sane** | "4"; "Die Hauptstadt von Deutschland ist Berlin." (German, as asked); "Photosynthesis is the process by which plants, algae, and some bacteria convert light energy into chemical energy by using carbon dioxide and water to produce glucose and oxygen." All finished with stop. |
| **K_ppl** | wikitext-2 test, 16 x 512, `-b 512`: **PPL 28.43 ± 1.54** |
| **K_speed** (lmx v0.1.48, canonical prompts, temperature 0, 256 tokens, 1 warmup + 3 timed) | reasoning-v1 **39.7 tok/s** (39.7, 39.7, 39.7), TTFT 2.16 s, 323 prompt tokens. code-v1 **39.8** (39.8, 39.8, 39.8), TTFT 2.00 s, 261 tokens. No drafter. |

## Registered verdicts

| # | claim | result |
|---|---|---|
| K1 | loads, and K_sane passes | **holds** |
| K2 | wikitext-2 PPL below 15 | **does not hold:** 28.4 |
| K3 | decode at least 30 tok/s | **holds:** 39.7 |

## What it means

- **The port works end to end on Pascal and is fast.** At 3.46B active it decodes 2.6x faster than Flash-Next without
  a drafter on the same box (15.0, `strata-194/`), and 20 % faster than Flash-Next with MTP (33.4).
- **PPL 28 is high, but it is not a verdict on the port.**
  - This is a reasoning-tuned bilingual model with a 128k vocabulary, scored on raw English wikitext at 512 context.
  - Per-token perplexity is not comparable across tokenizers, and chat/RL-tuned models often score high on raw text.
  - Its answers are clean.
  - With no runnable reference here (the official weights are FP8; BF16 is 156 GB), the way to judge the port is the
    planned agreement check: logits/KLD against the second unofficial port (Eliasfpv28's patch) on the same GGUF.
    A subtle port error (the 513-token sliding window, the sigmoid + bias gating) would show there.

## Not established

- Hob-forge's conversion, beyond the structure: K5 shows it agrees with an independent conversion on every float tensor
  and in weight structure, and finds one real defect (reserved-token ids). KLD against the other file is in the
  inconclusive band, because the two quants differ.
- Quality against Aleph Alpha's reference or their published numbers.
- Contexts beyond 2,048 (K4b exercised the 513-token sliding window up to 2,048).
- Thinking mode.
- MTP or speculation (none shipped for llama.cpp).

## K4: the two unofficial ports agree (addendum K4/K4b, Deviation K4-1)

- **Port 2:** Eliasfpv28's `kolibri1-runtime.patch` on upstream `edd6e2b`, which cites Aleph Alpha's inference
  reference. Built for sm_60 like port 1.
- **The test:** both ports run on the same Hob-forge Q4_K_M file. Port 1's logits are the base; port 2 is scored
  with `--kl-divergence`.
- **The tokenizer override:** port 2 needs `--override-kv tokenizer.ggml.pre=str:qwen2`. Port 1's `kolibri1`
  pre-tokenizer is the QWEN2 type in its own source, so tokenization is identical.

| context | port 1 PPL | port 2 PPL | mean KLD | max KLD | 99.9 % KLD | same top-1 |
|---|---:|---:|---:|---:|---:|---:|
| 512 (16 chunks) | 28.4302 | 28.4297 | -0.00001 (zero within rounding) | 0.000024 | 0.000010 | **100.000 %** |
| 2,048 (8 chunks, past the 513-token window) | 15.8325 | 15.8331 | -0.000008 | 0.000024 | 0.000013 | **100.000 %** |

**K4 holds.** Two independently written graph implementations produce the same next-token distributions to
rounding error, both inside and beyond the sliding window. Their routers are written differently: one as a new
generic gating op, one as model-local code that follows Aleph Alpha's reference.

**What this does and does not settle:**
- **K2's PPL is not a graph bug.** The implementations agree, and PPL falls from 28.4 at 512 to 15.8 at 2,048. The
  512 figure was mostly the short context.
- **It does NOT validate Hob-forge's conversion.** Both ports read the same converted file, so a converter error
  (tensor mapping, expert bias, norms) would be shared.
- **The converter test:** port 2's own GGUF (Q3_K_S, from Eliasfpv28's separate streaming converter) on the same
  wikitext.
  - Its PPL should come out a little above Q4_K_M's, since it is a lower quant.
  - A PPL far below would point at Hob-forge's conversion.
  - It needs a 31.5 GB download. Run as K5 below.
- **Raw:** `raw_k4/`. The base logit files (1-2 GB) were left on .194.

## K5: Hob-forge's conversion against an independent one (addendum K5)

**What K5 adds to K4:** K4 ran one file through two ports; K5 compares two files made by two converters.
- **File A:** Hob-forge's Q4_K_M, converted from Aleph Alpha's FP8 checkpoint.
- **File B:** Eliasfpv28's Q3_K_S @ `04f6e403`, converted with its own `stream-convert.py` from the official BF16, no
  imatrix. sha256 `26ce4a2f…d34aa` OK on .194.
- **Raw:** `raw_k5/` (`k5_compare.txt`, `q3_c512.txt`, `q3_c2048.txt`, logs) and `raw_k5/official_tokenizer_check.txt`.
- **Script:** `k5/k5_compare.py`, self-tested on A against itself (all gates pass with r = 1).

| gate | result |
|---|---|
| **K5a**, metadata | **does not hold as registered: 9 of 33 keys differ.** Itemised below. One is a real defect in A. |
| **K5b**, tensor list | **holds:** 903 tensors in each, identical names and shapes. Types: A Q4_K 426 / Q6_K 76 / F32 401; B Q3_K 501 / Q6_K 1 / F32 401. |
| **K5c**, float tensors | **holds, exactly: all 401 float tensors are bit-identical** (`attn_norm`, `attn_q_norm`, `attn_k_norm`, `ffn_norm`, `post_attention_norm`, `post_ffw_norm`, `output_norm`, the routers `ffn_gate_inp`, the expert biases `exp_probs_b`). This holds even though the two files start from different checkpoints (FP8 and BF16). |
| **K5d**, quantized weights | **holds:** Pearson r 0.981 (`attn_q`), 0.980 / 0.982 (expert 0 gate, layers 0/1), 0.990 / 0.991 (expert 0 down). Relative RMS difference 0.13-0.20, as expected for Q3_K against Q4_K/Q6_K. |
| **K5e**, end to end | **inconclusive by the registered bands** (see below) |

**K5a itemised:**
- **`tokenizer.ggml.tokens` and `token_type`: Hob-forge's file mis-numbers 75 reserved tokens.**
  - Aleph Alpha's `tokenizer.json` has two unused ids, 127923-127924, and `<|reserved-token-2..76|>` at
    127925-127999. That file is the same in the BF16 and FP8 repos (sha256 `5d4798f2…`).
  - Eliasfpv28's file matches it exactly.
  - Hob-forge's file fills the two gaps at the END instead: `<|reserved-token-2..76|>` sit at 127923-127997, and
    `[PAD127998]`/`[PAD127999]` follow. Every reserved token is 2 ids low.
  - Everything below id 127923 is identical (the ordinary vocab, the specials `<|im_end|>` 127906 and pad 127901,
    all 127,644 merges). So normal text and the chat template tokenize the same.
  - The defect only matters when a reserved token is generated or appears in input, where it maps to the wrong
    string or embedding.
- **`kolibri1.expert_gating_func`: A = 5, B = 2.**
  - Each port encodes the same rule its own way. Port 1 adds `SIGMOID_LOGIT_ADD` = 5 ("select top-k on logits +
    exp_probs_b, weight by unbiased sigmoid(logits)"), and its loader **throws** on any other value. Port 2's loader
    overwrites the key with `SIGMOID` (2), and its model code implements the same biased-selection, unbiased-weight
    rule.
  - **So port 2 reads both files, and port 1 refuses B outright (by source; not run).** Mixing a file and a port fails
    loudly instead of routing wrongly.
- **Six keys present in B and absent in A:** `feed_forward_length`, `rope.dimension_count`, `rope.scaling.type`,
  `vocab_size`, `tokenizer.ggml.add_space_prefix`, `tokenizer.ggml.eot_token_id`. Port 2 ran A identically to port 1
  (K4), so whatever port 2 uses in their place does not change its output on A.
- **All other architecture keys are equal:** heads 48/4, head dim 128, 50 blocks, 384 experts with 6 used plus 1
  shared, expert FFN 512, rms eps 1e-6, rope base 10000, sliding window 513 with the same per-layer pattern, context
  262,144, no expert-weight norm.

**K5e** (port 2 on Q3_K_S, KLD against port 1's Q4_K_M base logits from K4):

| context | Q3_K_S PPL | Q4_K_M PPL | ratio | mean KLD | median KLD | same top-1 |
|---|---:|---:|---:|---:|---:|---:|
| 512 (16 chunks) | 32.19 | 28.43 | 1.132 | 0.307 | 0.142 | 75.2 % |
| 2,048 (8 chunks) | 18.41 | 15.83 | 1.163 | 0.358 | 0.103 | 77.7 % |

The registered bands were "consistent" (mean KLD < 0.3 and top-1 >= 80 %) and "materially different" (KLD > 1.0 or
top-1 < 60 %). These figures are between them. With the structure identical (K5b-K5d), this gap is the size of the
quant difference: pure Q3_K without an imatrix against Q4_K_M, with 13-20 % weight RMS difference. But without a
Q3_K_S-vs-Q4_K_M baseline for this model that stays an inference, not a measurement.

**Prediction scorecard:**
- K5a-K5c (0.65): **missed**, on K5a.
- K5d (0.8): held.
- K5e (0.7): **missed** (inconclusive).

**What this settles:**
- **Hob-forge's file is structurally sound.** Its norms, routers and expert biases are bit-identical to an independent
  conversion from the other official checkpoint, and its weights correlate with that conversion as Q3-against-Q4
  quantization predicts. A tensor-mapping, transpose or norm error would have shown here.
- **One real converter defect:** the reserved-token ids, 2 low. It is harmless for ordinary chat and text, but it
  breaks any use of `<|reserved-token-N|>`.
- **Eliasfpv28's file matches the official token ids.** Its pure Q3_K quant costs 13-16 % PPL against Q4_K_M on
  wikitext.

**Not established:**
- Whether a subtler quantized-weight difference hides inside the KLD gap (no common-quant baseline).
- Port 1 on B (refused by source, not run).
- `provenance.json`'s source revision `7a8f290e` is not a valid revision of `Aleph-Alpha/Kolibri-1-BF16` on the Hub
  today, so the current head was used for the tokenizer check.
- **Housekeeping:** the Q3_K_S file was deleted after K5 (registered). The base logits and Q4_K_M are kept on .194.
