# PREREG: can the three machines be trusted equally? Same commit, same files, three stacks (2026-11-24, before any row)

**Mark (11-23):** "checking for drift between the stacks at the most current builds. Would like to see if we can depend on
all 3 systems equally at this point too." **Prior art checked:** `ledger_precheck.py "cross-host drift same model backends
ROCm CUDA P100 9070 byte identical answers"` -> only within-host evidence: .194's two lanes are bit-identical
(`quant-abstention/RESULT_MAIN.md`); replays on one machine reproduce byte for byte. Across machines, a preview only:
Qwen3.5-9B on the desktop (PR build, ROCm 7.2.4) against .194 (67107ac34f, CUDA) kept 227 of 240 grades and 160 of 240
answers word for word, but build and backend changed together (`sensenova-loop/RESULT_SENSENOVA_LOOP.md`). The desktop
moved to ROCm 10.1 on 11-24 (`PREREG_ROCM10.md`). **What this adds:** one commit on all three.

## Stacks (llama.cpp mainline `33aeb17f8`, built by `data/scorecard/build_engine.sh`)

| stack | machine | backend |
|---|---|---|
| **DESK** | desktop, RX 9070 XT | HIP, system ROCm 10.1 (`engines/rocm10/up_33aeb17f`) |
| **N194** | .194, one P100 (GPU 0) | CUDA 12.4, sm60 |
| **N73** | .73, one P100 (GPU 0) | CUDA 12.4, sm60 |
| **CPU** | desktop CPU (reference) | the same source, `-DGGML_HIP=OFF` |

Server flags everywhere: `-ngl 99 -c 16384 -ctk f16 -ctv f16 -np 1 --jinja --cache-ram 0` (`-ngl 0` for CPU), fresh server
per run; .194 and .73 add `-fit off`. Each run records the machine's driver, toolkit and binary hash.

## Measures

1. **M1 (Qwen3.5-9B Q8_0, sha256 `f904644b...`):** 240 items, greedy, thinking off, `quant-abstention/run_main.py`, run
   **twice** on each GPU stack (arms `DR_<STACK>_1`, `_2`). Grading with the bare-answer rule.
2. **Logits:** `llama-perplexity --kl-divergence-base` on the CPU stack (wikitext-2 test, `-c 512`, first 10 chunks),
   then `--kl-divergence` on each GPU stack: mean KLD, the 99th percentile, same-top-token rate, perplexity.
3. **The daily model (Qwen3.8-27B Q8_0, sha256 `a680f44a...`), two cards:** M1 once on .194 (GPUs 0+1) and once on .73
   (arms `DR27_N194`, `DR27_N73`), flags as the anchor runs (`-sm layer -fit off`).

## Predictions

- **D1 (each machine agrees with itself):** run 1 and run 2 identical on every GPU stack, 240 of 240. Confidence 0.85.
- **D2 (the two P100 machines are the same instrument):** N194 and N73 identical, 240 of 240. Confidence 0.75.
- **D3 (the desktop drifts in wording, not in results):** DESK vs N194 not byte-identical (0.9), yet at least 225 of
  240 grades agree (0.7), and the paired difference on invented-declined and on hard-right has a 95 % interval that
  includes 0 (0.7).
- **D4 (logits):** every GPU stack against the CPU reference: mean KLD below 0.005 and same top token at least 98 %.
  Confidence 0.7.
- **D5 (the daily model):** DR27_N194 and DR27_N73 identical, 240 of 240. Confidence 0.7.

**Reading rule:** two stacks count as interchangeable for scored results if D3's agreement and interval conditions hold
between them; byte-identical stacks can also stand in for each other in replays.

## Limits stated now

One commit, one model per size, one quant, greedy only (sampling adds its own variation), one card per small-model run.
The desktop's ROCm is days old in this setup. A difference shows that the stacks drift, not which one is "right"; the
CPU reference is a reference, not ground truth.
