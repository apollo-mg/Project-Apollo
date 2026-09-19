# Result -- S5 / charter (g): SCALE 1.7.1 vs 1.7.3 on gfx1201

**2026-09-18.** Final milestone of Avarok-Cybersecurity/atlas#1126. RX 9070 XT (16 GB, headless),
Ornith-1.0-9B-NVFP4, Ubuntu 24.04 container, both toolchains bind-mounted from the host with
sha256 recorded at fetch.

Charter (g): *"S1 census and probes, plus decode and TTFT, on SCALE 1.7.1 and 1.7.3 ... both
recorded side by side."*

## The headline

**1.7.3 trades prefill for decode, costs 1.9x the compile time, changes no capability, and fixes
neither #1119 defect.** On this evidence there is no reason to upgrade.

| axis | 1.7.1 | 1.7.3 | delta |
|---|---:|---:|---|
| census result | **180/180 clean** | 179/180 + **1 TIMEOUT** | -1 |
| census wall (serial) | 741 s | 1407 s | **1.90x slower** |
| median per-file compile | -- | -- | **1.00x (unchanged)** |
| LDS ceiling | 65536 B | 65536 B | none |
| e4m3 MMA codegen | absent | absent | none |
| BF16 MMA control | compiles | compiles | none |
| `cudaMemGetInfo` 4x defect | present | present | none |
| `cuModuleGetFunction` defect | present | present | none |
| **decode** | 69.42 tok/s | **70.69 tok/s** | **+1.83%** better |
| **TTFT** (~2400 tok prompt) | **6.939 s** | 7.246 s | **+4.42%** worse |

Both runtime distributions separate cleanly: 1.7.3's slowest decode (69.76) beats 1.7.1's fastest
(69.60), and 1.7.1's slowest TTFT (6.957 s) beats 1.7.3's fastest (7.232 s). n=40 decode, n=6 TTFT
per version.

## Compile: a tail regression in GEMM kernels, not a uniform slowdown

Median per-file ratio is **1.00x** -- most of the 180 kernels compile in the same time. The 1.90x
total comes from a tail:

```
fp8_gemm_t_blockscaled.cu          2.0s ->   10.0s   5.00x
w4a16_gemm.cu                    173.0s ->  600.0s   3.47x  (timeout; true ~750s)
inferspark_prefill_v47.cu          4.0s ->   13.0s   3.25x
inferspark_prefill_paged_fp8.cu   12.0s ->   36.0s   3.00x
moe_w4a16_grouped_gemm.cu         93.0s ->  203.0s   2.18x
```

Every one is a GEMM or prefill kernel. **That is the same code path the TTFT regression lands on**,
which makes a single cause plausible: something in 1.7.3's GEMM codegen is both slower to produce
and slower to run, while decode-side kernels improved slightly. Stated as a hypothesis, not a
finding -- confirming it needs a look at the generated ISA, which is Spectral's job rather than
mine.

## The finding that matters most for the PRD

**TheTom's own `kernel-census.sh`, at its documented default `--timeout 600`, reports SCALE 1.7.3
as having a compile FAILURE. It does not.** `w4a16_gemm.cu` compiles fine in roughly 750 s -- the
real build produced its `.o` and linked successfully. The census simply gives up at 600.

Anyone running charter (g) as written concludes 1.7.3 broke `w4a16_gemm.cu` and goes hunting a
codegen bug that does not exist. Suggested fix: raise the default, or report timeouts as a
distinct status from compile failures in the summary (the CSV already distinguishes them; the
summary rolls them into "failures: 1 (other 1)").

## Three environment gaps that only appear on a version switch

Charter (g) asks for both versions "in the same container", so anyone following it hits these.

1. **`build-amd.sh` cannot switch SCALE versions.** It clears `target/release/build/avarok-kernels-*`
   and `spark-storage-*`, but the crate that emits the CUDA library search path is
   **`spark-runtime`**, which it does not clear. Its cached output still held
   `rustc-link-search=native=/opt/scale/scale-1.7.1-Linux/targets/gfx1201/lib64` during a 1.7.3
   build. Result is either a silent hybrid (1.7.3 kernels, 1.7.1 libs) or, if the old tree is not
   mounted, `rust-lld: error: unable to find library -lcuda`. Add `spark-runtime-*` to the rm line.
2. **`cudarc` needs the full environment**, not just `SCALE_HOME`: `CUDA_PATH`, `CUDA_HOME` and
   `CUDARC_CUDA_VERSION=12080`, all of which `build-amd.sh` exports internally. Invoking cargo
   directly for an A/B fails with `exit status: 101` and no useful message.
3. **`LD_LIBRARY_PATH` needs four SCALE directories**, not the three previously reported:
   `targets/<arch>/lib` (libredscale), `llvm/lib` (nvcc's toolchain libs), `lib` (libhipblaslt),
   and **`lib/llvm/lib`** (`liblldELF.so.22.0git` and friends, needed by the built binary at
   runtime). Missing the fourth gives 35 unresolved libraries at exec time.

## Method notes, including three of my own errors

**Both binaries were hash-verified distinct before any comparison.** This was not paranoia: after
the first 1.7.3 build failed at link, `target/release/spark` still held the 1.7.1 binary, and I
had already copied it to `spark-scale173` and announced it saved. sha256 showed both files as
`3615339e...`. **An A/B run against that file would have compared 1.7.1 to itself and reported "no
difference between versions"** -- a clean-looking null result that nobody would question. The
check caught the same class of error twice.

**Corrected overstatement.** I first reported this as "1.7.1 built everything in 5m08s while 1.7.3
spent 12m30s on one file", implying a ~180x regression. That compared a 16-worker parallel build
against a single serial compile. Serial to serial, `w4a16_gemm.cu` is 173 s under 1.7.1 -- it was
always by far the slowest kernel in the tree -- and ~750 s under 1.7.3. The real figure is **4.3x**.

**Corrected inference.** I suggested 1.7.3 might ship a newer LLVM, from `nvcc --version`
reporting clang 20.1.8 for 1.7.1. Both versions ship `liblldELF.so.22.0git` at the same path; the
clang frontend and lld are versioned separately. The 3.5 GB vs 13 GB install-size difference
remains unexplained and I am not going to guess at it.

**TTFT first attempt returned HTTP 400** because I built a ~6800-token prompt against a server
started with `--max-seq-len 4096`. The server was right to reject it. Re-run at 1650 words
(~2400 tokens), 6 samples per version.

## Recommendation

Stay on **1.7.1**. 1.7.3 offers +1.8% decode against -4.4% TTFT, doubles census time, trips the
project's own timeout on a kernel that does compile, and leaves both reported defects in place.
Revisit when Spectral ships a fix for scale-validation #67, #68 or #69.

Data: `logs/s5-census/{1.7.1,1.7.3}/`, `logs/s5-probe/{1.7.1,1.7.3}/`,
`logs/s5-runtime/{1.7.1,1.7.3}/`. Binaries `spark-scale171` / `spark-scale173` retained.
