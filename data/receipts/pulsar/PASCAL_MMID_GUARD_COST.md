# turbo-tan issue-#11 Pascal `mul_mat_id` guard costs **~50% of all MoE throughput** on sm_60 — and sm_60 does not reproduce the bug

Date 2026-08-03. Node `.73`, 2× Tesla P100-PCIE-16GB, **compute capability 6.0 (sm_60)**,
150 W / 1063 MHz, persistence on. Model `Qwen3.6-35B-A3B-UD-IQ4_NL-MTP.gguf` (`qwen35moe`,
17.26 GiB). Flags `-c 8192 -fa on -np 1 -ngl 99 -sm tensor`, n_predict 128, temp 0, K=3.

## The guard

`turbo-tan/llama.cpp-tq3` @ `af0d9d7bc` ("cuda: guard mul_mat_id fast path on pascal", charpdev,
2026-05-30, branch `fix/issue-11-pascal-mmid`):

```c
// Issue #11 reports an eval-time illegal access on Pascal/SM61 in the
// mm_ids helper path. Keep newer CUDA fast paths enabled, but route
// Pascal-class NVIDIA devices through the existing conservative fallback.
const bool allow_mmid_fast_path =
    !GGML_CUDA_CC_IS_NVIDIA(cc) || cc >= GGML_CUDA_CC_VOLTA;
```

The issue names **SM61**. The guard catches **everything below Volta**, including sm_60.

## Measured cost

Method: the guard was applied to **our own build** (`TheTom/llama-cpp-turboquant` @ `d0e2a8b64`)
in a separate worktree, so the guard is the *only* variable. Cross-fork comparison would confound
enum layout, TQ dispatch and upstream base. Patch verified present (2 references) before building.

| `--spec-draft-n-max` | unguarded | guarded | loss |
|---|---|---|---|
| none (no MTP) | 47.42 / 47.56 / 47.31 | **24.17 / 24.33 / 24.37** | **−48.7%** |
| 2 | 68.76 / 68.68 / 68.60 | **30.93 / 31.17 / 31.13** | **−54.6%** |
| **3** | **70.28 / 70.50 / 70.52** | **31.96 / 32.94 / 32.88** | **−53.3%** |
| 4 | 35.20 / 35.43 / 35.26 | **26.63 / 26.86 / 26.87** | −23.9% |

`cuda_errors=0` on every guarded arm and every unguarded arm.

**The cost is not confined to speculative decoding.** The no-MTP baseline loses **48.7%** — at
`ne2 = 1`. MoE decode routes every single token through `MUL_MAT_ID` for expert selection, so the
guard halves *ordinary* MoE inference on Pascal, not just MTP.

## sm_60 does not reproduce the illegal access

Across this session, on the **unguarded** build (TheTom `d0e2a8b64` contains no such guard —
verified by grep), sm_60 ran:

- MTP verify batches `ne2` ∈ {2, 3, 4, 5} — the n-max 1/2/3/4 sweep, 3 reps × 128 tokens each
- the same sweep again under `-sm layer`
- a 3-model crossover ladder and a split-mode A/B on two further models

**Zero illegal memory accesses; `cuda_errors=0` on every arm.** This is not proof the bug cannot
occur on sm_60 — it is evidence that the workload class the guard protects runs clean here.

## Predictions (logged before the run) and scoring

- **G1 (0.85) — CONFIRMED.** Guarded < unguarded at every n-max.
- **G2 (0.80) — WRONG.** Predicted the n-max 4 cliff would *disappear* under the guard. It is
  attenuated (−18% vs −50%) but survives, so some batch-dependent degradation exists in the
  fallback path too, not only in the fast path.
- **G3 (0.7) — direction right, reasoning wrong.** Baseline did lose slightly less than MTP
  (48.7% vs 53.3%), but the stated reason ("`ne2=1` barely uses the batched path") is refuted by
  the size of the baseline loss.

## Suggested action for issue #11

**Narrow the guard from `cc >= GGML_CUDA_CC_VOLTA` to exclude sm_60**, i.e. gate on sm_61
specifically, unless someone reproduces the illegal access on sm_60. As written it costs P100
users roughly half of all MoE throughput to work around a fault reported on GTX-10-series silicon.

⚠️ **Not established here:** whether the illegal access reproduces on sm_61 hardware (we have none
in this fleet at that cc), and whether the sm_60 clean run generalises beyond `qwen35moe`. Both are
required before proposing the narrowing as a fix rather than a question.

## Provenance

`.73:~/guard_cost.log`, `~/guard_r_*.json`, `~/guard_srv_*.log`; script `~/guard_cost.sh`;
guarded worktree `~/tom_guarded` @ `d0e2a8b64` + patch. Unguarded reference:
`MTP_PASCAL_NMAX_MMVQ.md`.
