# Result -- O8: EXL3 on Pascal is three separate walls, and only the first one is tensor cores

**2026-09-20, `.73`** (2x Tesla P100, sm_60). Resolves ledger objection **O8**, open since
2026-09-12 when `NOTE_EXL3_QUANTIZER_ON_SM60.md` read the source and found no blocker in what it
sampled.

> **This receipt supersedes an earlier version of itself.** The first pass (commit `a1ec57d`)
> concluded *"the cause is tensor cores"* and stopped at the first compiler error. That was the
> first error, not the cause. Compiling the whole tree with `ninja -k 0` showed **107 of 108
> failures had nothing to do with tensor cores.** The corrections are itemised at the bottom.

## What actually blocks the build

`exllamav3` 1.5.0, `TORCH_CUDA_ARCH_LIST=6.0`, CUDA 12.4, gcc-13 pinned. Building the full tree
with keep-going rather than stopping at the first error: **108 of 138 targets fail.**

| failures | cause | arch required | kind |
|---:|---|---|---|
| **107** | `__dp4a` undefined, `__nanosleep` undefined | sm_61, sm_70 | **missing intrinsic, front-end** |
| **1** | `mma`, `.m16n8k16`, `ldmatrix`, `cp.async` | sm_70/sm_80/sm_75/sm_80 | inline PTX, ptxas |

The tensor-core failure is real but it is **one file** (`hgemm_f16acc.cu`). Everything else died
earlier, on two identifiers that simply do not exist below their introducing architecture:

```
quant/codebook.cuh(35): error: identifier "__dp4a" is undefined
ptx.cuh(343):           error: identifier "__nanosleep" is undefined
```

## The finding: a GTX 1080 clears a bar the P100 does not

**`__dp4a` is sm_61.** It arrived on GP102/GP104 -- the GTX 1080, 1080 Ti, and Tesla P40. It is
**absent on GP100**, the sm_60 die in the P100. GP100 spent its transistor budget on fast FP16 and
FP64 and did not get the INT8 dot-product instruction that its cheaper siblings received.

So the $3000-at-launch datacentre Pascal fails a compile that a gaming card of the same generation
passes. This is the sharpest single fact in the whole campaign and it is not a tensor-core story at
all.

## The blocker is code turboderp already wrote and commented out

`quant/codebook.cuh` uses `__dp4a` for one purpose: summing the four bytes of a word during
trellis codebook decode. Directly above each call sits the previous implementation, commented out,
with the author's own note:

> *"Byte sum via dp4a, bit-identical to the previous vabsdiff4(x, 0, acc) but native on Blackwell
> where vabsdiff4 is emulated."*

`vabsdiff4` is **sm_50 (Maxwell)**. It runs on a P100. The portable path is present in the file,
is documented by its author as producing identical bits, and was swapped out for a Blackwell
performance win -- not for a correctness or capability reason.

`__nanosleep` is a backoff hint inside spin-wait loops in the multi-GPU collectives. Omitting it
leaves a correct, busier spin.

## The patch: 46 lines, no source edits

`o8-sm60-patch/exl3_sm60_compat.cuh`, force-included into every CUDA translation unit via
`nvcc -include`. It defines software `__dp4a` (both overloads, correct for **all** operands, not
just the byte-sum case exllamav3 happens to use) and a no-op `__nanosleep`, each guarded to the
device pass below the introducing arch.

One subtlety worth recording: the guards must be `#if defined(__CUDA_ARCH__) && __CUDA_ARCH__ < 610`,
**not** `#if !defined(__CUDA_ARCH__) || ...`. CUDA declares both identifiers in the **host** pass
(where `__CUDA_ARCH__` is undefined), so the permissive form collides with the real declaration and
fails with *"function has already been defined"*. Cost me one build cycle.

## Result: every quantizer kernel compiles on sm_60

Failures drop **108 -> 92**, and the composition changes completely.

| target | round 1 | round 2 (shim) |
|---|---|---|
| `quantize.cuda.o` | FAILED | **BUILT** (216,240 B) |
| `quantize_tiles_inst_k1..k8` | FAILED (all 8) | **BUILT (all 8)** |
| `reconstruct.cuda.o` | FAILED | **BUILT** (9,968,184 B) |
| `pack.cuda.o` | FAILED | **BUILT** (213,912 B) |
| `hadamard.cuda.o` | FAILED | **BUILT** (480,456 B) |
| `hgemm.cuda.o` | FAILED | **BUILT** (109,168 B) |

