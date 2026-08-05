# Phase 0 — study tooling built, `d0e2a8b64` validated, and a second TQ4_1S defect found

**Node `.73`, 2× Tesla P100-PCIE-16GB (sm_60), 150 W cap. 2026-08-03.**
Phase 0 of `Lab_Spec_TQ_Weight_Fidelity_Per_Bit.md`.

## Tooling built

`llama-quantize`, `llama-perplexity`, `llama-imatrix`, `test-backend-ops` — on **both** trees
(`tom_rebase` @ `d0e2a8b64`, `tom_sync` @ `6aa97d810`). Previously only `llama-server` existed.
CUDA arch 60, Release, `LLAMA_BUILD_TESTS=ON`.

## ✅ Validation gate PASSED — the study may proceed on `d0e2a8b64`

`test-backend-ops -o MUL_MAT -b CUDA0`:

| build | result | TQ cases | FAIL | NaN |
|---|---|---|---|---|
| **`d0e2a8b64` (GOOD)** | **1344/1344 passed, 3/3 backends** | 278 | **0** | **0** |
| `6aa97d810` (BROKEN) | 1358/1359, **2/3 backends, rc=1** | 294 | 3 | 1 |

This is a *numeric* CUDA-vs-CPU comparison per op and quant type — a far stronger gate than
inspecting generated text, which is what the spec originally called for. `TQ4_1S` and `TQ3_1S`
MUL_MAT agree with the CPU reference across all tested shapes on `d0e2a8b64`.

**Fidelity measurements in Phase 1 will therefore be taken on `d0e2a8b64`.** This gate exists
because tonight showed a build can emit fluent garbage with `cuda_err=0` and identical throughput
(`TQ4_1S_PASCAL_REGRESSION.md`); a KLD number from such a build would look entirely plausible and
mean nothing.

## The broken build fails its own test suite

`6aa97d810` exits `rc=1`, `2/3 backends passed`. **Running `test-backend-ops` before merging would
have flagged a TQ4_1S problem.** The merge even *added* TQ coverage (28 refs in
`tests/test-backend-ops.cpp` vs 18 on the rebase branch), so the suite grew and still shipped red.

## ⚠️ NEW: a second, independent TQ4_1S defect

The failing case:

```
[MUL_MAT] NaN at index 245 (CUDA0=nan CPU=-nan)
MUL_MAT(type_a=tq4_1s, type_b=f32, m=256, n=256, k=1536, bs=[1,1], nr=[1,1], k_v=1600, o=1): FAIL
```

**It is not the `__byte_perm` centroid-LUT bug.** Rebuilding `6aa97d810` with *only* `e130aef60`'s
`mmvq-tq.cu` hunk applied — the patch proven to restore coherent generation — leaves this failure
byte-identical: same shape, same `index 245`, same `CUDA0=nan CPU=-nan`, `rc=1`, `2/3 backends`.

| build | generation | `test-backend-ops` |
|---|---|---|
| `6aa97d810` | garbage | NaN FAIL |
| `6aa97d810` + LUT fix | **coherent** | **NaN FAIL (unchanged)** |
| `d0e2a8b64` | coherent | pass |

Two distinguishing features:

1. **The NaN appears on CPU as well as CUDA** (`CUDA0=nan CPU=-nan`). The CPU backend never touches
   the `__byte_perm` kernel, so this lives in shared code — the reference quantize/dequantize path
   or the `k_v` handling — not in a CUDA kernel.
2. It survives the fix that demonstrably repairs generation.

So `6aa97d810` carries **two independent TQ4_1S defects**: the LUT bug (CUDA-only, garbage output,
fix known) and this NaN (both backends, cause unknown).

### Caveat — this does not clear `d0e2a8b64`

The failing case **does not exist in the rebase branch's test file** (0 occurrences of
`tq4_1s … k_v=1600` in its output vs 2 in the merged branch). So `d0e2a8b64` passes every test it
has, which is not the same as passing this one. Whether the good tree shares the latent NaN is
**open** — settling it would mean backporting the newer test file, which may pull in unrelated API
changes.

For Phase 1 this is acceptable: the shape in question (`m=256, n=256, k=1536, k_v=1600`) is a
prefill-scale batched matmul, and the KLD workflow will be checked against a CPU reference anyway.
But it should not be quietly forgotten.

## Reproduction

```bash
~/tom_rebase/build/bin/test-backend-ops -o MUL_MAT -b CUDA0   # 1344/1344, 3/3 backends
~/tom_sync/build/bin/test-backend-ops   -o MUL_MAT -b CUDA0   # 2/3 backends, rc=1, NaN
```

Scripts on `.73`: `~/phase0.sh`, `~/lut_ops.sh`. Raw output: `~/ops_GOOD.txt`, `~/ops_BROKEN.txt`,
`~/ops_LUTFIX.txt`. LUT patch: `~/tq_lut_fix.patch`.

## Next (Phase 1)

Blockers cleared except one: **pick and fetch an fp16/bf16 base model in the 4B–9B class**. Then
build the matched `--pure` ladder (TQ3_1S, TQ4_1S, IQ4_XS, Q4_K_S, Q4_K_M, Q5_K_S + Q8_0/fp16
reference), measure real bpw per arm with `tensor_bpb.py`, and compute KLD against the reference.
