Hit a configure-time break building master (`38ada0e1b`) for gfx1201 with ROCm 7.x. It is a
one-line scope issue rather than anything deep, and it only bites HIP -- the CUDA path is immune
for a reason that is worth spelling out.

**Symptom.** `cmake --build` fails before compiling anything:

```
CMake Error in tests/CMakeLists.txt:
  HIP_ARCHITECTURES is empty for target "test-exl3-byte-dot".

-- Generating done (0.5s)
CMake Generate step failed.  Build files cannot be regenerated correctly.
```

**Cause.** `ggml/src/ggml-hip/CMakeLists.txt:38-40` forwards the targets:

```cmake
if(GPU_TARGETS AND NOT CMAKE_HIP_ARCHITECTURES)
    set(CMAKE_HIP_ARCHITECTURES ${GPU_TARGETS})
endif()
```

A bare `set()` is **directory-scoped**. The top-level `CMakeLists.txt` adds `ggml` at line 231 and
`tests` at line 253 -- siblings, not nested -- so `CMAKE_HIP_ARCHITECTURES` never reaches
`tests/`. `tests/CMakeLists.txt:628` then calls `enable_language(HIP)` in a scope where it is
empty, and `test-exl3-byte-dot` ends up with no architectures.

**Why CUDA does not hit this.** The CUDA siblings a few lines below read a **target** property,
which is global rather than directory-scoped:

```cmake
get_target_property(EXL3_CUDA_ARCHITECTURES ggml-cuda CUDA_ARCHITECTURES)
set_target_properties(${exl3_test} PROPERTIES
    CUDA_STANDARD 17 CUDA_ARCHITECTURES "${EXL3_CUDA_ARCHITECTURES}")
```

The HIP branch at `tests/CMakeLists.txt:636-642` sets `HIP_STANDARD 17` but never the matching
`HIP_ARCHITECTURES`.

**What does and does not work around it.** Measured, not assumed:

| configure | result |
|---|---|
| `-DAMDGPU_TARGETS=gfx1201` (what my cache had) | **fails** |
| `-DGPU_TARGETS=gfx1201` | **fails** |
| `-DCMAKE_HIP_ARCHITECTURES=gfx1201` | **configures and builds** |

So passing the documented `GPU_TARGETS` is not enough, which is the part most likely to cost
someone else an hour. ROCm 7.x also now warns that `AMDGPU_TARGETS` is deprecated in favour of
`GPU_TARGETS`, so anyone with an older cache lands here.

**Suggested fix**, mirroring what the CUDA branch already does:

```cmake
if (TARGET ggml-hip)
    get_target_property(EXL3_HIP_ARCHITECTURES ggml-hip HIP_ARCHITECTURES)
    set_target_properties(test-exl3-byte-dot PROPERTIES
        HIP_ARCHITECTURES "${EXL3_HIP_ARCHITECTURES}")
endif()
```

Making the forward in `ggml-hip/CMakeLists.txt` a `CACHE STRING ... FORCE` would also do it, but
the target-property version matches the CUDA path and does not leak a cache entry.

Environment: Arch, ROCm 7.x, RX 9070 XT (gfx1201), CMake generating fine at `3823c9eb6` before
this. Happy to test a patch -- this card is sitting right here.