**Every one of the 92 remaining failures is an inference or multi-GPU-collective kernel. Zero are
quantizer kernels.**

| remaining failures | what it is |
|---:|---|
| 38 | `exl3_moe_inst_*` -- MoE inference GEMM |
| 24 | `exl3_comp_unit_*` -- dense EXL3 inference GEMM |
| 14 | `exl3_gemv_int8_inst_*` -- int8 GEMV inference |
| 8 | `exl3_moe_coop_*` -- cooperative MoE |
| 6 | `parallel/*`, `cpu/moe_handoff` -- collectives (sm_70 memory model) |
| 2 | `exl3_gemv`, `hgemm_f16acc` |

The features they need: `.m16n8k16` and `mma` (5,936 errors each), `cp.async` (4,586),
`cp.async.commit_group` (4,068), `ldmatrix` (1,680), `cp.async.wait_group` (1,421), and the sm_70
memory model qualifiers `.acquire` / `.acq_rel` / `.relaxed` (1,066 each).

## Why the quantizer needs none of it

The conversion path calls exactly seven extension functions: `had_r_128`, `hgemm`, `hgemm_recon`,
`reconstruct`, `reconstruct_had_slice`, `reconstruct_slice`, `split`, plus `quantize_tiles` and
`quantize_tiles_scratch` from `modules/quant/exl3_lib/`. Checked directly, **every quantizer-path
source uses zero `cp_async`, zero `ldsm4`, zero `mma` and zero `__nanosleep`**; `codebook.cuh`'s
six `__dp4a` calls were the only contact with anything above sm_60.

And the one tensor-core file the quantizer does touch is already optional. `hgemm.cu:117` reads:

```c
if (hgemm_f16acc_try(a, w, c)) return;   // ... cuBLAS immediately below
```

The fp16-accumulator MMA kernel is a *try*, with a cuBLAS fallback behind it, by design.

**Separately worth noting:** `LinearEXL3.forward` (`modules/quant/exl3.py:132-139`) dispatches on
row count -- at most `AUTO_RECONSTRUCT_THRESHOLD = 144` rows it runs the packed EXL3 kernel,
above that it runs `reconstruct` + `hgemm_recon`. **That second path compiles on sm_60 today.** So
even EXL3 *inference* has an architecturally available route on Pascal; what is missing is the
fast packed one.

## The extension was then patched all the way to a working build

Going further than the shim: **24 inline-PTX statements** across `ptx.cuh`, `hgemm_f16acc.cu` and
`quant/exl3_gemv_kernel.cuh` were wrapped in `#if __CUDA_ARCH__ >= 800 ... #else __trap(); #endif`
(`o8-sm60-patch/guard_ptx.py`), two one-liner `cp.async` helpers were guarded by hand, a runtime
`props->major < 8` gate was added to `hgemm_f16acc_try` so `hgemm.cu` takes its cuBLAS path, and
the one raw `dp4a.u32.s32` asm in the int8 GEMV kernel got a correct software fallback rather than
a trap.

Trapping rather than silently no-opping is deliberate: anything guarded out is, by construction,
only reachable from the 92 inference targets, and **all quantizer targets had already compiled
clean in round 2, which proves they emit none of these instructions.** A trap turns a wrong
assumption into a crash instead of a wrong quant.

| round | patch | failed targets |
|---|---|---:|
| 1 | none | 108 of 138 |
| 2 | `exl3_sm60_compat.cuh` (46 lines) | 92 |
| 4 | + 24 PTX arch guards | 6 |
| 5 | + `dp4a_us` software fallback | **0 of 100** |

```
exllamav3_ext.so   161,894,880 B

IMPORT OK
torch 2.6.0+cu124 devices 2
   0 Tesla P100-PCIE-16GB (6, 0)
   1 Tesla P100-PCIE-16GB (6, 0)
   has quantize_tiles True   has reconstruct True   has pack_trellis True
   has hgemm True            has had_r_128 True
```

