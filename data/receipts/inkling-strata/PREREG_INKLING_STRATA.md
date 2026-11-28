# PREREG: Inkling-2-Mini as released (Strata SQ-20) and compressed (SQ-10), with reasoning truly off (2026-11-27, before any M1 row)

**Why (Mark, 11-27):** Strata ships Inkling-2-Mini packs (strata-engine/Inkling-2-Mini-Strata). Thinking Machines released
the model only in NVFP4 (20.16 GB, `quant_method: modelopt, quant_algo: NVFP4`), so Strata's SQ-20 (19.37 GB) is a lossless
repack -- Strata reports next-word agreement 100.00 % and drift 0.00000 against the original; SQ-15 and SQ-10 compress
further (SQ-10: 92.35 % same word, drift 0.050 on held-out prompts). Our INK arm (`inkling-mini/RESULT_INKLING_MINI.md`)
scored AtomicChat's AD-Q6_K, a second conversion of the NVFP4 release, on llama.cpp. **Prior art checked:**
`ledger_precheck.py "Inkling Strata SQ pack thinking off NVFP4"` -> nothing on Strata's Inkling; the reasoning-vs-model
confound of INK (`RESULT_Q27_LOW.md`). **What this adds:** the released weights, a compressed pack, and Inkling with its
reasoning off.

## Smoke seen before this prereg (`raw/smoke.*`; fresh non-M1 questions)

- Strata 0.2.23 (Control and Inkling engine 0.1.70, CUDA 12 build, which supports Pascal) serves its default SQ-20 pack
  (SQv2) on .73's two P100s at ~42 tok/s.
- **reasoning_effort "none" turns reasoning fully off here:** 0 reasoning characters, 21-28 tokens per answer. At the
  default effort it reasons briefly (260-400 characters, 88-130 tokens). In our llama.cpp INK run, "none" still reasoned a
  few hundred tokens (median 150-432 output tokens): the two engines handle "none" differently.
- Four fresh questions in M1's format: W, 1648, and UNKNOWN for both invented items (with and without reasoning).
- The server has no `/tokenize` or `/apply-template`; `run_main.py --chat-only` (added for this, default off) skips them.

## Arms (.73, 2x P100; Strata `launch --context 32k --vision off --parallel 1 --tune skip --access local --port 8085
--gpu 0,1 --kv fp16 --draft off --drafting off`; tunnel from the desktop)

- `INKS20`: Inkling-2-Mini-SQ-20.strata (sha256 `0bbfd523...`, the pack the card calls identical to the original), loaded
  with `--model-path`.
- `INKS20V2`: Inkling-2-Mini-SQv2-20.strata (sha256 `429671f8...`), what `--model SQ-20` installs in 0.2.23; the card does
  not mention v2. Reported without prediction, including its agreement with INKS20.
- `INKS10`: Inkling-2-Mini-SQ-10.strata (sha256 `ac4d452a...`).
All three hashes match the Hub's.
M1 240 items, greedy, `run_main.py --max-tokens 4096 --timeout 900 --usage --skip-slot --no-think-check --chat-only
--neutral-penalties --template-kwargs '{"reasoning_effort": "none"}'`. Bare-answer rule. Drafting off so decoding is plain.

## Predictions

- **S1 (compression costs caution):** INKS10 declines fewer invented questions than INKS20. Confidence 0.55.
- **S2 (compression costs facts, or none):** INKS10 hard right <= INKS20 hard right. Confidence 0.65.
- **S3 (reasoning made INK careful):** INKS20, with reasoning off, declines fewer invented questions than INK (78, llama.cpp
  "none" with a few hundred reasoning tokens). Confidence 0.7.
- **Reported without prediction:** paired differences (bootstrap over items, 10,000, seed 20261127); INKS20 against
  Qwen3.8-27B Q8_0 thinking off (DR27_N73: 59 declined, 48 hard right), now a same-condition comparison; INKS20 against INK
  (different engine, file and reasoning, so not a file test); unfinished and output length.

## Limits stated now

Greedy where the vendor samples at 1.0; reasoning off only; two engines and three files are not a factorial design (the
file effect is measured only within Strata, SQ-20 vs SQ-10); M1 is short English factual questions; one run per arm.
