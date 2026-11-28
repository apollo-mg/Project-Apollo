# PREREG: does the sm_60 fp32 carve-out close the P100s' gap to the CPU? (2026-11-27, before any patched-build row)

**Why (Mark, 11-27):** `RESULT_STACK_DRIFT.md` (D4) found the P100s ten times farther from the CPU reference than the
desktop (mean KLD 0.0065 vs 0.00067; same top 94.6 % vs 98.8 %) and left the cause untested. ggml-org/llama.cpp #25593
(mainline does sm_60 math in fp16) was closed unfixed on 11-27; the three-line fix (`tools/patches/sm60-fp32-carveout.patch`,
buun #80, turboquant #212) is now the default for our sm_60 builds (`data/scorecard/build_engine.sh`). Mark: "do the drift
test again to see if that closes the gap... a tidy ending." **Prior art checked:** `ledger_precheck.py "sm_60 FAST_FP16
carve-out KLD against CPU drift"` -> the July carve-out results (`data/Apollo Docs/Pascal_FAST_FP16_Carveout_Results.md`:
median KLD to an f32 GPU reference 0.0023 -> 0.000001, Qwen3.6-27B, an older mainline) and D4 above. **What this adds:**
the fix on current mainline, measured against the CPU reference the drift study used.

## Setup (.73, one P100, the drift study's exact KLD command)

- Patched build: `build_engine.sh sm60 33aeb17f8` (worktree `~/llama.cpp-33aeb17f-fp32`, the BUILD_OK line must name the
  patch). Unpatched: the drift study's `~/llama.cpp-33aeb17f/build_sm60`.
- KLD: Qwen3.5-9B Q8_0 (sha256 `f904644b...`), wikitext-2 test, `-c 512 --chunks 10`, `-ngl 99 -sm layer -fit off
  -ctk f16 -ctv f16`, `CUDA_VISIBLE_DEVICES=0`, against `raw/kld_base.bin` (CPU, sha256 `5f0e666b...`, same file on .73).
- M1: Qwen3.5-9B Q8_0 on the patched build, `-c 16384 -ctk f16 -ctv f16 -np 1 --jinja --cache-ram 0`, `run_main.py
  --max-tokens 1024 --usage`, arm `DR_N73F_1`.

## Gate

- **G1 (replay):** the unpatched build, rerun today, reproduces the drift study's mean KLD 0.006451 and same top 94.588 %
  (the run is deterministic on this rig).

## Predictions

- **F1:** patched mean KLD against the CPU <= 0.002 (from 0.0065; the desktop is 0.00067). Confidence 0.75.
- **F2:** patched same top token >= 98 % (from 94.6 %). Confidence 0.65.
- **Reported without prediction:** 99.9 % KLD and PPL ratio; M1 answers of the patched P100 against the desktop
  (`DR_DESK_1`: unpatched P100s matched it on 153 of 240 answers and 230 of 240 grades) and against the unpatched P100
  (`DR_N73_1`).

## Limits stated now

One model (9B dense, Q8_0), one card, one context length; the CPU is a reference, not truth (it has its own rounding);
M1 agreement with the desktop also depends on the desktop's own numerics.
