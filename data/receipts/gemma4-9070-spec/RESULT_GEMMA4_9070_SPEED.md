# Result -- upstream llama.cpp on an RX 9070 XT decodes Tom's Gemma-4-12B Q4_K_M at 98.1 tok/s with the gemma4-assistant drafter (LocalMaxxing's own CLI and prompt), against vbutter's 85.3; vbutter keeps a 2x lead on time to first token

**2026-10-05.** Pre-registration `PREREG_GEMMA4_9070_SPEED.md` (`df89601e`, before any timed row).
- **Runner:** `run_g4.sh`.
- **Analysis:** `analyze_g4.py`, output `RESULT_g4.json`.
- **Raw:** `runs/` (each arm's LMX JSON and stdout, server log, `run.log`).

## Setup

- **Engine:** `ggml-org/llama.cpp` master `50569eb87` (2026-10-05), HIP gfx1201, graphs on, MMQ MFMA on.
- **Card and host:** the control-plane RX 9070 XT, which also drives Mark's desktop (~2.5 GB of VRAM in use).
- **Model:** Tom's exact file, `unsloth/gemma-4-12b-it-GGUF` `gemma-4-12b-it-Q4_K_M.gguf`, sha256 `0a270ec9…`
  (matches HF LFS).
- **Drafter:** the same repo's `MTP/mtp-gemma-4-12b-it-Q8_0.gguf`, sha256 `145db909…`.
- **Server, every arm:** `-ngl 99 -fit off -fa on -np 1 -c 262144 -ctk f16 -ctv f16`, plus the arm's flags; fresh
  server per arm. The full 262,144 context fits: 15.3 GB used with the drafter, desktop included.
- **Measurement:** `lmx speed-test run llama.cpp --mode remote` (localmaxxing-cli `16a3493`, built from source),
  `--max-tokens 256 --prompt-tokens 434`.
  - Its defaults: one warmup, three timed requests, median reported.
  - Temperature 0, and a cache-bust nonce on every request.
  - Decode rate = (completion tokens - 1) / time from the first to the last streamed token.
  - **Prompt length:** N = 434 was set before any arm (three calibration requests, `runs/*tune*`) so that the server
    counts about 505 prompt tokens, like Tom's row. Every arm measured 501-505.
  - With N = 512, llama.cpp's Gemma template counts 578 tokens. So vbutter probably sees a slightly different token
    count for the same text.
- **Gates (all passed):** the drafter was loaded and accepted tokens on every request; 256 completion tokens; prompt
  within 5 of the tuned count. The q8_0 override in K8 was confirmed in a verbose start ("K (q8_0)").

## Results

| arm | tok/s out (median) | samples | acceptance (timed) | mean len | TTFT ms |
|---|---:|---|---|---|---:|
| B0 (no drafter) | 61.3 | 61.4, 61.3, 60.4 | - | - | 490 |
| D8 (Q8_0 drafter, default draft max 3) | 99.0 | 102.2, 98, 99 | 0.62, 0.58, 0.60 | 2.87, 2.74, 2.79 | 572 |
| D4 (QAT repo's Q4_0 drafter, max 3) | 96.5 | 96.5, 106.4, 96.1 | 0.56, 0.66, 0.57 | 2.68, 2.97, 2.68 | 500 |
| D8, max 1 | 87.3 | 88.3, 86.1, 87.3 | 0.81, 0.81, 0.81 | 1.81 | 500 |
| **D8, max 2** | **99.8** | 94.9, 102.5, 99.8 | 0.63, 0.74, 0.71 | 2.26, 2.47, 2.42 | 517 |
| D8, max 4 | 94.0 | 94, 85.1, 95.9 | 0.52, 0.45, 0.53 | 3.06, 2.77, 3.11 | 524 |
| max 2 + KV q8_0 | 92.9 | 90.4, 92.9, 94.5 | 0.65, 0.68, 0.71 | 2.30, 2.36, 2.41 | 352 |
| max 2, `-ub 256` | 98.6 | 97.8, 98.6, 98.9 | 0.66, 0.67, 0.68 | 2.32, 2.34, 2.36 | 490 |
| max 2, `-ub 1024` | 97.6 | 97.6, 98.3, 95.5 | 0.68, 0.72, 0.64 | 2.36, 2.44, 2.29 | 534 |
| max 2, confirmation 2 | 98.1 | 99.6, 98.1, 97.4 | 0.70, 0.68, 0.66 | 2.40, 2.36, 2.32 | 413 |
| max 2, confirmation 3 | 97.0 | 97, 96.6, 102.2 | 0.66, 0.65, 0.71 | 2.32, 2.30, 2.43 | 454 |
| *Q0: QAT `UD-Q4_K_XL` (all Q4_0, 6.72 GB) + its Q4_0 drafter, max 2* | *110.7* | 109.6, 114.9, 110.7 | 0.69, 0.74, 0.71 | 2.37, 2.48, 2.42 | 392 |
| *Q0 without a drafter (added context row, not registered)* | *64.8* | 64.9, 64.8, 64.8 | - | - | 311 |

- **The best configuration:** Q8_0 drafter, `--spec-draft-n-max 2`. Its three fresh-start medians are 99.8, 98.1 and
  97.0, so **98.1 tok/s** (median of medians). That is 15 % above Tom's 85.3 and 1.60x the no-drafter baseline.
- **Draft max 2 and 3 tie,** at 99.8 and 99.0. At max 3 the drafter averages 2.8 tokens per pass, exactly the "2.8
  tok/pass" on Tom's row. So the gap is per-pass speed (about 35 vs 30 passes/s), not acceptance.
- **The cache-bust nonce changes the answer on every request,** so acceptance moves (0.56-0.74 at the same settings)
  and single requests spread by up to 10 tok/s. The three-run median absorbs most of that.

## Registered verdicts

| # | claim | result |
|---|---|---|
| P1 | B0 at 55-62 tok/s | **holds** (61.3) |
| P2 | the drafter at least 1.25x | **holds** (1.63x at max 2) |
| P3 | best confirmed configuration at least 85.3 | **holds** (98.1; all three medians at 97.0 or more) |
| P4 | Q0 (all-Q4_0) faster than the best Q4_K_M | **holds** (110.7 vs 98.1) |

## Where vbutter is still ahead: time to first token

- **TTFT:** Tom's row reports 213 ms, from which LMX estimates prefill at 2,373 tok/s. Ours runs 311-572 ms (LMX
  estimates 1,210 tok/s for the best configuration).
- **It is not the drafter:** B0 shows the same 490 ms.
- **The R9700 row (plain llama.cpp, same chip) reports 2,350 and 216 ms,** so it is probably this machine rather than
  llama.cpp. GPU clock ramp from desktop idle is the first suspect (the sclk read 778-2656 MHz at server start). Not
  tested.

## Not established

- **Any prompt but LocalMaxxing's.** Acceptance depends heavily on content (INDEX L503), so this is "on LocalMaxxing's
  prompt", not a general speed claim.
- **Output quality.**
- **Depth beyond ~505 tokens.**
- **vbutter on this card.** Tom's 85.3 is from his card.
- **Whether the TTFT gap is power management.**
- **The DFlash arm (F)** has not run yet. Upstream supports `draft-dflash`, and z-lab's Gemma-4-12B DFlash drafter has
  a Qwen3 backbone, which upstream supports. It needs converting with `--target-model-dir`.
- **Nothing was submitted to LocalMaxxing.** That is Mark's decision.
