# PREREG: qualifying the desktop's ROCm 10.1 (2026-11-24, before any ROCm 10.1 build)

**Why (Mark, 11-24):** the CachyOS update moved the desktop from ROCm 7.2.4 (legacy stream) to 10.1 (the new ROCm Core
SDK stream, LLVM 24). Every llama.cpp build made on 7.2.4 segfaults on load under 10.1; the 7.2.4 libraries unpacked
privately restore them byte for byte (`NOTE_ROCM10_UPDATE.md`). Mark: "see if we can build the current forks against the
new ROCm", check what the new version changes, and "check for bugs for Tom and buun's forks, since this might be their
first exposure to this driver version". **Prior art checked:** `ledger_precheck.py "ROCm update rebuild gfx1201 replay"`
-> the 11-24 note only; AMD's 10.1 notes name no gfx1201 change relevant to llama.cpp and say nothing on 7.x binary
compatibility.

## Builds (all `data/scorecard/build_engine.sh gfx1201`, system ROCm 10.1, its flags: Release, `GPU_TARGETS=gfx1201`,
FA on, sched copies 4; into `engines/rocm10/`)

| build | source | for |
|---|---|---|
| `buun_38ada0e1` | buun `38ada0e1b` (as FZ_BASE's binary) | same source, ROCm 7.2.4 vs 10.1 |
| `up_4bc61eed` | llama.cpp PR 32588 `4bc61eed7` (as Q35R's binary) | same source, ROCm 7.2.4 vs 10.1 |
| `up_33aeb17f` | mainline master `33aeb17f8` (11-24) | current mainline on 10.1 |
| `buun_1e50db7b` | buun master `1e50db7be` (11-24) | current buun on 10.1 |
| `tq_f7c3638e` | TheTom turboquant `feature/turboquant-kv-cache` `f7c3638e8` (11-24) | current turboquant on 10.1 |

The three head builds also build `test-backend-ops` (`LLAMA_BUILD_TESTS=ON`); the two same-source builds keep the
original configuration (tests off) and add only `llama-bench`.

## Measures and predictions

- **B1 (builds and runs):** each build completes, and its server loads Qwen3.5-9B Q8_0 and answers a greedy request.
  Prediction: all five. Confidence 0.7.
- **B2 (op correctness, the forks' first exposure):** `test-backend-ops -b ROCm0` (each GPU op against the CPU backend)
  on the three head builds; report passed / failed / not supported per build, and every failing op by name. Prediction:
  mainline has no failure in MUL_MAT, MUL_MAT_ID or FLASH_ATTN_EXT. Confidence 0.7. No prediction for the forks.
- **B3 (ROCm alone, same source):** M1 replays on the 10.1 rebuilds against the stored 7.2.4 arms: FZ_BASE_N10 (buun
  `38ada0e1b`) vs FZ_BASE, Q35R_N10 (`4bc61eed7`) vs Q35R. Predictions: answers are NOT all byte-identical (LLVM 24
  recompiles every kernel), confidence 0.6; at most 10 of 240 grades change in each, confidence 0.7.
- **B4 (speed, same source):** `llama-bench` pp512 and tg128, Qwen3.5-9B Q8_0, 5 repetitions, `4bc61eed7` on 7.2.4
  (`tools/rocm724.sh`, old binary) vs 10.1 (rebuild), same card, back to back. Reported without prediction.

## Limits stated now

One card (RX 9070 XT), one OS image; `test-backend-ops` checks single ops against the CPU backend, not whole models. A
build that fails is reported with its error, not fixed here; fixes or reports to the fork owners are Mark's call.

## Deviation 1 (2026-11-24 ~17:45 EST, before any build finished or any B-measure ran)

B4 as registered cannot run: the old `4bc61eed7` binary was built without `llama-bench`. B4 is now: prompt processing from
`llama-perplexity`'s own timing (Qwen3.5-9B Q8_0, wikitext-2 test, `-c 512`, 20 chunks), old binary through
`tools/rocm724.sh` against the 10.1 rebuild, three runs each, alternating; decode speed as the median `gen_tps` of the M1
replays (Q35R_P724, today on 7.2.4, against Q35R_N10). The same `llama-perplexity` runs also give each side's perplexity,
reported as a numeric-drift check (no prediction).