**The extension builds, links and imports on two Tesla P100s, with every quantizer entry point
live.** One operational wrinkle: torch's JIT leaves a stale `lock` file in
`~/.cache/torch_extensions/.../exllamav3_ext/` if a build is interrupted, after which every later
import blocks forever in `hrtimer_nanosleep` with no output. Delete the `lock` file.

## Then convert.py failed anyway -- on Triton, not on Pascal

Conversion of Qwen3-0.6B (fp16 source sha256 `f47f7117...`, matched to turboderp's own
`Qwen3-0.6B-exl3-4.0bpw`: 4.0 bpw, head 6, 100x2048 calibration) got as far as creating the job,
loading the config, instantiating all 28 blocks, loading the tokenizer and resolving RoPE -- then
died compiling a **Triton** kernel:

```
chained boolean operators (A or B or C) are not supported; use parentheses to split the chain.
  ... in _paged_attn_prefill_inner
```

exllamav3 1.5.0 ships its flash attention as a **Triton** kernel and offers no alternative:
`prepare_for_attn` accepts only `flash_attn` and `flash_attn_nc`, both Triton. The calibration
forward pass therefore cannot avoid it. Triton 3.2.0 (the version pinned by torch 2.6.0) rejects
syntax the kernel uses.

**This is a version-skew bug, unrelated to sm_60.** But testing Triton directly on the P100 found
something that is not:

| Triton 3.2.0 on sm_60 | result |
|---|---|
| elementwise kernel | **OK**, exact (err 0.0) |
| `tl.dot`, fp16 | **LLVM ERROR: Unsupported conversion from f16 to f16 / Unsupported rounding mode** |
| `tl.dot`, fp32 | **OutOfResources: shared memory required 131,072 B, hardware limit 49,152 B** |

Triton runs fine on Pascal until you ask it to multiply matrices. The fp16 path -- the one an
attention kernel needs -- is a hard codegen crash inside LLVM, not a slow fallback. So upgrading
Triton to fix the syntax error would not have produced a working conversion either; it would have
moved the failure from the parser to the code generator.

**Note the shared-memory number.** sm_60 caps shared memory at **48 KB per block** against sm_80's
~163 KB, and that ceiling has now bitten twice: Triton's default matmul tiling wants 128 KB, and
the quantizer's own K=2 configuration computes to 66,240 B (below).

## Verdict, in three layers

**1. exllamav3's CUDA extension: "it is doable, the community just needs to tidy some things up."**
**Demonstrated, not argued.** A 46-line shim plus 24 mechanical arch guards takes it from 108
failures to a linked, importable extension on sm_60 with every quantizer kernel present. The
blocking intrinsic has a portable equivalent that the author already wrote, documented as
bit-identical, and left in the file as a comment. The upstream ask is small and specific.

**2. The conversion pipeline end to end: "it can probably be done, but with some heavy lifting."**
Not because of exllamav3's CUDA code -- that part is tidying -- but because calibration runs
attention through Triton, and **Triton cannot generate an fp16 matmul for sm_60 at all.** Closing
that means either upstream Triton/LLVM work or giving exllamav3 a non-Triton attention path for
old hardware. Neither is a patch you write in an afternoon, and neither is in turboderp's tree.

**3. EXL3's packed inference kernels: "this will probably never work pre-Ampere."**
`m16n8k16` + `cp.async` + `ldmatrix` + the sm_70 memory model are the algorithm, not the
packaging: asynchronous global-to-shared staging feeding tensor-core fragments. 92 targets. No
shim helps. The `reconstruct` + `hgemm_recon` route (taken above `AUTO_RECONSTRUCT_THRESHOLD =
144` rows) does compile and is the only architecturally available path on Pascal.

**The boundary is not "pre-Volta".** `m16n8k16` and `cp.async` are sm_80, so a V100 (sm_70, which
*does* have tensor cores) and a T4 / RTX 2080 (sm_75) fail the same way. Ampere is the floor for
the packed kernels; sm_61 is the floor for the quantizer as shipped.

## What is established and what is not

**Established:** the extension compiles, links and imports on sm_60 with all quantizer entry
points; the 108 -> 92 -> 6 -> 0 progression; the Triton `tl.dot` failures; the 48 KB ceiling.

