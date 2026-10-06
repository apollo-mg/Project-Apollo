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

- Agreement between the two ports.
- Quality against Aleph Alpha's reference or their published numbers.
- Long contexts (the sliding-window path beyond 513 was only exercised by the ~300-token prompts' KV, i.e. barely).
- Thinking mode.
- MTP or speculation (none shipped for llama.cpp).
