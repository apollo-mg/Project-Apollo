# Result -- O8 CONFIRMED: we cannot make EXL3 quants on Pascal, and the cause is tensor cores

**2026-09-20, `.73`** (2x Tesla P100, sm_60). Resolves ledger objection **O8**, open since
2026-09-12 when `NOTE_EXL3_QUANTIZER_ON_SM60.md` read the source and found no blocker in what it
sampled.

## The blocker

`exllamav3` 1.5.0's CUDA extension **fails to compile for sm_60**:

```
exllamav3_ext/hgemm_f16acc.cu   (nvcc -gencode=arch=compute_60,code=sm_60)

ptxas error : Feature 'mma' requires .target sm_70 or higher
ptxas error : Feature '.m16n8k16' requires .target sm_80 or higher
ptxas fatal : Ptx assembly aborted due to errors
```

**`mma.m16n8k16` is a tensor-core instruction requiring Ampere (sm_80).** `mma` in any form
requires Volta (sm_70). **Pascal has no tensor cores at all.** This is silicon, not configuration
-- no flag, compiler or version changes it.

## What it is NOT -- every other hypothesis was tested and cleared

| hypothesis | result |
|---|---|
| PyTorch dropped Pascal | **FALSE.** torch 2.6.0+cu124 ships `sm_60`: arch list is `['sm_50','sm_60','sm_70','sm_75','sm_80','sm_86','sm_90']` |
| torch cannot see the P100s | **FALSE.** Both visible, and an **fp16 matmul executed on device** |
| torch too old for exllamav3 (needs >= 2.6.0) | **FALSE.** 2.6.0 exactly meets the floor |
| Python too new (3.14 vs cp313 wheels) | **CLEARED.** `uv 0.12.6` was already installed; `uv python install 3.13` took seconds, no root |
| CUDA/gcc mismatch | **CLEARED.** CUDA 12.4 with gcc-13 pinned; the C++ TUs compiled fine |
| disk space | **CLEARED.** 66 GB freed earlier the same day |

**The interesting part is that the obvious suspect was innocent.** "You can't quantize on old
hardware because PyTorch dropped it" is the intuitive answer and it is wrong here. PyTorch still
supports Pascal; **exllamav3 does not.**

## Why the source reading missed it

`NOTE_EXL3_QUANTIZER_ON_SM60.md` (2026-09-12) sampled **6 of 113 CUDA sources** and recorded its
own limit plainly:

> *"Not found in what I read: bf16, `mma.sync`, `cp.async`, or an sm_80 floor."*
> *"The repo has 113 CUDA sources; most were not read."*

`hgemm_f16acc.cu` was not among the six. **The note's stated limitation was the actual
limitation** -- which is the argument for compiling rather than reading. One `TORCH_CUDA_ARCH_LIST=6.0`
build answered in 82 seconds what source sampling could not answer in principle.

## Open follow-up, if it ever matters

`exllamav3` ships inference and conversion in one extension, so the build is all-or-nothing. It is
**unknown whether the quantizer PATH actually calls `hgemm_f16acc`** -- half-precision GEMM with
fp16 accumulate reads like an inference kernel, not a trellis-encoding one.

**A test exists:** stub out `hgemm_f16acc.cu`, rebuild, and see whether `convert.py` runs. If it
does, Pascal quantization is possible with a local patch, and that is a one-line upstream ask
(guard the file behind `__CUDA_ARCH__ >= 800`). Not attempted -- this was scoped as a quick look,
and the headline answer is already decided for any unpatched install.

## Ledger

**O8: CONFIRMED.** We cannot make our own EXL3 quants on this fleet without patching upstream.
The constraint is **Ampere-class tensor cores**, so it applies to every pre-Volta card, not just
these P100s.

Combined with `NOTE_QUANTIZER_SUPPORT_MATRIX.md`, EXL3's "who can make one" answer is now measured
on both of this fleet's architectures: **RDNA4 no (CUDA-only), Pascal no (needs sm_80).**
