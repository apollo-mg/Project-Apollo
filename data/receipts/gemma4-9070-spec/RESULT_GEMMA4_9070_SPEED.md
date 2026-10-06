# Result -- like for like with TheTom's verified row (same Gemma-4-12B Q4_K_M, same Q8 gemma4-assistant drafter, draft 2, canonical reasoning-v1 prompt, thinking off), upstream llama.cpp on an RX 9070 XT decodes at 110.7 tok/s against vbutter's 85.3; vbutter keeps the TTFT lead (213 vs ~318 ms)

**2026-10-05.** Pre-registration `PREREG_GEMMA4_9070_SPEED.md` (`df89601e`, before any timed row).
- **Runner:** `run_g4.sh`.
- **Analysis:** `analyze_g4.py`, output `RESULT_g4.json`.
- **Raw:** `runs/` (each arm's LMX JSON and stdout, server log, `run.log`).


## Head-to-head, like for like (Deviations 2 and 3)

The registered arms below matched Tom's prompt LENGTH with LMX's filler prompt, and llama.cpp's Gemma-4 template ran
them in thinking mode (`reasoning_content`).

**Tom's row, read from the public API:**
- prompt: the canonical **reasoning-v1** (sha256 `9000edaa…`);
- the same Q8 drafter file (`145db909…`), gamma 2;
- 158/194 accepted (0.814), mean accepted length 2.63;
- a direct answer, so thinking off;
- `verifiedRun: true`.

**The like-for-like arms** use `--prompt-file canonical_reasoning-v1.txt` and `--reasoning off`, with the evidence
captured by `g4_proxy.py` (lmx still times):

| arm | tok/s out (median) | samples | acceptance (timed) | mean len | TTFT ms | prompt |
|---|---:|---|---|---|---:|---:|
| R_B0, no drafter | 60.6 | 61, 60.5, 60.6 | - | - | 298 | 305 |
| **R_D8n2 start 1** | 110.6 | 110.6, 111.4, 109.7 | 0.85, 0.86, 0.85 | 2.68, 2.71, 2.68 | 320 | 306 |
| **R_D8n2 start 2** | **110.7** | 110.7, 110.7, 109.2 | 0.86, 0.84, 0.84 | 2.71, 2.68, 2.67 | 317 | 305 |
| **R_D8n2 start 3** | 112.1 | 112.1, 112.1, 113.3 | 0.87, 0.87, 0.89 | 2.73, 2.73, 2.77 | 320 | 304 |
| R_D8n3 (draft 3) | 119.1 | 119.1, 121.2, 117.6 | 0.82, 0.83, 0.80 | 3.45, 3.49, 3.40 | 317 | 303 |

- **At Tom's settings: 110.7 tok/s,** the median of three fresh-start medians, against 85.3. That is 1.30x, and 1.83x
  over no drafter.
- **Acceptance is slightly higher than his** (0.84-0.89 vs 0.814), and the per-pass yield is similar (2.67-2.77 vs
  2.63).
- **Draft 3 is faster still (119.1),** but it is not his setting.
- **The output matches his:** both begin "## 1. Budget and Battery Calculation / Step-by-Step Reasoning".
- **The same prompt text is 305 tokens on llama.cpp's template and 505 on vbutter's.** The prompt hash matches, so
  the extra tokens come from vbutter's template.
- **TTFT 317-320 ms vs 213:** vbutter keeps that lead. LMX's prefill estimate (956 vs 2,373 tok/s) also divides
  different prompt lengths.
- **Thinking-mode canonical arms (Deviation 2, C_*):**
  - C_B0 60.7;
  - C_D8n2 109.0 / 113.9 / 111.0;
  - C_D8n3 114.7;
  - the no-proxy check 111.1, inside the proxied range, so the proxy does not perturb timing.
  - Decode is essentially unchanged by thinking mode on this prompt. TTFT was higher (376-458 ms).
- **Verified dry run:** `runs/sub_R_D8n2_r2.json`, the middle start under the fixed submission rule, passes
  LocalMaxxing's dry run with `verified: true` and no issues. **Not submitted:** that is Mark's call.
- **`lmx` v0.1.48 does not capture the evidence fields** (prompt hash, output, engine timings, draft counts). The
  proxy plus `build_submission.py` supply them from the median timed request.

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

## Registered arms (LMX filler prompt, thinking mode)

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
| CR0: max 2 + `--cache-ram 0` (Deviation 1) | 96.1 | 103.3, 91.9, 96.1 | 0.73, 0.67, 0.69 | 2.45, 2.33, 2.38 | 381 |

- **The best configuration:** Q8_0 drafter, `--spec-draft-n-max 2`. Its three fresh-start medians are 99.8, 98.1 and
  97.0, so **98.1 tok/s** (median of medians). That is 15 % above Tom's 85.3 and 1.60x the no-drafter baseline.
- **Draft max 2 and 3 tie,** at 99.8 and 99.0. At max 3 our drafter averages 2.8 tokens per pass, the same "2.8 tok/pass"
  as Tom's row. **The acceptance figures are not comparable.**
  - In llama.cpp's numbers, mean length = 1 + acceptance x draft max (1.81 at max 1, 2.80 at max 3).
  - Under that definition, vbutter's "81 %" cannot produce 2.8 tokens per pass, so vbutter counts differently or
    adapts its draft length.
  - No mechanism for the decode gap is claimed.
- **The cache-bust nonce changes the answer on every request,** so acceptance moves (0.56-0.74 at the same settings)
  and single requests spread by up to 10 tok/s. The three-run median absorbs most of that.

## Registered verdicts

| # | claim | result |
|---|---|---|
| P1 | B0 at 55-62 tok/s | **holds** (61.3) |
| P2 | the drafter at least 1.25x | **holds** (1.63x at max 2) |
| P3 | best confirmed configuration at least 85.3 | **holds** (98.1; all three medians at 97.0 or more). On Tom's prompt and mode it is 110.7 (Deviations 2-3) |
| P4 | Q0 (all-Q4_0) faster than the best Q4_K_M | **holds** (110.7 vs 98.1) |

## Where vbutter is still ahead: time to first token

- **TTFT:** Tom's row reports 213 ms, from which LMX estimates prefill at 2,373 tok/s. Ours ran 311-572 ms.
- **Traced in the server logs (Deviation 1):**
  - Prefill itself takes 250-290 ms for ~500 tokens (1,750-2,000 tok/s; the Q0 file ~200 ms).
  - Each request also waits between `selected slot` and `processing task`, and the wait grows per request (0 -> 52
    -> 127 ms in a confirmation run). That is this build saving the previous conversation to its host prompt cache
    (`--cache-ram`, 8 GiB by default).
- **CR0, `--cache-ram 0`:** the wait is gone (~0.03 ms) and TTFT holds at 381-406 ms instead of climbing. Decode is
  unchanged within noise (96.1; samples 103.3, 91.9, 96.1). Prefill measured slower in that run (322-348 ms), cause
  not established.
- **What is left is prefill speed:** this llama.cpp build does ~1,500-2,000 tok/s on a 505-token prompt here,
  against vbutter's implied 2,373. The R9700's plain llama.cpp row (same chip) reports 2,350 and 216 ms; its build
  and flags are unknown. The TTFT lead stays with vbutter.
- `-ub 256` / `1024` did not change TTFT. KV q8_0 lowered it (352 ms) but cost decode.
- **Correction:** the prereg said clocks and power would be recorded per arm. Only clocks were.

## Not established

- **Any prompt but LocalMaxxing's filler and its canonical reasoning-v1.** Acceptance depends heavily on content (INDEX L503), so this is "on LocalMaxxing's
  prompt", not a general speed claim.
- **Output quality.**
- **Depth beyond ~505 tokens.**
- **vbutter on this card.** Tom's 85.3 is from his card.
- **Why prefill measured slower with `--cache-ram 0`,** and what the R9700 row's build does differently.
- **The DFlash arm (F)** has not run yet. Upstream supports `draft-dflash`, and z-lab's Gemma-4-12B DFlash drafter has
  a Qwen3 backbone, which upstream supports. It needs converting with `--target-model-dir`.
- **Nothing was submitted to LocalMaxxing.** That is Mark's decision.

- **Submission run SUB1 (filler prompt, thinking mode, official lmx):** 102.1. It was superseded as the submission candidate by the like-for-like R_D8n2 start 2.

## Submitted (Mark's OK, 10-05 ~20:00 EDT)

- **Row:** `runs/sub_R_D8n2_r2.json`, LocalMaxxing speed test `cmuvwxpmq006nmr01viqmmmkr`, created
  2026-10-06T00:00:52Z.
- **Read back from the public API:** status APPROVED, `verifiedRun: true`, no verification issues. tok/s 110.7, TTFT
  317 ms, prompt 305 / output 256, context 262144, reasoning-v1 sha matching, MTP draft 2 (187/161), command snippet
  and notes intact. The hardware is listed as "RX 9070 XT".
- The account is not yet a verified user; that takes 3 verified runs.
- Owner edits are possible until about 2026-10-07 00:00Z.
