# Spin -- Nemotron 3.5 Bolt 74B-A9B (NVIDIA's 24GB GGUF) on .73's two P100s, with and without the LiliCorr drafter

**Date:** 2026-10-15, 19:11-19:15 EDT, the day of release. A quick look, not a campaign: no prereg, one prompt per content
type, two reps each. Raw output in `raw/`.

**Prior art checked:** `ledger_precheck.py "Nemotron Bolt dflash lilicorr speculative"` -> MTP receipts found
(`mtp-transfer/RESULT_MTP_HEAD_TRANSFER.md`: content type dominates acceptance, prose 0.27-0.31 / code 0.65-0.66 /
JSON 0.87-0.92; `RESULT_SPECULATION_IS_NOT_BIT_EXACT`). This adds a different drafter class (a DFlash block drafter
with the LiliCorr candidate-selection head) on a new architecture, and shows that at `n_max=7` it costs prose speed
rather than merely gaining less.

## Setup

| | |
|---|---|
| node | .73, 2x Tesla P100-PCIE-16GB, clocks locked 1328 MHz, 150 W cap (read at leg start) |
| build | upstream llama.cpp v0.7.0, commit `620d222` (`/mnt/HDD/llama.cpp-v0.7.0/build_sm60`), CUDA 12.4.131, gcc-13 host |
| target | `nvidia/NVIDIA-Nemotron-3.5-Bolt-74B-A9B-24GB-GGUF`: 22,018,326,528 B, sha256 `91d63363...`, GGUF arch `nemotron_h_moe`, NVIDIA's QAT "native 2-bit" (IQ2_XXS) |
| drafter | `nvidia/...-24GB-LiLiCorr-GGUF`: 998,242,560 B, sha256 `080e1ea4...`, arch `dflash`, 5 layers, `block_size` 8, `lilicorr.candidate_topk` 8 (non-zero, so the LiliCorr path is on), 2-layer head |
| server | `-ngl 99 -c 16384 -np 1 -fa on`, default layer split, f16 KV, no mmproj; drafter leg adds `-md ... -ngld 99 --spec-type draft-dflash --spec-draft-n-max 7`. Fresh server per leg |
| client | `/v1/chat/completions`, temperature 0, `cache_prompt: false`, `enable_thinking: false` (reasoning_len 0 on every row), max_tokens 256 |

## Results

| content | no drafter | LiliCorr, n_max 7 | acceptance | speed-up |
|---|---|---|---|---|
| prose (bicycle history) | 27.3-27.5 tok/s | 18.5-18.9 tok/s | 170 / 587 = **0.29** | **0.68x (slower)** |
| code (ISO-8601 function) | 27.5-27.6 tok/s | 42.5-43.3 tok/s | 137 / 161 = **0.85** | **1.56x** |
| JSON (8 employee records) | 27.5 tok/s | 45.4-45.8 tok/s | 220 / 240 = **0.92** | **1.66x** |

- **Plain decode is flat at ~27.5 tok/s** across content types (the 9B active set in IQ2_XXS on sm_60).
- **VRAM:** 10.2 + 12.2 GB without the drafter, 11.7 + 13.8 GB with it, at 16k context. Both fit with room to spare.
- **Load:** server listening 49 s after launch (NVMe).
- **Reps reproduce exactly** (identical token and acceptance counts), as expected at temp 0, np 1, no prompt cache.
- **`draft_n` confirms each arm:** absent on every no-drafter row, non-zero on every drafter row.
- **Text:** every answer is coherent. The first 160 characters match between arms for all three prompts; the code
  answer is the same length (540 chars) both ways, while prose (1,183 vs 1,122) and JSON (623 vs 626) diverge later,
  consistent with `RESULT_SPECULATION_IS_NOT_BIT_EXACT`.
- Prompt-processing figures (34-49 tok/s) are on 20-60-token prompts and say nothing about prefill throughput.

## Reading

Content type decides whether this drafter pays, as it did for MTP heads: acceptance 0.29 / 0.85 / 0.92 for prose /
code / JSON, close to the MTP pattern (code is higher here). The new point is the sign on prose: at `n_max=7` a block
drafter with 29 % acceptance makes decode **32 % slower** than no speculation, where the MTP heads were never
net-negative. For chat and prose on this box, run it without the drafter; for code, tool calls and structured output,
LiliCorr is worth ~1.6x.

## Not established

- One prompt per content type; no `n_max` sweep (a smaller block may break even on prose); no plain-DFlash control
  (this drafter file cannot run without its LiliCorr head as shipped); 256-token answers; short prompts only.
- Quality was not scored beyond reading the answers. The QAT 2-bit vs post-hoc IQ2 question (AtomicChat's files from
  BF16) is open.
- Built and measured on Pascal only. No vision (mmproj) or `--moe-cache-mib` test.
