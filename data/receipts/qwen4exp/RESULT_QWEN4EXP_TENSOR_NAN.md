# `qwen4exp` under `-sm tensor` produces NaN — and `test-llama-archs` cannot see it

**2026-09-03.** `.194`, 4x P100 sm_60 @ 150 W. Build `~/buun-llama-cpp/build_sm60_qwen4`
(`7a918624b`, 2026-09-01) — **predates** the deny-list entry, so its `test-llama-archs` still
*runs* qwen4exp under `LLAMA_SPLIT_MODE_TENSOR` instead of skipping it. That is the only reason
this is observable.

## 1. The defect

`test-llama-archs -a qwen4exp`, with `GGML_CUDA_ALLREDUCE=internal`:

| Model arch | Device | Config | NMSE vs. CPU | Roundtrip |
|---|---|---|---|---|
| qwen4exp | Tesla P100-PCIE-16GB | MoE | OK (3.12e-14) | OK |
| qwen4exp | Xeon E5-2650 v3 | MoE | OK (0.00e+00) | OK |
| **qwen4exp** | **Meta** (= `SPLIT_MODE_TENSOR`) | MoE | **OK (nan)** | SKIP |

For contrast, dense archs on the same Meta device in the same suite:
`falcon | Meta | OK (3.49e-11)`, `baichuan | Meta | OK (2.60e-14)`.

**qwen4exp's tensor-split logits are NaN.** Process exits **0**.

## 2. Why the test reports that as OK

`tests/test-llama-archs.cpp`:

```cpp
status_nmse = "OK";
if (nmse_val > 1e-4) {
    all_ok = false;
    status_nmse = "FAIL";
}
```

`nan > 1e-4` is **false** under IEEE 754, so the branch never fires: `all_ok` stays true, the row
prints OK, and the suite exits 0. Any arch whose tensor-split path yields NaN passes silently.

This is inconsistent with the internal unit tests **in the same file**, which guard correctly:

```cpp
GGML_ASSERT(std::isfinite(tier_nmse) && tier_nmse <= 1.0e-6);
GGML_ASSERT(std::isfinite(gather_k_nmse) && gather_k_nmse <= 1.0e-5);
```

One-line fix: `if (!std::isfinite(nmse_val) || nmse_val > 1e-4) {`.

**The same bug is upstream** — `ggml-org/llama.cpp` `tests/test-llama-archs.cpp:749`, identical
expression. Upstream cannot hit it *for qwen4exp* (already deny-listed, so skipped), but it is
live for any other arch that produces NaN under tensor split.

## 3. The runtime symptom of the same path

[RESULT_META_BACKEND_SEGFAULT.md](RESULT_META_BACKEND_SEGFAULT.md): deterministic segfault (3/3)
in `ggml_backend_meta_graph_compute` on a prefix-extension prompt, `-sm tensor` only, clean with
`-sm layer` and on a single GPU. Together: the tensor-split path for this arch computes NaN and
has a memory defect. The gate (`// TODO: fix test-llama-archs`, upstream PR #27941) is correct.

## 4. On Pascal the suite cannot run at all

Two blockers, both previously found and still unsent in `DRAFT_buun_report.md`:

- **NCCL hard-abort.** Without `GGML_CUDA_ALLREDUCE=internal` the run aborts (core dumped) at the
  `llama` arch: `ggml_backend_cuda_comm_allreduce_nccl` -> `ggml_abort`,
  `ncclAllReduce(...)` -> "CUDA error: unhandled cuda error". sm_60 fails the `cc >= 700` gate for
  internal AllReduce ([allreduce-internal-inert-on-pascal]), so the fallback must be pinned.
- **`grok` fails to load** — `error loading model hyperparameters` ->
  `encountered runtime error: failed to create llama model` — which kills the whole run early,
  before most archs including qwen4exp. `-a <arch>` is the workaround.

So a full `test-llama-archs` pass has probably never completed on Pascal. Anyone validating
tensor-split on sm_60 needs both workarounds.

## Reproduction

```bash
GGML_CUDA_ALLREDUCE=internal build_sm60_qwen4/bin/test-llama-archs -a qwen4exp
# needs a build from BEFORE 36b101543 (upstream #27941), which deny-lists qwen4exp
```

## Status

Diagnostics only. buun said today he intends to fix tensor splitting; **no patch written here** to
avoid duplicating that work. Items 1, 2 and 4 are things he cannot easily obtain himself (item 4
needs Pascal). Nothing sent — awaiting Mark's review and approval.
