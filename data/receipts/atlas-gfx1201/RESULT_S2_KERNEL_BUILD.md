# Result -- Atlas gfx1201 bring-up, S2 (kernel build) complete

**2026-09-17.** Milestone S2 of Avarok-Cybersecurity/atlas#1126, run in the S0 container against
`TheTom/atlas` `amd/r9700-target` @ `68b26331`.

## Acceptance met

The PRD requires all 176 kernels to compile without errors. They did, and the count matches
the r9700 baseline exactly:

```
avarok-kernels: 176 kernels (r9700, ornith-1.0-9b, nvfp4), 12 model-dir kernels, 0 declared overrides
avarok-kernels: dedup+parallel: 176/176 unique nvcc invocations (0 cache hits, 1.0x dedup), 16 parallel workers
Finished `release` profile [optimized] target(s) in 5m 08s
BUILD_RC=0
```

| item | result |
|---|---|
| kernels compiled | **176 of 176** (PRD baseline: 176) |
| declared overrides | 0 |
| build time | 5m 08s (PRD estimate: ~3 min; this included a cold Rust compile) |
| artifact | `target/release/spark`, 54.6 MB, ELF x86-64 PIE |
| `spark --version` | `spark 1.0.0-beta-preview` |
| missing shared libs at runtime | 0 |

Note the binary is named **`spark`**, not `spark-server`: the crate is `spark-server` but declares
`[[bin]] name = "spark"`. Looking for the crate name finds nothing and reads like a failed build.

The Ornith target carries no `nvfp4/` kernel directory of its own under `r9700` -- only a
`MODEL.toml`, which declares `kernel_source = "qwen3.6-27b"` and redirects to that tree. This is
deliberate (gb10's copy has no such key; it was added for r9700) and is **not** a missing
directory, though it looks exactly like one on first inspection.

## Three more gaps in the PRD, all found by running it

Numbered continuing from the two in `RESULT_S0_ENVIRONMENT.md`.

**3. No Rust toolchain anywhere in the PRD.** `build-amd.sh` line 74 runs
`cargo build --release -p spark-server`, and `rust-toolchain.toml` pins channel **1.93.1** with
`rustfmt` and `clippy`. Ubuntu 24.04's packaged rustc is far older, so apt cannot satisfy it;
rustup is required. **This blocks S2 completely** for anyone following the document literally --
the single highest-impact correction of the set.

**4. `libibverbs-dev` is missing.** `crates/avarok-rdma`'s build script compiles
`src/rdma_shim.c`, which includes `<infiniband/verbs.h>`. Without it the build dies in about 15
seconds:
```
error: failed to run custom build command for `avarok-rdma v1.0.0-beta-preview`
  src/rdma_shim.c:20:10: fatal error: infiniband/verbs.h: No such file or directory
```
The crate honours an `AVAROK_NO_RDMA` escape hatch, but installing the headers keeps the build
identical to the r9700 reference rather than compiling a different feature set. A scan of every
C/C++ shim in `crates/` shows this is the **only** non-trivial system header the tree needs, so
one package closes the whole class.

**5. The PRD assumes podman; on Docker it leaves root-owned artifacts.**
`--group-add keep-groups` is podman-only syntax, and rootless podman maps container writes to the
host user automatically. Docker does not: everything the container writes into the bind mount
(`logs/`, `target/`) lands owned by root and is then unwritable from the host. Symptoms are
confusing -- a later `docker build` fails with `checking context: no permission to read from
.cargo-registry/...` rather than anything that names the cause. Either run with explicit
`--user`, or `chown` inside the container at the end of each run, which is what this build does.

## Revision to gap 2

`RESULT_S0_ENVIRONMENT.md` reported that `LD_LIBRARY_PATH` needs `$SCALE_HOME/llvm/lib` for
nvcc. That was incomplete. **Three** SCALE library directories are needed, for different
consumers and at different times:

| directory | provides | needed by |
|---|---|---|
| `targets/gfx1201/lib` | `libredscale.so` | the per-arch runtime |
| `llvm/lib` | `libLLVM.so.20.1`, `libclang-cpp.so.20.1` | `nvcc` at compile time |
| `lib` | `libhipblaslt.so.1` | the built `spark` binary **at run time** |

The third only surfaces when the server is first executed, long after a clean build, which is the
worst moment to discover it. All three are bundled by SCALE rather than supplied by the distro,
so all three are path problems rather than missing packages -- the reason they are easy to
misdiagnose as apt gaps.

## Environment as built

Image `atlas-gfx1201:s0`, 2.02 GB: Ubuntu 24.04 (glibc 2.39), the PRD's apt list plus
`libelf1t64 libdrm2 libdrm-amdgpu1 libibverbs-dev`, rustup with pinned 1.93.1, SCALE 1.7.1
bind-mounted read-only from the host. Cargo registry cached at `.cargo-registry/` on the host so
rebuilds do not re-download.

## Next

S3: serve Ornith-1.0-9B NVFP4 within the 16 GB budget. Expect the `cudaMemGetInfo` defect to
matter here -- `HARDWARE.toml` already documents `AVAROK_MEMINFO_SOURCE` and the sysfs path as
required on this target, and the measured 4.00x over-charge caps honest capacity reporting at
roughly 3.9 GiB on a 16 GB board.
