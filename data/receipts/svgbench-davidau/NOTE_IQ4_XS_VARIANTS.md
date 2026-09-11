# Note — the three IQ4_XS files in DavidAU's Twin-Turbo repo

**Written 2026-09-11.** Mark asked whether the repo's three IQ4_XS files are mislabeled.

- **Repo:** `DavidAU/Qwen3.8-27B-TWIN-TURBO-Fable-Cold-Fusion-709-L-Uncensored-NM-DAU-NEO-MTP-GGUF`
  at commit `7ee443a7`.
- **Method:**
  - Read the first 24 MiB of each file (the GGUF header) with HTTP range requests and parsed it
    with `gguf-py`.
  - Computed each tensor's byte size from its dims and type.
  - Compared tensor data by SHA-256 of range-read samples, 64 KiB to 1 MiB each.
  - No file was downloaded whole.

## What the three files are

| file | bytes | blocks | nextn | `output.weight` | MTP head (blk.64) |
|---|---|---|---|---|---|
| `…-NEO-IQ4_XS` | 15,082,514,848 | 64 | none | Q6_K | absent |
| `…-NEO-MTP-IQ4_XS` | 15,309,047,136 | 65 | 1 | Q6_K | 7× IQ4_XS, 1× Q5_K |
| `…-NEO-MAX-MTP-IQ4_XS` | 17,033,688,416 | 65 | 1 | **BF16** | 8× Q8_0 |

- **All three share:** `general.file_type` MOSTLY_IQ4_XS, `token_embd` IQ4_XS, and the same
  imatrix dataset (`neo1-v2.txt`).
- **The size gaps are fully explained.** Header offsets plus tensor sizes reproduce every file size
  to the byte.
  - plain → MTP (+226.5 MB): exactly the MTP head.
  - MTP → MAX (+1,724.6 MB):
    - `output.weight` Q6_K → BF16: +1,499.9 MB (248,320 × 5,120).
    - The head re-quantized to Q8_0: +224.8 MB.
  - Nothing else changes type.

**The filenames are accurate.**

## Where the model card and the files disagree

- **The MTP head's precision.** README line 408: *"I have also set the MTP tensors to Q8_0
  precision for all quants."*
  - True only for the MAX-MTP file.
  - The plain MTP IQ4_XS has an IQ4_XS/Q5_K head.
  - The locally held `NEO-MTP-IQ3_M` (sha256 `d25b96e4…`, the file used in `RESULT_TOKENS.md`)
    has a Q4_K head, read with GGUFReader.
- **The output tensor.** README line 404 says the output tensor is 16-bit on MAX quants only.
  Confirmed: BF16 in MAX, Q6_K in the others.
- **"No other difference."** README line 424: *"Note there is NO other diffence between the quants
  type besides speed."* Close, but not byte-true.
  - **Different imatrix files.** The plain file was quantized with an imatrix computed on the
    `…-NEO.gguf` source, and the MTP files with one computed on `…-NEO-MTP.gguf`.
  - **Source weights are the same.** Every F32 tensor sampled matches.
  - **Early and middle layers match.** 1 MiB samples of `token_embd`, `blk.0`, `blk.31` and
    `blk.40` are byte-identical, as are 64 KiB `ffn_down` samples in all of layers 0–55.
  - **The late layers differ.**
    - `ffn_down` differs in layers 56, 57, 61 and 63.
    - Across blk.62 and blk.63, 11 of 15 quantized tensors differ.
    - Within a differing tensor only 0.2–1.8% of 256-weight blocks change, in 1 MiB samples.
    - Such sparse differences can hide in a 64 KiB sample: `blk.63.attn_k` matched at 64 KiB and
      differed at 1 MiB.
  - **MAX vs MTP trunk:** no difference in any sample.
  - **Practical reading:** the same model, with a slightly different rounding of the last ~8
    layers. Any quality effect should be far below what our benchmarks can resolve. That has not
    been measured.

## Loading on buun `3823c9eb6`

- **What is skipped.** The loader skips the four `blk.64.nextn.*` tensors.
  - `llama-model-loader.cpp:1609–1611` prints "unused tensor … ignoring" for TENSOR_SKIP or
    unclaimed tensors.
  - The IQ3_M run logged exactly those four.
- **What is loaded.** The head's attention and FFN block is created as a normal layer, because the
  layer loop runs to `n_layer_all` = 65. It is therefore allocated in VRAM.
- **Cost without an MTP draft configured:** the MTP IQ4_XS keeps **+190 MiB** of GPU weights that
  do nothing. buun's source has an MTP draft context (`LLAMA_CONTEXT_TYPE_MTP`); it has not been
  tested here.

## Fit on the RX 9070 XT — a prediction, not a measurement

**Card and baseline.** The card has 16,304 MiB. The desktop held 1,467 MiB on 2026-09-11 with no
server running.

**Method.** Delta from the measured IQ3_M run:
- **Run settings:** `-c 24576 -ctk q8_0 -ctv q8_0 -np 1 -fa on`.
- **Measured:** peak 14,482 MiB on a 1,439 MiB desktop baseline (`memtrace.csv`).
- **GPU-resident weights:** every tensor except `token_embd` (kept on CPU) and the skipped
  `nextn.*`.
- **Non-weight overhead:** 1,377 MiB. That is 816 MiB of q8_0 KV (16 full-attention layers, 34 MiB
  per 1k tokens) plus recurrent state and compute buffers.

**Cross-check.** The same arithmetic applied to the ladder's measured UD-IQ4_XS fit probe (15.29
GiB) implies a 1,260 MiB desktop that day. That is consistent to within ~200 MiB.

**Direct comparison, with no overhead model.** The plain file carries 709 MiB more GPU-resident
weight than UD-IQ4_XS (13,729 vs 13,020 MiB). The fit probe loaded UD-IQ4_XS with 647 MiB free, so
the plain file is ~60 MiB over even on that day's lighter desktop.
- **The margin band at `-c 24576` q8_0 is about −60 to −270 MiB,** negative throughout.
- **Shortening the context changes the instrument.** `PREREG_TOKENS.md` runs at `-c 24576 -n 20000`,
  and stock first drawings reached 10,503 tokens. A run at shorter context is not comparable to
  `RESULT_TOKENS.md`.

| file | GPU weights | predicted peak at `-c 24576` q8_0 | margin |
|---|---|---|---|
| NEO-IQ4_XS | 13,729 MiB | 16,573 MiB | **−269** |
| NEO-MTP-IQ4_XS | 13,919 MiB | 16,762 MiB | **−458** |
| NEO-MAX-MTP-IQ4_XS | 15,537 MiB | 18,380 MiB | **−2,076** |

- **None fits the ladder's `-c 24576` q8_0 settings with the desktop running.**
- **Plain file at `-c 8192`:** predicted 16,029 MiB (+275 margin).
- **From a TTY:** most of the 1,467 MiB desktop comes back.
- **MAX does not fit** at any useful context.
- **Why a predicted overshoot matters:** `UD-Q4_K_M` in the fit probe hit 15.9/15.92 GiB, spilled
  1.08 GB to GTT, and later OOM'd the desktop under load.
