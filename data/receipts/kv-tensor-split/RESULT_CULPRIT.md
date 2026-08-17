# The collapse enters at one commit — and the two forks got there independently

**2026-08-17**, `.73`, dual Tesla P100 (sm_60). Raw `~/probe_*.log`, scripts
`probe_series.sh`, `verify_bisect.sh`. Closes `BACKLOG U1`.

## The commit

```
5fd3089472b55ed42bb01b12c048d4d70496adb9
2026-07-31  jabbatheduck
cuda : add TurboQuant MMVQ/WHT/inner-quant CUDA kernels
```

| commit | | verdict |
|---|---|---|
| `89482bd66` | before any TurboQuant work | **clean** |
| `00fda770b` | ggml : core quant types + CPU kernels | **clean** |
| **`5fd308947`** | **cuda : TurboQuant MMVQ/WHT/inner-quant kernels** | **COLLAPSE** |
| `c3a048776` | sycl : WHT and vec kernels | collapse |
| `2a716ac47` | vulkan/metal/hip : kernel support | collapse |

`00fda770b` is the **direct parent** of `5fd308947` (verified with `rev-parse`), so this is a
single-commit isolation, not a range.

Test: `Qwen3.5-4B-BF16` (D=256, GQA 4:1), `-sm tensor -ts 1,1 -fa on -ctk q8_0 -ctv q8_0`,
`TURBO_AUTO_ASYMMETRIC=0`. Clean git worktree and a from-scratch build per commit.

## It touches exactly the right files

```
fattn-vec.cuh      +372    <- the path sm_60 actually takes
fattn.cu           +261
fattn-common.cuh   +504
fattn-mma-f16.cuh  +264
fattn-mma-turbo.cuh +118   (new)
mmvq-tq.cu         +568    (new)
```

**The `+261` on `fattn.cu` independently corroborates the file-level analysis.** Earlier the
same day, diffing upstream `34af94c` against the fork tree gave `fattn.cu` at 589 → 846 lines
and a 261-line diff. This one commit accounts for essentially the entire divergence. Two
methods — static diff and dynamic bisect — landing on the same file and the same magnitude.

## The first bisect was wrong, and why

An automated `git bisect run` over the 1,667-commit range first named
`2a716ac47 "vulkan/metal/hip : add TurboQuant kernel support"`. **That result was discarded.**

The tell was mechanical implausibility: that commit touches only Metal, Vulkan and HIP files —
**zero CUDA** — and the test runs CUDA on sm_60. A commit that changes no CUDA code cannot
change CUDA behaviour.

Re-testing with clean worktrees showed the harness was at fault: `bisect_test.sh` reused a
single build directory across every step, so incremental CMake across large commit jumps
produced stale or mixed binaries. A commit the bisect had called **GOOD** (`c3a048776`)
**collapses** when built from scratch. Every `good` verdict in that log was unreliable, so the
"first bad commit" was meaningless.

**Corrective:** a bisect that rebuilds must use a fresh build directory per step, or the
verdicts are not independent. And a bisect result should be checked against mechanism before
it is quoted — if the named commit cannot plausibly cause the symptom, it probably didn't.

## buun's fork reached the same failure independently

This is the part that changes the report.

| | result |
|---|---|
| `5fd308947` present in `buun_vbr` by SHA | **no** |
| any commit in `buun_vbr` with a matching subject | **none** |
| `fattn-vec.cuh` size | buun **718** lines · Tom **953** lines |

buun's fork does **not** carry this commit and his `fattn-vec.cuh` is a different, smaller
implementation. So the identical symptom — 512 `/` characters, first request, deterministic,
`q8_0` and `q4_0` symmetric, D=256, sm_60 — was arrived at **twice, independently**.

That makes the finding more interesting rather than less: it is not a shared bad commit
propagating, it is a **shared trap** in how quantized-KV dispatch gets added on hardware with
neither Turing MMA nor AMD WMMA. Two people solving the same problem in the same file hit the
same hole.

**Consequence for reporting:** Tom can be pointed at a specific commit. buun **cannot** —
he needs the *class* of defect and the reproduction, and has to find the analogous place in
his own dispatch. A "cherry-pick this fix" message would be wrong for him.

## What this does NOT establish

- **Not the line.** The commit is isolated; the specific hunk inside ~2,100 changed lines is
  not. `fattn-vec.cuh` is the strongest candidate because it is the path sm_60 takes, but
  that is reasoning, not measurement.
- **Not why.** The mechanism — D=256 dispatch behind a
  `turing_mma_available() || amd_wmma_available()` gate that is false on Pascal — is supported
  by the RDNA4 dissociation (`RESULT_RDNA4.md`) but this bisect does not prove it.
- **One model, one head dim, one arch.** D=256 on sm_60. The commit may be fine everywhere
  else, which is consistent with it having shipped.
- **`9421bd097`** ("WIP: add TurboQuant KV cache types") **does not compile**
  (`redeclaration of GGML_TYPE_Q1_0`), so it is genuinely untestable rather than skipped.
