# PR #295 runtime on RDNA4: the surviving VGPR spill costs nothing measurable

**2026-08-17**, control plane **RX 9070 XT (gfx1201, RDNA4, ROCm/HIP)**.
Answers the open runtime question in `TheTom/llama-cpp-turboquant#294` — *"a turbo2/turbo3
decode run against `f6124e914` on any RDNA part would settle whether a 20-60 VGPR residual is
worth chasing or worth leaving alone"* — and closes the gap our own
`RESULT_PR295_GFX1201.md` listed under *"What this does NOT answer: the performance question."*

> **CORRECTED 2026-08-17, same evening — before anything was sent.** The first pass (5 reps)
> showed turbo2/3/4 all improving monotonically at D=128. **A 12-rep re-run does not
> replicate that**: turbo2 goes −0.3 %, turbo3 −0.9 %, turbo4 +1.0 %. The signs flip.
>
> The deltas are **within run-to-run noise in both directions**, and the noise is not confined
> to D=256 — the 12-rep pass has ±1.35 and ±1.74 cells at D=128 too. This machine shows
> intermittent 1–2 % (occasionally 6 %) variance between otherwise identical runs.
>
> **The defensible claim is "no measurable regression, and no resolvable difference either
> way at ±1 %".** That still answers #294's question — a residual that costs nothing
> detectable is not worth chasing — but it is *not* the monotonic improvement the first pass
> appeared to show. Corrected table below; both passes retained.

**Paired build, same card, same models, same flags — only the commit differs:**

| build | | gfx1201 spill state |
|---|---|---|
| `fca3093c9` | pre-fix baseline | 98 FA kernels spilling, worst 735 |
| `f6124e914` | **#295 merge** | 41 spilling, worst 357 |

`llama-bench`, pure decode (`-p 0 -n 128`), 5 reps, `-fa 1`, `TURBO_AUTO_ASYMMETRIC=0`.
Both models sit below the 6:1 auto-asymmetric gate (GQA 3:1 and 4:1) so it cannot fire and
silently swap K. Script `bench_rdna4.sh`.

## head_dim 128 — where the residual lives

`Llama-3.2-3B-Instruct-BF16`, D=128, GQA 3:1. This exercises the
`<128,2,turbo-K,*>` class TheTom flags as *"a shape decode really launches"*, and which
`RESULT_PR295_GFX1201.md` showed does **not** reach zero on gfx1201 — it survives at
**23-57 VGPR**.

| KV | pre `fca3093c9` | post `f6124e914` | delta |
|---|---:|---:|---:|
| f16 *(control)* | 74.11 ± 0.34 | 73.25 ± 1.48 | −1.2 % |
| **turbo2** | 72.63 ± 0.22 | **72.93 ± 0.18** | **+0.4 %** |
| **turbo3** | 72.23 ± 0.23 | **72.79 ± 0.18** | **+0.8 %** |
| **turbo4** | 71.60 ± 0.20 | **72.29 ± 0.19** | **+1.0 %** |

**12-rep re-run of the same comparison:**

| KV | pre `fca3093c9` | post `f6124e914` | delta |
|---|---:|---:|---:|
| f16 *(control)* | 74.39 ± 0.27 | 73.55 ± 1.35 | −1.1 % |
| turbo2 | 72.95 ± 0.26 | 72.71 ± 0.36 | −0.3 % |
| turbo3 | 72.67 ± 0.22 | 72.00 ± 1.74 | −0.9 % |
| turbo4 | 71.81 ± 0.29 | 72.50 ± 0.19 | +1.0 % |

**The two passes disagree in sign on turbo2 and turbo3.** Taken together, six independent
measurements of the same three comparisons land between −0.9 % and +1.0 % with no consistent
direction. The effect is not resolvable at this precision on this machine.

### The answer to the question as asked

**The surviving 23-57 VGPR spill costs no measurable decode throughput on RDNA4.** Across two
passes the difference never exceeds ±1 % and does not hold a sign. **TheTom's guess — leave it
alone — is supported**, and the residual does not justify the larger "teach the LUT paths to
stride and reduce" change.

