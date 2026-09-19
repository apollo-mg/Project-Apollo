# Result -- Atlas gfx1201 bring-up, S0 (environment) complete

**2026-09-17.** Milestone S0 of Avarok-Cybersecurity/atlas#1126, the RX 9070 XT (gfx1201, 16 GB)
bring-up PRD written by TheTom. Build context: `/mnt/TG_2TB/experiments/atlas-gfx1201/`.

## Gate

The PRD's stated S0 gate is `ls "$SCALE_HOME/targets/gfx1201/bin/nvcc"`. **PASS.**

Verified past the literal gate, since a file existing does not prove a toolchain works:

| check | result |
|---|---|
| glibc inside container | **2.39** (Ubuntu 24.04), below the 2.41 threshold that breaks SCALE |
| GPU visible from inside the container | `AMD Radeon RX 9070 XT - gfx1201`, 15.92 GiB |
| `nvcc --version` | clang 20.1.8 under SCALE's wrapper |
| compile **without** `-U_GNU_SOURCE`, incl. `<vector>`/`<string>` | **rc=0**, warnings only |
| resulting binary runs against the real GPU | yes, `cudaMemGetInfo` returned live values |

The compile test is the one that matters. The container exists to fix the glibc 2.41+ C23 clash
(spectral-compute/scale-validation#69), and the PRD explicitly forbids `-U_GNU_SOURCE`. The test
deliberately includes `<vector>` and `<string>`, which are exactly what that workaround breaks,
so a pass here shows the container **solves** the problem rather than relocating it.

## Two gaps in the PRD, both real

Reported back to TheTom; neither is his fault, since he wrote the plan without this hardware.

1. **The apt dependency list is incomplete.** Every SCALE diagnostic tool fails to start on the
   listed packages alone:
   ```
   scaleinfo:  libelf.so.1, libdrm.so.2, libdrm_amdgpu.so.1   -- all not found
   scalediag:  same three
   hsasysinfo / hsakmtsysinfo: same
   ```
   Fix: add `libelf1t64`, `libdrm2`, `libdrm-amdgpu1`. **Note the `t64` suffix** -- on Ubuntu 24.04
   the package was renamed for the 64-bit `time_t` transition, so the obvious `libelf1` returns
   "Unable to locate package."

2. **`nvcc` needs `LD_LIBRARY_PATH` to include SCALE's bundled LLVM.** It wants `libLLVM.so.20.1`
   and `libclang-cpp.so.20.1`, which ship in `$SCALE_HOME/llvm/lib` rather than coming from the
   distro. This is a path issue, not a missing package, and it is easy to misdiagnose as one.
   Fix: `LD_LIBRARY_PATH=$SCALE_HOME/targets/gfx1201/lib:$SCALE_HOME/llvm/lib`.

## One deliberate deviation

The PRD downloads and extracts SCALE into the image. This build **bind-mounts it read-only from
the host** instead:

- 1.7.1 extracts to 3.5 GB and 1.7.3 to 13 GB; baking both for the S5 comparison would mean a
  ~17 GB image and two more network pulls.
- The host copies have sha256 recorded at fetch time, which is stronger provenance than an
  unpinned `curl` inside a build layer.
- `SCALE_HOME` lands at the same path, so nothing downstream can tell the difference.

Resulting image is 1.14 GB.

## Toolchain provenance

| version | sha256 | fetched |
|---|---|---|
| SCALE 1.7.1 (PRD target) | `060a3627725f60005a69e209b332d7847fd7c03eb9518be7055ddc003c73a2be` | 2026-09-17T22:02:43Z |
| SCALE 1.7.3 (for S5 comparison) | `869afb15e6a947c7966cdf9408633eab6390b21ddae3755538eba3127c6871da` | 2026-09-17T16:00:48Z |

1.7.1 is available version-pinned at `pkgs.scale-lang.com/tar/scale-1.7.1-amd64.tar.xz` (1.33 GB
compressed, against 2.68 GB for the `-latest` tarball now serving 1.7.3).

## Incidental confirmation

Inside the container on **1.7.1**, `cudaMemGetInfo` reported 15.63 GiB free of 15.92 GiB while the
desktop held roughly 2.2 GB. That is the same baseline under-reporting documented on 1.7.3 in
`../scale-gfx1201/RESULT_SCALE_MEMINFO.md`, so it is not new to 1.7.3 and is not an artifact of
the host distro -- it reproduces inside Ubuntu 24.04 as well.

## Run recipe

```
docker run --rm \
  --device /dev/kfd --device /dev/dri \
  --group-add 987 --group-add 983 \          # render, video GIDs on this host
  --security-opt label=disable --ipc=host \
  -v /mnt/TG_2TB/toolchains/scale-1.7.1-Linux:/opt/scale/scale-1.7.1-Linux:ro \
  -v /mnt/TG_2TB/experiments/atlas-gfx1201:/work \
  atlas-gfx1201:s0
```

`--group-add keep-groups` in the PRD is podman syntax; this host runs Docker 29.7.2, which needs
explicit host GIDs. `--security-opt label=disable` is an SELinux flag and is inert on Arch, kept
for parity with the PRD.

## Next

S1: compile census and hardware probes.
