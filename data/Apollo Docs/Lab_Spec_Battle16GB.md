# Lab Spec — The Battle for 16GB: Gemma-4-12B QAT vs Ternary Bonsai 27B

**Date:** 2026-07-17 (launched same evening as the RDNA4 first-run)
**Hardware:** RX 9070 XT 16GB (gfx1201), desktop, **stock clocks** (sclk 2669 MHz / mclk 1258 MHz observed; no p100-efficiency analog applied — record with all numbers per OPERATIONS.md §2b discipline).

## 1. The Question

Two state-of-the-art answers to "what is the best model you can deploy in 16 GB":

| | Gemma-4-12B QAT UD-Q4_K_XL | Ternary-Bonsai-27B Q2_g64 |
|---|---|---|
| Params | 12B | 27B (Qwen3.6-27B backbone) |
| True bpw | ~4.3 | 1.71 (2.125 deployed) |
| Disk | 6.72 GB | 7.59 GB |
| Bet | fewer params, gentler quant (QAT@4bit) | 2.25× params, radical quant (ternary) |
| Extras | vision, MTP drafter (~2× decode) | vision (not used), DSpark drafter (fork-only, unavailable) |

Matched-bytes within 13%. The parameter delta is staggering (Mark's words); the bpw delta
equally so. This is QAT-at-4-bit vs ternary-at-scale on identical silicon.

## 2. Suites (mirrors W3 for cross-campaign comparability)

- **GSM8K-250**: seed-42 250-subset (identical indices to W1/W3 — `samples_gsm8k.json`),
  5-shot, raw `/v1/completions` (thinking-free by construction), greedy.
- **IFEval full** (541): chat endpoint, `--apply_chat_template`, trained-default thinking
  for both (Gemma `enable_thinking: true`, Bonsai default-on), equal gen budget
  `max_gen_toks=4096`, greedy. Server-side reasoning parser splits `reasoning_content`;
  harness grades answer text only. Truncation rate is a reported metric.
- **Speed**: llama-bench tg128/pp512 (Bonsai already receipted: 46.53/1334.85; Gemma
  MTP A/B already receipted: ~60 base, 110–143 with MTP) + per-leg harness wall time.

## 3. Serving (both: llama.cpp family, -ngl 99, fp16 KV, fa on, greedy)

- **Bonsai**: `engines/llama_cpp_bonsai/build_hip` (master 10068 + PR #25707, gfx1201),
  port 8093, `-c 32768`. Backend correctness pre-receipted: test-backend-ops q2_0 157/157.
- **Gemma**: `engines/llama_cpp_turboquant/build_rocm` (9966), port 8094, `-c 16384`,
  **MTP ON** (`--spec-type draft-mtp`, n-max 3) — speculative decoding is lossless in
  distribution, and MTP is part of Gemma's legitimate 16GB deployment story. No mmproj
  (text-only evals). KV fp16 (Mark's turbo4 KV dropped for cross-build parity).
- **Declared variables that are NOT controlled:** different builds (unavoidable — Bonsai
  needs the PR kernels, Gemma's MTP needs turboquant), Bonsai 32k vs Gemma 16k ctx alloc
  (both ≫ any prompt here), MTP nondeterminism on freeform (lossless-in-distribution,
  not bit-identical — receipted 2026-07-17).

## 4. Predictions (logged before first result, scored after)

- **P-B1 (conf 0.55):** Bonsai wins GSM8K-250 — the ternary card's math-retention claim
  (93.4 thinking-mode) survives contact with raw-completions mode, and 27B of backbone
  beats 12B. Low confidence: their numbers are thinking-mode; this is completion-mode.
- **P-B2 (conf 0.70):** Gemma wins IFEval — constraint-tracking is where sub-2-bit
  representations historically fray, QAT@4.3bpw is the gentler treatment, and Gemma
  lineage is strong on IF.
- **P-B3 (conf 0.97):** Gemma wins every throughput metric by ≥2× (MTP-on vs no drafter).
  The real deliverable is quality-per-wall-clock framing, not the win itself.
- **P-B4 (conf 0.60):** Bonsai finishes all 791 prompts with zero pathological loops
  (>99% finish=stop). The 4-probe smoke was clean; 791 multi-constraint prompts is the
  actual 2-bit-drunk test.

## 4b. Amendment (2026-07-18, pre-scoring)

**FINDING during v1: Bonsai cannot raw-complete.** On GSM8K 5-shot plain-text prompts it
puts ~100% first-token mass on `<|im_end|>` (id 248046; reproduced on exact harness prompt;
`add_bos_token=false` in GGUF and `add_special:false` change nothing — not a BOS artifact).
The v1 raw-completions leg returned empty strings (0.4% strict ≈ noise). Consequences:
- **P-B1 unscoreable as designed** — its raw-completions premise is falsified. Replacement
  **P-B1′ (conf 0.55, logged before any chat-mode GSM8K result):** Bonsai wins GSM8K-250
  via chat endpoint (`--fewshot_as_multiturn`, thinking on, 4096 budget, both models).
- Gemma additionally runs the original raw-completions leg (it completes normally) for
  W1/W3 cross-campaign comparability; Bonsai's raw column is recorded as N/A-by-behavior.
- Deployment-relevant in its own right: completion-API workflows are unusable on Bonsai.
v1 wrapper kill also reaped the first ifeval attempt ~2.4h in (no results written);
driver v2 relaunched setsid-detached 02:10.

## 5. Receipts

Driver + logs: scratchpad `b16/`; results `b16/results/`; serving configs recorded per leg
(cmdline + version + clocks). CHANGELOG entry on completion. Publishable target: HF/blog
post "The Battle for 16GB" + receipts comment on PR #25707 (Mark authors all GGML-facing
prose; agent fact-checks only).