Stated precisely: this is a **null result at ±1 % resolution**, not a demonstrated improvement.
A real 1 % effect would need many more reps on a quieter machine to separate from noise.

Second, on the PR's other open point — whether the fix avoids the reported **12-31 % turbo2
decode regression on `ncols=1`**: **no such regression appears on gfx1201.** turbo2 measured
+0.4 % and −0.3 % across the two passes. Whatever produced 12-31 % elsewhere does not
reproduce on this architecture — and a 12-31 % effect would be an order of magnitude above
this machine's noise floor, so it is a real absence rather than a resolution limit.

## head_dim 256 — measured, but NOT quotable at this rep count

`Qwen3.5-9B-Q8_0`, D=256, GQA 4:1. Exercises residual buckets #1 (18 kernels @ 57 VGPR) and
#2 (4 kernels @ 357, the worst survivor).

| KV | pre `fca3093c9` | post `f6124e914` |
|---|---:|---:|
| f16 | 54.44 **± 3.34** | 56.09 ± 0.28 |
| turbo2 | 56.42 ± 0.21 | 54.97 **± 3.28** |
| turbo3 | 56.52 ± 0.12 | 56.19 ± 0.25 |
| turbo4 | 55.76 ± 0.15 | 56.29 ± 0.21 |

**Two of eight D=256 cells show ~±3.3 (≈6 %) while the other six sit at ±0.1-0.3.**

The 12-rep re-run tightened D=256 considerably and every cell moved the same way:

| KV | pre `fca3093c9` | post `f6124e914` | delta |
|---|---:|---:|---:|
| f16 | 56.59 ± 1.19 | 56.98 ± 0.24 | +0.7 % |
| turbo2 | 56.04 ± 1.37 | 56.59 ± 0.21 | +1.0 % |
| turbo3 | 56.27 ± 0.16 | 56.42 ± 0.24 | +0.3 % |
| turbo4 | 55.65 ± 0.19 | 56.43 ± 0.19 | +1.4 % |

All four post-fix, including the **f16 control the fix does not touch** — which is the tell
that this is a machine-state offset between the two build's runs, not an effect of the commit.
**No delta is claimed at D=256.**

The first high-variance cell was the first D=256 run after a model swap, which suggested
warm-up. **That explanation is wrong** — the second (post-fix turbo2) was mid-sequence. The
cause is intermittent and unidentified; the control plane is also Mark's active desktop, so
contention is the leading suspect. A 12-rep re-run is in flight.

Recording this rather than quoting the tidy-looking subset, because picking the six clean
cells and ignoring the two noisy ones would manufacture a result.

## Provenance — the numbers apply to the commit he named

The build-only spill sweep in `RESULT_PR295_GFX1201.md` was measured against **`f050a2501`**
(the fix commit), while #294 asks about **`f6124e914`** (the merge). Checked before
publishing: the only delta between them touching flash attention is in `fattn-common.cuh`,
and it is `(void)` casts to silence `[[nodiscard]]` on `cudaStreamSynchronize`/`cudaFree`
inside a destructor. No functional change, no register-allocation impact. The other file
(`ggml-cuda.cu`) is a host-side RDNA2 stream-capture fix. **The spill numbers carry.**

This runtime bench builds `f6124e914` directly, so it needs no such caveat.

## What this does NOT establish

- **One card, one vendor.** gfx1201 only. Says nothing about gfx1030/1100/1103, where the
  residual counts and the starting spill state are very different.
- **Decode only.** `-p 0 -n 128`. No prefill, no long-context, no batch > 1. Prefill takes the
  TILE/MMA path and is a different question.
- **Not fidelity.** Throughput only. Nothing here says the output is correct — that needs a
  KLD or hazard panel.
- **`ncols=2` is inferred, not forced.** The bench runs ordinary decode; `ncols=2` arises via
  GQA packing rather than being pinned by a flag. A shape-pinned microbenchmark would be
  stronger.
