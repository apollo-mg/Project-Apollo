# qwen4exp runs correctly on Pascal — and is the only arch in the suite that fails the Meta split

**2026-08-27.** `TheTom/llama-cpp-turboquant` **PR #324** (`qwen4exp` / Qwen3.8-Flash-Next,
imported from upstream `ggml-org/llama.cpp#27742`) at head **`d74823a0c`**.
Node `.194`: 4x Tesla P100-PCIE-16GB (**sm_60**), CUDA 12.4, driver 580.173.02, gcc 15.2.0,
1063 MHz / 150 W. Built `-DCMAKE_CUDA_ARCHITECTURES=60
-DCMAKE_CUDA_FLAGS=-allow-unsupported-compiler`; `cuobjdump` confirms real `sm_60` cubins.

Existing PR validation is an **NVIDIA 5090** (Giveen) and an **Apple M5 Max** (TheTom).
This is the first sm_60 datapoint.

## Result — `test-llama-archs`, single GPU

| arch | device | config | NMSE vs CPU | roundtrip |
|---|---|---|---|---|
| `qwen4exp` | Tesla P100-PCIE-16GB | MoE | **OK (3.04e-14)** | **OK** |
| `qwen4exp` | Xeon E5-2650 v3 (CPU) | MoE | OK (0.00e+00) | OK |
| `qwen4exp` | **Meta** | MoE | **GGML_ASSERT failed** | — |

**The architecture is numerically correct on Pascal.** 3.04e-14 NMSE against CPU is
indistinguishable from every other passing arch in the run (2.6e-14 – 2.8e-14), and the
model save/reload roundtrip passes. The PR touches **zero** `ggml-cuda` files, so sm_60
support is inherited from existing op coverage rather than written — and it holds.

## The failure is arch-specific, not environmental

In the **same run**, **24 Meta rows passed**, including every other MoE architecture:

`qwen2moe` 2.69e-14 · `qwen3moe` 2.63e-14 · `qwen3next` 2.74e-14 ·
`qwen3vlmoe` 2.67e-14 · `qwen35moe` 2.73e-14 — all **OK** on Meta.

`qwen4exp` is the **only** architecture of ~30 tested that aborts there.

```
ggml-backend-meta.cpp:730: GGML_ASSERT(split_states_equal(src_ss[0], src_ss[2])) failed

  in handle_set_rows:
      GGML_ASSERT(src_ss[0].axis != GGML_BACKEND_SPLIT_AXIS_1);
      GGML_ASSERT(src_ss[1].axis == GGML_BACKEND_SPLIT_AXIS_MIRRORED);
      GGML_ASSERT(split_states_equal(src_ss[0], src_ss[2]));   <-- fails

  llama_context::decode -> process_ubatch -> ggml_backend_sched_alloc_graph
    -> ggml_gallocr_alloc_graph -> ggml_backend_meta_buffer_init_tensor
    -> ggml_backend_meta_get_split_state -> ggml_abort
```

A `SET_ROWS` op in the qwen4exp graph reaches the Meta splitter with sources 0 and 2 carrying
mismatched split states, during graph allocation. Plausible origin is the new
`llama-memory-hybrid-idx` / PLE indexer path (~900 new lines in this PR), but that is a
hypothesis — not traced.

## Open question this does NOT answer

TheTom reports `test-llama-archs` passing on **Apple M5 Max including qwen4exp**. On that host
the Meta device composes Metal + CPU; here it composes CUDA + CPU. So this may be
CUDA-path-specific rather than Pascal-specific, and **an sm_80+ CUDA box would separate the
two.** Nothing here distinguishes "Pascal" from "CUDA" as the relevant variable.

## Environment notes that cost two runs

1. **`GGML_CUDA_ALLREDUCE=internal` must be set on `.194`.** Without it the suite dies far
   earlier, on `llama`/Meta, in `ggml_backend_cuda_comm_allreduce_nccl` (`ggml-cuda.cu:1105`)
   with an unhandled NCCL error. Standing constraint for this node; unrelated to the PR.
2. With all 4 GPUs visible, `qwen3next`/Meta/MoE aborts at `ggml-backend-meta.cpp:1050`
   (`split_state.ne[j]*split_state.nr[0] * ...`) — a *different* assertion, and it does **not**
   reproduce with `CUDA_VISIBLE_DEVICES=0`, where `qwen3next` passes Meta cleanly. So there is a
   second, separate multi-GPU splitting issue on this box that is not qwen4exp's.

Archs run alphabetically, so `qwen3next` sorts immediately before `qwen4exp` — the first two
runs died one row short of the target.

## Second defect: `gguf-py` is broken on this branch

`import gguf` fails outright at `gguf-py/gguf/constants.py`:

```
AttributeError: type object 'MODEL_ARCH' has no attribute 'QWEN4EXP'
```

The `MODEL_ARCH.QWEN4EXP` tensor list was added (line 2459) but the enum member, the
`MODEL_ARCH_NAMES` string mapping, and **17 of the 48 `MODEL_TENSOR` members it references**
were never declared. All 17 are missing from `TENSOR_NAMES` as well:

| family | missing members |
|---|---|
| hyper-connections (11) | `HC_ATTN_{DOWN,INJECT,NORM,UP}`, `HC_FFN_{DOWN,INJECT,NORM,UP}`, `HC_HEAD_{DOWN,NORM,UP}` |
| per-layer embeddings (6) | `PLE_CONV1D`, `PLE_KEY`, `PLE_VALUE`, `PLE_NORM_{CONV,KEY,QUERY}` |

~19 declarations total. Reproduced in a fresh interpreter with `__pycache__` cleared; adding
`MODEL_ARCH.QWEN4EXP` alone just advances the failure to `MODEL_TENSOR.HC_HEAD_NORM`.

**Impact:** anything importing `gguf-py` fails, including `convert_hf_to_gguf.py` — the
converter for the architecture this PR adds. The C++ side is unaffected (the model loads and
`test-llama-archs` passes), so this is confined to the Python package.

**Caveat on novelty:** as of this writing the PR's `python type-check` and `Lint` CI jobs are
still **queued** on `d74823a0c`. If they import the module they will catch this independently.
Reported as early, not as unique.

## Loading the real weights — placement, not capability

`Qwen3.8-Flash-Next-UD-IQ4_XS` (87.2 GiB, 3 shards) on 4x P100, `-ngl 99 -fit off -c 4096`:

```
ggml_backend_cuda_buffer_type_alloc_buffer: allocating 16847.21 MiB on device 0:
  cudaMalloc failed: out of memory
```

**It reached memory allocation without tripping the Meta assert** — the graph path is fine
under `llama-server`; the naive split simply tried to place 16.8 GiB on a 16 GiB card. This is
the P2 scenario stated in the pre-registration: a distribution problem to be solved with
explicit `-ot` placement, not evidence the architecture cannot run here.

## Pre-registration scoring

`PREREG_FLASHNEXT_OFFLOAD.md` **P4** — *"runs at all on sm_60 without new kernels"*, registered
at **0.55**. **CONFIRMED for single-GPU execution**: builds clean, correct numerics, roundtrip
passes. Not confirmed for the Meta/multi-backend path. P1/P2/P3/P5 remain open — they need the
87.2 GiB IQ4_XS weights, not synthetic test models.