**Not established: no EXL3 quant was produced on Pascal.** The conversion never reached the first
quantized layer, so `quantize_tiles` has been *linked and exposed* but never *executed*. Whether
the `__dp4a` software fallback is numerically correct in situ is therefore **untested** -- it is
correct by construction and matches upstream's own "bit-identical" note, but that is an argument,
not a measurement. The gate for the stronger claim remains perplexity against the
`Qwen3-0.6B-exl3-4.0bpw` reference already on `.73`, at matched bitrate. See
[[readiness-probes-lie]].

**A K=2 ceiling, computed but not observed.** `quantize.cu:128` sets dynamic shared memory to
`cost_arrays * (65536 >> K) * 2 + L * 2 + 192`, and `quantize_tiles_use_optimized` returns false
for major 6, so `cost_arrays = 2`. That gives **66,240 B at K=2** against sm_60's 48 KB ceiling, so
2-bit conversion should fail at `cudaFuncSetAttribute` even though the kernel compiles. K=1 (704 B),
K=3 (33,472 B) and above fit. **Derived from source arithmetic, never executed.**

## Corrections to the previous version of this receipt

| claim in `a1ec57d` | status |
|---|---|
| *"the cause is tensor cores"* | **FALSE for 107 of 108 failures.** The cause was two undefined intrinsics. |
| *"The constraint is Ampere-class tensor cores, so it applies to every pre-Volta card"* | **WRONG IN BOTH DIRECTIONS.** `__dp4a` is sm_61, so it bites sm_60 specifically; `m16n8k16`/`cp.async` are sm_80, so Volta and Turing fail too. "Pre-Volta" is the one framing the evidence excludes. |
| *"Ampere-class tensor cores"* | Imprecise. Tensor cores are Volta (sm_70); the binding constraint is the **`m16n8k16` shape** and `cp.async`, both sm_80. |
| *"unknown whether the quantizer PATH actually calls `hgemm_f16acc`"* | **RESOLVED.** It calls `hgemm`, which tries `hgemm_f16acc_try` and falls back to cuBLAS. |
| *"stub it and see whether convert.py runs ... Not attempted"* | **Attempted.** Result above: the stub was not even needed for the quantizer kernels; a shim for two intrinsics was. |

What survives unchanged: PyTorch is innocent (2.6.0+cu124 ships sm_60), and the 2026-09-12 source
reading missed this because it sampled 6 of 113 CUDA sources and said so.

## Artifacts

`o8-sm60-patch/`:

| file | what |
|---|---|
| `exl3_sm60_compat.cuh` | the 46-line shim (`__dp4a`, `__nanosleep`) |
| `guard_ptx.py` | wraps inline-PTX statements in arch guards (24 sites) |
| `fix_oneliners.py`, `fix_dp4a_asm.py`, `patch_extpy.py` | the remaining hand patches |
| `triton_sm60_probe.py` | the `tl.dot` probe |
| `round1_summary.md`, `round2_summary.md` | deduped failure lists and feature tallies |
| `exl3_keepgoing.log.gz`, `exl3_round2.log.gz`, `exl3_round5.log.gz` | raw builds (108 / 92 / 0 failures) |
| `exl3_convert.log` | the conversion run, up to the Triton error |

## Ledger

**O8: CONFIRMED, with the cause restated and the patch idea closed out.** We still cannot make
EXL3 quants on this fleet. But the reason is not the one the first pass gave:

- Pascal lacking tensor cores blocks **1 of 108** build failures.
- exllamav3's own extension is **fixable** -- proven, it now builds and imports on two P100s.
- What stops the conversion *on this install* is **Triton version skew**: Triton 3.2.0 (pinned by
  torch 2.6.0) will not parse exllamav3 1.5.0's attention kernel.
- A Triton upgrade is **unlikely to rescue it**, because fp16 `tl.dot` is an LLVM codegen crash on
  sm_60 -- but that is an inference from a direct probe, **not** a conversion that was run against
  a Triton which parses the kernel.

So the honest one-liner for the article is: *EXL3 quantization on Pascal is not blocked by missing
tensor cores -- the extension can be patched to build and import. It is blocked one layer up, by a
compiler that cannot emit an fp16 matmul for sm_60.*

**Distinct from [[exl3-on-pascal]]**, which measured buun's llama.cpp EXL3 *reader* on these
cards -- a different codebase answering a different question.
