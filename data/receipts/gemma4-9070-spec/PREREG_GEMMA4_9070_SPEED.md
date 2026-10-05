# Pre-registration: can upstream llama.cpp on the RX 9070 XT match TheTom's 85.3 tok/s on Gemma-4-12B Q4_K_M, measured the same way?

**Registered 2026-10-05, before any timed row.** Mark: "We can try to see if we can beat him on llama.cpp."

**The reference row** (LocalMaxxing, submitted by thetom 10-05):
- Engine: `custom vbutter 0.1.0 HIP, uncommitted`.
- Model and decoding: `unsloth/gemma-4-12b-it-GGUF` Q4_K_M, with the `gemma4-assistant` drafter at "2.8 tok/pass, 81%".
- Run shape: batch 1, input 505, output 256, context 262144, kv-cache-tokens 0.
- Result: **85.3 tok/s out, prefill 2,373 tok/s, TTFT 213 ms.**
- The plain llama.cpp rows on the same board show no drafter, e.g. R9700 (same Navi 48 chip) at 58.2.

**Prior art checked:** `ledger_precheck.py "gemma 4 12b 9070 speculative MTP decode assistant drafter"` -> receipts found:
- **INDEX L503:** content type dominates MTP acceptance (prose 0.27-0.31, code 0.65, JSON 0.87-0.92), so one prompt
  says little about others.
- **INDEX L501, L34:** the speculative path changes output, the drafter does not.
- **`mtp-sm60/RESULT_MTP_SHARE_SILENT_CASE.md` (09-03):** this exact pair (Gemma4-12B + `mtp-gemma-4-12B-it`)
  tripped buun's sidecar tensor-share assert (buun #118). That is one reason for upstream.
- **INDEX L246:** the QAT file was used for quality on HermesAgent-20, not for speed.
- **What this adds:** the first Gemma-4 drafter speed measurement on this card, taken with the leaderboard's own tool.

## Instrument

- **Measurement:** LocalMaxxing's own CLI, built from source (`LottoLottoLotto/localmaxxing-cli` `16a3493`):
  `lmx speed-test run llama.cpp --mode remote --base-url http://127.0.0.1:<port> --max-tokens 256 --prompt-tokens <N>`.
  - Its defaults: one warmup request, then three timed requests, median reported.
  - Temperature 0, streaming, and a random cache-bust nonce on every request.
  - Decode rate = (completion_tokens - 1) / (last token - first token).
  - **N is set once, before any arm,** so that the server reports about 505 prompt tokens, and then held fixed.
  - **Nothing is submitted.** Submitting is Mark's decision.
- **Engine:** fresh upstream `ggml-org/llama.cpp` master, built for HIP gfx1201 (`-DGGML_HIP=ON`, graphs on, MMQ MFMA
  on). The commit is recorded in the result.
- **Model:** Tom's exact file, `gemma-4-12b-it-Q4_K_M.gguf`, 7,121,861,440 B, sha256 `0a270ec9…` (matches HF LFS).
- **Drafters:**
  - same repo `MTP/mtp-gemma-4-12b-it-Q8_0.gguf`, sha256 `145db909…`;
  - the QAT repo's Q4_0 drafter, sha256 `fcb35dea…`, in arm D4 only.
- **Server, every arm:**
  - Base flags: `-ngl 99 -fit off -fa on -np 1 -c 262144` (if it does not fit, the largest power of two that does,
    recorded) and `-ctk f16 -ctv f16`.
  - **Restarted for every configuration.**
  - VRAM is read after load with rocm-smi; this card also drives Mark's display (~2.5 GB in use).
  - GPU clocks and power are recorded once per arm.
- **Gates per arm (an arm that fails one is reported as failed, not as a number):**
  - for drafter arms, the server log shows the drafter loaded, and the server reports drafted and accepted tokens
    above 0;
  - LMX reports 256 completion tokens and a prompt within +-5 of the tuned count.

## Arms (in order)

| arm | change from the previous arm |
|---|---|
| **B0** | no drafter (the baseline; always shown) |
| **D8** | + Q8_0 assistant drafter, default draft settings |
| **D4** | Q4_0 drafter in place of Q8_0 |
| **Dn sweep** | the better drafter, draft-max 1, 2, 3, 4 (and 6, 8 if 4 is still rising) |
| **K/UB** | the best Dn with KV `q8_0`; then `-ub` 256 / 1024 against the default |

- **Confirmation:** the best configuration is rerun twice more, each from a fresh server start. All three medians are
  reported.
- **Separate, labeled, not part of the head-to-head:**
  - **Q0:** Mark's QAT file (`gemma-4-12B-it-qat-UD-Q4_K_XL`, which is **all Q4_0** inside, 6.72 GB) with its Q4_0
    drafter, best settings.
  - **Optional F:** a DFlash drafter (z-lab `gemma4-12B-it-DFlash`, GGUF conversions exist), only if upstream supports
    DFlash. On a fork it is labeled as a fork.

