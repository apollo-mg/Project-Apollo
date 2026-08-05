# Preserved: the `k_v=1600` TQ test cases from the deleted `sync/upstream-master`

**Why this file exists.** These two `test-backend-ops` cases are the only test in either branch that
surfaces the TQ4_1S non-contiguous-`src1` NaN. They were added on TheTom's `sync/upstream-master`,
which was **deleted from the repo** on or before 2026-08-04 (`git fetch --prune` reports
`- [deleted] (none) -> thetom/sync/upstream-master`). They were never ported to the default branch —
`grep -c k_v=1600` on `feature/turboquant-kv-cache` @ `0967f4997` returns **0**.

The only remaining accessible copy is pinned by the `/home/mark/tom_sync` worktree on `.73`, which
holds `6aa97d810` checked out. Removing that worktree and running `git gc` would destroy it.
Copied here verbatim so the coverage survives independent of that machine.

Source: `6aa97d810:tests/test-backend-ops.cpp`, lines 9144–9149.

```cpp
    // TQ3_1S / TQ4_1S: non-contiguous src1 (k_v > k view) with batched n, to exercise
    // the rotate-act contiguity fallback. rotate-act walks src1 as a flat array so it
    // requires contiguous src1; non-contiguous must fall back to the standard mul_mm
    // path (inverse-RHT dequant), which handles strides via nb1x.
    test_cases.emplace_back(new test_mul_mat(GGML_TYPE_TQ3_1S, GGML_TYPE_F32, 256, 256, 1536, {1, 1}, {1, 1}, {0, 1, 2, 3}, 1600));
    test_cases.emplace_back(new test_mul_mat(GGML_TYPE_TQ4_1S, GGML_TYPE_F32, 256, 256, 1536, {1, 1}, {1, 1}, {0, 1, 2, 3}, 1600));
```

## Applying to the default branch

`test_mul_mat`'s member layout is identical on both branches —
`m, n, k, bs[2], nr[2], per[4], k_v` — with the same `k_v` semantics
(*"size of k in memory, resulting in a non-contiguous view for k_v > k, no view for k_v == 0"*).
The 8-argument constructor call therefore compiles unchanged; no API surface needs porting.

Insert immediately before the `// TQ4_1S: large-batch MUL_MAT exercises` comment block
(line 9193 at `0967f4997`). Verified: builds clean, adds 6 lines including comments.

## What it finds on `0967f4997` (default branch, sm_60)

```
Backend 1/3: CUDA0   1483/1484 tests passed
  [MUL_MAT] NaN at index 245 (CUDA0=8.191498  CPU=nan)     Backend CUDA0: FAIL
Backend 2/3: CUDA1   1483/1484 tests passed
  [MUL_MAT] NaN at index 246 (CUDA1=5.454212  CPU=-nan)    Backend CUDA1: FAIL
Backend 3/3: CPU
1/3 backends passed
```

**CUDA returns finite values; the CPU reference returns NaN.** The failures are booked against the
CUDA backends only because every backend is compared against the CPU reference — CPU itself is
never exercised as a backend (`Skipping CPU backend`), so a fault in the reference can only ever
surface as other backends failing. TQ3_1S at the same shape reports `not supported` and is skipped —
the defect is TQ4_1S-specific.

⚠️ CUDA is **not** thereby shown correct: the two CUDA backends report different values at different
indices (8.191498 @ 245, 5.454212 @ 246), and with the reference NaN there is nothing to check them
against.

## This is not the only missing coverage

The two files differ by 29 TQ-relevant lines, including **6 further `test_mul_mat` cases** absent
from the default branch — see `preserved/tq_coverage_delta.txt`, with the complete deleted-branch
file at `preserved/test-backend-ops.cpp.6aa97d810`.

Full analysis and limits in `TQ4_1S_PASCAL_REGRESSION.md`.
