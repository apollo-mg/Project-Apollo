# `75a24b8f2` confirmed on RDNA4; `test/hip-vec-turbo-only` is correctness-neutral; the graph-capture abort is pre-existing and **nondeterministic**

RX 9070 XT (gfx1201, HIP arch 1300, wave32, 16,304 MiB), ROCm 7.2.4.
`test-backend-ops test -o FLASH_ATTN_EXT -b ROCm0`. Date 2026-08-02.
Builds: `75a24b8f2` (head) and `418b1759c` (`test/hip-vec-turbo-only`), same worktree,
incremental rebuild of one TU between arms — compiler, flags and ROCm held identical.

## 1. The fix is confirmed (graphs off)

| build | OK | FAIL | `no device code` | ratio-9 OK | died at |
|---|---|---|---|---|---|
| `75a24b8f2` | **7,604** | 0 | **0** | 784 | `hsk=576,hsv=512` in `..._tile` |
| `418b1759c` | **7,604** | 0 | **0** | 784 | same |
| *(my earlier revert arm)* | *7,604* | *0* | *0* | *784* | *same* |

`75a24b8f2` reproduces the revert-arm result exactly. The `ncols2 == 1` abort is gone, and
**the test branch is correctness-neutral** — identical on every counter. The remaining death is
the separate pre-existing `DKQ > 128` hole on the MLA geometry.

## 2. The graphs-on question: no detectable difference

Tom's question was whether narrowing the HIP VEC-forcing rule exposes the capture abort on the
TILE path — i.e. whether the branch trades Chris's perf bug for a crash bug.

**First measurement (K=1 per arm) appeared to say yes:** head 3,951 OK before aborting vs branch
997 — a 4× regression, with a plausible mechanism ready to explain it (more shapes routed to
TILE, which allocates raw temp buffers during capture).

**It was noise.** Repeating at K=3:

| build | graphs-on OK counts (line-buffered) |
|---|---|
| head `75a24b8f2` | 927, 957, 3951, 5260 |
| branch `418b1759c` | 907, 997, 2701, 5876 |

The ranges overlap almost completely; the head's median is if anything *higher*. **The abort
point varies by ~6× run to run on an unchanged binary.** No conclusion about the branch survives.

**Answer: no evidence the branch introduces or worsens the capture abort.**

### Direct test of the re-routed set

Isolating exactly the tests the branch changes — quantized KV, small batch — under graph capture:

```
-o FLASH_ATTN_EXT -p 'nb=[1-8],.*type_K=q8_0'   (graphs ON)
  head   : 545 OK, 0 capture-aborts
  branch : 545 OK, 0 capture-aborts
```

Both clean. The re-routed tests do not trigger the abort in isolation on either build.

## 3. The capture abort itself

Identical on both builds — same error, same backtrace:

```
ROCm error: operation not permitted when stream is capturing
  current device: 0, in function ggml_cuda_compute_forward at ggml-cuda.cu:2450
  ggml-cuda.cu:108: ROCm error
#5 ggml_cuda_error
#6 ggml_cuda_graph_evaluate_and_capture
#7 ggml_backend_cuda_graph_compute
#8 ggml_backend_compare_graph_backend
```

**It is stateful and nondeterministic**, which has a practical consequence: `test-backend-ops`
cannot localize it, and any single-run comparison of it is meaningless.

Two attribution methods were tried and both failed:

- *Last descriptor before the abort.* Even under `stdbuf -o0`, `test-backend-ops` prints the
  descriptor and verdict **together after** the test completes, so the failing test is never
  printed at all.
- *Next test in deterministic suite order* (recovered by locating the last passing descriptor in
  the graphs-off log, which runs much further). This yields a specific shape — but the shape it
  named for the branch (`hsk=64,nr23=[1,3],nb=75,bf16`) **passes on the head's graphs-on run**,
  while the branch diff touches only *quantized* types and bf16 is not one. The inference is
  therefore unsound: the abort reflects accumulated capture state, not the current op.

## Limits

- K=3–4 per arm on graphs-on. Enough to establish the spread is enormous and swamps any
  difference; **not** enough to exclude a small real effect. A difference smaller than ~6×
  cannot be resolved by this instrument at this K.
- One GPU, one arch, one ROCm version.
- The graphs-off arms are K=1, but they are deterministic (identical counters across builds and
  across the earlier revert arm), so this is not a concern there.
- No claim is made about RDNA3 (Chris's card) or about whether the branch fixes his 123K
  throughput gap — untested here.

## What this means for the thread

- `75a24b8f2` does what it says on RDNA4. **Finding formally closed.**
- The branch is safe to evaluate on perf grounds; the crash concern that gated it is not
  supported by RDNA4 data.
- The capture bug (#247/#251) needs a **reproducibility protocol**, not a single run — anyone
  measuring it, on any vendor, will get a different answer each time.

## Provenance

- Scripts `scratchpad/tq_249_verify.sh`, `scratchpad/tq249_stdbuf.sh`
- `logs/tq249_*.log` (block-buffered arms), `logs/sb_*.log` (line-buffered),
  `logs/rep_{head,branch}_{1,2,3}.log` (K=3 reproducibility), `logs/filt_*.log` (isolated set)
- Worktree `/mnt/TG_2TB/tmp_pr244`