## Predictions

| # | claim | confidence |
|---|---|---|
| P1 | B0 lands at 55-62 tok/s (the R9700's plain llama.cpp is 58.2) | 0.6 |
| P2 | the drafter raises decode by at least 1.25x over B0 | 0.6 |
| P3 | the best confirmed configuration reaches **at least 85.3 tok/s** (Tom's row) | 0.45 |
| P4 | Q0 (all-Q4_0) is faster than the best Q4_K_M configuration | 0.6 |

## Reporting rule (fixed now)

- Every arm's median is reported with its acceptance and tokens per pass, B0 included.
- The head-to-head uses only the Q4_K_M file and upstream llama.cpp. Q0 and any fork are reported beside it, never
  instead of it.
- **One fixed prompt (L503):** whatever the result, it is "on LocalMaxxing's prompt", not a general speed claim.

## Not tested

- Output quality.
- Any other prompt.
- Context depth beyond about 505 tokens.
- vbutter itself (uncommitted).

## Deviations

Any change after the first timed row gets a numbered Deviation here before the affected rows run.
- **Deviation 1 (after the registered arms; before the rows it adds; 10-05 ~19:10).**
  - **Why:** TTFT (311-572 ms vs Tom's 213) was traced in the existing server logs. Prefill is only 250-290 ms.
    The rest is a gap between `selected slot` and `processing task` that grows request by request (0 -> 52 ->
    127 ms in BEST_r2). That is where this build saves the previous slot state to its host prompt cache
    (`--cache-ram`, default 8192 MiB).
  - **Added arms, reported beside the registered ones; the head-to-head decode figure is unchanged:**
    - **CR0:** the best configuration plus `--cache-ram 0`.
    - **CR0X:** CR0 plus `-ctxcp 0` (no SWA context checkpoints), only if CR0 leaves a growing gap.
  - **Correction (not a deviation):** "clocks and power recorded once per arm" -- only clocks were recorded.
- **Deviation 2 (before its rows; 10-05 ~19:50). The registered head-to-head matched Tom's prompt LENGTH, not his
  prompt.**
  - **Tom's row, read from the public API** (`GET /api/speed-tests?hfId=unsloth/gemma-4-12b-it-GGUF`):
    - prompt: the canonical prompt **reasoning-v1** (sha256 `9000edaa…`), 505 tokens on vbutter;
    - gamma 2, with the **same Q8 drafter file as our D8** (sha256 `145db909…`);
    - draft 194, accepted 158 (0.814), mean accepted length 2.63, `verifiedRun: true`.
  - Our registered arms used LMX's synthesized filler prompt (`--prompt-tokens 434`), where acceptance at draft max 2
    is about 0.66-0.70.
  - **Added arms, on the canonical prompt** (`lmx ... --prompt-file canonical_reasoning-v1.txt`; otherwise the
    registered instrument, and every other flag as in the arms):
    - **C_B0:** no drafter.
    - **C_D8n2:** Q8_0 drafter, draft max 2 (Tom's gamma), x3 fresh starts. **This is the new head-to-head.**
    - **C_D8n3:** draft max 3, x1.
  - **Evidence capture:** a localhost pass-through proxy (`g4_proxy.py`) between `lmx` and `llama-server` records
    each request's body, the streamed text and llama.cpp's final `timings`/`usage`.
    - `lmx` still does all the timing.
    - **Proxy check:** one C_D8n2 start without the proxy. Its median must fall within the three proxied medians'
      range +-3 tok/s, or the proxy is reported as perturbing.
  - **Submission rule (fixed now):** the C_D8n2 start whose median is the median of the three is the one offered to
    Mark. Its evidence fields come from that start's median timed request. The filler-prompt rows stay reported.
- **Deviation 3 (before its rows; 10-05 ~20:00). Every arm so far ran in THINKING mode.**
  - **What happened:** llama.cpp's Gemma-4 template defaults to reasoning `auto`, which enables it. The output was
    streamed as `reasoning_content`, the model's thinking, not an answer. Found because the capture proxy saw empty
    `content`.
  - **Why it matters:** Tom's evidence `outputSample` is a direct answer ("## 1. Budget and Battery Calculation ..."),
    so his row is thinking-off. Drafter acceptance on thinking text and on answer text can differ, so no row so far
    is like-for-like.
  - **The decode rate itself is valid:** `lmx` timed the streamed tokens and took the count from `usage`.
  - **Added arms, the canonical prompt with `--reasoning off`, otherwise as in Deviation 2 (proxy on):**
    - **R_B0:** no drafter.
    - **R_D8n2:** x3 fresh starts. **This becomes the head-to-head.**
    - **R_D8n3:** x1.
  - **Gate per arm:** captured `content` is non-empty and `reasoning_content` is empty.
  - **Submission rule** as in Deviation 2, applied to R_D8n2.
  - The thinking-mode rows stay in the result, labeled as thinking mode.
