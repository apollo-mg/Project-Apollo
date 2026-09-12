# Note — what a HIP port of EXL3 would take (ledger O1, source reading)

**2026-09-12, against buun `9ae8f0f40`. No code was written or compiled.** This is a reading of the
kernels, for Mark to relay to buun if it is useful. It matters because RDNA4 is a far larger installed
base than P100s, and buun has no AMD hardware.

## The encouraging part: the sm_60 fallback path is already HIP-shaped

Every Ampere-only construct in the int8 GEMV is guarded on `__CUDA_ARCH__`, and **HIP does not define
that macro**, so `#if __CUDA_ARCH__ >= 800` is false and the portable branch is taken automatically:

| construct | guard | what a HIP compile gets |
|---|---|---|
| `cp.async.cg.shared.global` + commit/wait groups | `__CUDA_ARCH__ >= 800` | a plain `uint4` copy into the same warp-private ring (`exl3-gemv-int8.cuh:33-51`) |
| `dp4a.u32.s32` (unsigned weights, signed activations) | `__CUDA_ARCH__ >= 610` | a scalar byte loop (`exl3-gemv-int8.cuh:64-78`) — correct, but see below |
| `__dp4a(x, 0x01010101u, acc)` byte sum | `__CUDA_ARCH__ >= 610` | scalar adds (`exl3-dq.cuh:15-21`) |

**That fallback path exists because of the P100 work.** It is the same path a first HIP port would use.

## What actually blocks a compile today

1. **The file is compiled out.** `exl3.cu:29` is `#if !defined(GGML_USE_HIP)`, and the entry points are
   `GGML_ABORT("EXL3 is CUDA only")` stubs (`exl3.cu:399-402`).
2. **`supports_op` returns false** for EXL3 `MUL_MAT` and `MUL_MAT_ID` under HIP (`ggml-cuda.cu:8678`).
3. **Three unguarded PTX idioms in the trellis decoder** (`exl3-dq.cuh`). Each has a one-line portable
   equivalent:
   - `EXL3_FSHF_IMM` → `shf.r.wrap.b32` (line 46) is a funnel shift: `__funnelshift_r(lo, hi, imm)`, which
     HIP provides.
   - `EXL3_BFE16_IMM` → `bfe.u32 d, src, imm, 16` (line 47) is `(src >> imm) & 0xFFFFu`.
   - `lop3.b32 x, x, 0x8fff8fff, 0x3b603b60, 0x6a` (lines 76, 77, 92, 101). **LUT `0x6a` is
     `(a & b) ^ c`**, so this is `x = (x & 0x8fff8fff) ^ 0x3b603b60`.
4. **The Ampere GEMV must be excluded from the compile.** `exl3-gemv.cuh:27` is inline
   `mma.sync.aligned.m16n8k16` PTX. It is already excluded at *runtime* by
   `compiled_cc >= GGML_CUDA_CC_AMPERE`, but it still has to compile.

## What needs no work at all

- **Warp shuffles.** `__shfl_sync` / `__shfl_xor_sync` with full masks work under HIP, and **RDNA is
  wave32**, matching the kernel's 32-lane assumptions. `THREADS = 256` is 8 waves.
- **Shared memory fits.** The static worst case is `MAX_M * COLS * 4 + 4096` = 12 KB, plus up to ~12 KB
  of staging at 6 bits. RDNA has 64 KB of LDS per workgroup.
- **The reconstruct + cuBLAS fallback** maps through ggml's existing shims: `cublasGemmEx →
  hipblasGemmEx` (`vendors/hip.h:47`), `cublasSetStream`, `CUBLAS_COMPUTE_32F`.

## One optimization worth doing immediately

The scalar `dp4a` fallback is correct but slow, and it is the inner loop. **RDNA3/4 have the
instruction:** ggml already maps `ggml_cuda_dp4a` to `__builtin_amdgcn_sudot4(true, a, true, b, c, false)`
for RDNA3/4 (`common.cuh:726`). EXL3 needs the *unsigned* weight bytes against *signed* activations,
which the same builtin expresses by setting the first sign flag false:
`__builtin_amdgcn_sudot4(false, a, true, b, c, false)`.

## Not portable, and not needed

The Ampere GEMV. On Pascal it never runs, and the int8 path beats reconstruct+cuBLAS by **2.9×**
(`kv-tensor-split/RESULT_EXL3_SM60_INFERENCE.md`), so a first HIP port can ship without it. RDNA4 has
WMMA if anyone wants the equivalent later.

## Caveat: CDNA is wave64

The MI-series is wave64, and the kernel's 32-lane shuffle math would need rework there. **RDNA3/4 is the
clean target** — which is the hardware Mark has.

## What source cannot tell us: performance

On Pascal the int8 path is compute-bound on trellis decoding, not bandwidth-bound: 7 t/s over 13.4 GB of
weights is about 94 GB/s against the P100's 732 GB/s. Whether RDNA4's `v_dot4` throughput and LDS
bandwidth land it near its own roofline is unknown until it runs. For scale, our 9070 XT decodes a 12 GB
IQ3_XXS GGUF of the same model at **32.1 t/s** (~390 GB/s effective, measured 2026-08-21).

## The tester is ready

Mark offered buun RDNA4 testing on 2026-09-12 at 15:01. The build tree is already standing:
`/mnt/TG_2TB/Projects/buun-9ae8f/build_rocm` at `9ae8f0f40`, `gfx1201`, with `llama-server` and
`llama-bench` built, and a 0.6B EXL3 snapshot local. Turnaround on a patch would be minutes.
