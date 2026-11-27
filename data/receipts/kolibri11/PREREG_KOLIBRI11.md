# PREREG: Aleph Alpha's Kolibri 1.1 against Kolibri 1 on M1 -- does the successor know more, and decline more? (2026-11-27, before any M1 row)

**Why (Mark, 11-26/27):** Kolibri 1.1 (released 2026-11-23; 75B total, 3.44B active MoE, German/English, sparse attention,
NVFP4 quantization-aware training, knowledge cutoff June 2026) is the successor to Kolibri 1, which we ran on .194 in
October but never scored. Aleph Alpha publishes per-quant quality including hallucination metrics (Q4_K_M: AA-Omniscience
hallucination rate 39.1 % vs 38.9 % unquantized). **Prior art checked:** `ledger_precheck.py "Kolibri abstention honesty
Aleph Alpha"` -> no M1 or abstention result for either Kolibri (`kolibri-194/` is load, speed and port agreement only).
**What this adds:** both generations on M1, each on an implementation validated for it.

## Checks before this prereg (`raw/smoke.*`, `raw/k11_*.log`)

- **Build:** llama.cpp PR #32891 (Aleph Alpha, "Kolibri-1.1 support") head `5f4d22289`, built for sm_60 on .194.
  `test-backend-ops -b CUDA0`: ROUND_NVFP4 4/4, LIGHTNING_INDEXER 240/240, FLASH_ATTN_EXT 4,373/4,373 pass.
- **File:** `Kolibri-1.1-Q4_K_M.gguf` from Aleph-Alpha/Kolibri-1.1-GGUF, sha256 `ee511452...` matches the Hub.
- **Kolibri 1.1 on the P100s vs the CPU (same build, wikitext 16 x 512):** PPL 9.614 vs 9.602; KLD 0.039, same top
  92.2 %. **Path-noise control:** a second CPU run with another thread count and micro-batch vs the first: KLD 0.037,
  same top 93.0 %, PPL 9.687. The P100s are as close to the CPU as the CPU is to itself; the architecture is unusually
  sensitive to arithmetic order (likely the NVFP4 activation rounding).
- **Kolibri 1 on this build:** the October file (Hob-forge Q4_K_M) loads only with two overrides (pre-tokenizer
  `qwen2`, gating key 5 -> 2), and then differs from October's validated run (KLD 0.053, same top 91.3 %, PPL 28.20 vs
  28.43). Not used. **Kolibri 1 runs on October's port 1** (Hob-forge `60d1d51cc`), which matched an independent port to
  KLD 0.000024 (`kolibri-194/RESULT_KOLIBRI_194.md`).
- **Fresh questions, thinking off (enable_thinking false):** both answer four non-M1 questions in M1's format at ~39 tok/s;
  both get tungsten and the Peace of Westphalia right and decline an invented element; on an invented bridge Kolibri 1.1
  says it is not real and Kolibri 1 describes it ("a small tidal bridge in Lincolnshire").

## Arms (.194, 4x P100, `-ngl 99 -sm layer -fa on -fit off -c 8192 -np 1 -ctk f16 -ctv f16 --jinja --cache-ram 0`)

- `KOL11`: Kolibri 1.1 Q4_K_M on PR #32891 `5f4d22289`.
- `KOL1`: Kolibri 1 Q4_K_M (Hob-forge, October) on port 1 `60d1d51cc`.
M1 240 items, thinking off (Kolibri 1.1's template then adds "Reasoning is disabled. Proceed straight to answering..."),
greedy, `run_main.py` defaults (1,024 tokens, slot readout on) with `--usage`. Bare-answer rule.

## Predictions (KOL11 vs KOL1, paired over items)

- **H1 (the successor knows at least as much):** KOL11 hard right >= KOL1 hard right. Confidence 0.6.
- **H2 (the successor declines more):** KOL11 declines more invented questions than KOL1. Confidence 0.55.
- **Reported without prediction:** paired differences (bootstrap over items, 10,000, seed 20261127), wrong answers, easy
  right, unfinished, slot P(UNKNOWN), output length; both against Qwen3.8-27B Q8_0 thinking off (DR27_N73, .73) for
  context only.

## Limits stated now

Two builds (each validated for its model, not against each other); thinking off only (Kolibri defaults to high
reasoning); greedy where the vendor samples at 1.0; one quant; M1 is short English factual questions and Kolibri is
built for German and English; Kolibri 1.1's sensitivity to arithmetic order means a rerun on another build or thread
count could change some answers.
