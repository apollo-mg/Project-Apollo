# Spectral issue 3 of 3 -- ready to paste

**Tracker:** https://github.com/spectral-compute/scale-validation/issues
**Attach:** nothing required; the error text below is self-contained. `scale_bugreport.txt` optional.

This one is the highest-impact of the three for new users: it is not a degraded path, nothing
compiles at all.

---

**Title:** `SCALE 1.7.3 fails to compile any source against glibc 2.41+ (rsqrt/cospi collide with C23 math declarations)`

---

OS: CachyOS (Arch), kernel 7.2.3-1-cachyos, **glibc 2.44**, gcc 16.2.1
SCALE Version: 1.7.3 (tarball)
GPU: AMD Radeon RX 9070 XT, gfx1201 (not relevant -- this is a host compile failure)
Description: Every compilation fails on a distro shipping a C23-era glibc. SCALE's force-included `redscale_impl/builtins.h` declares `__host__ __device__ double rsqrt(double)` and friends, which collide with the C23 math functions glibc now exposes. This is invisible on SCALE's supported distros because they all ship older glibc, but it blocks Arch and derivatives, Fedora Rawhide, and eventually Ubuntu entirely.
Steps to Reproduce:
1. On a system with glibc 2.41 or newer, write any trivial CUDA file that includes a C++ standard header, e.g. `#include <cstdio>` plus `#include <cuda_runtime.h>` and an empty `main`.
2. `nvcc -o test test.cu`
3. Compilation fails before reaching any user code.

---

## Error

```
In file included from <built-in>:1:
In file included from .../redscale_impl/common.h:42:
In file included from .../redscale_impl/builtins.h:705:
In file included from /usr/include/c++/16/cmath:55:
In file included from /usr/include/math.h:450:
/usr/include/bits/mathcalls.h:207:17: error: __host__ function 'rsqrt' cannot overload
    __host__ __device__ function 'rsqrt'
  207 | __MATHCALL_VEC (rsqrt,, (_Mdouble_ __x));
      |                 ^
.../redscale_impl/builtins.h:667:26: note: previous declaration is here
  667 | __host__ __DEVICE double rsqrt(double);
      |                          ^
```

`cospi` produces the same class of error, and `rootn` and `powr` are declared in the same glibc
block.

## Cause

glibc exposes `rsqrt`, `cospi`, `rootn` and `powr` when `__GLIBC_USE (IEC_60559_FUNCS_EXT_C23)` is
set. From `bits/libc-header-start.h`:

```c
#undef __GLIBC_USE_IEC_60559_FUNCS_EXT
#if defined __USE_GNU || defined __STDC_WANT_IEC_60559_FUNCS_EXT__
# define __GLIBC_USE_IEC_60559_FUNCS_EXT 1
...
#if __GLIBC_USE (IEC_60559_FUNCS_EXT) || __GLIBC_USE (ISOC23)
# define __GLIBC_USE_IEC_60559_FUNCS_EXT_C23 1
```

`__USE_GNU` comes from `_GNU_SOURCE`, which clang defines automatically for C++ on Linux. So the
block is always active, and SCALE's declarations of the same names as `__host__ __device__` cannot
overload the host-only ones glibc declares.

Confirmed this is glibc and not the compiler version: building with `-ccbin g++-15` does not help,
because the declarations live in `/usr/include/bits/mathcalls.h`, which is shared across GCC
versions. The macros are `#undef`'d and recomputed inside `libc-header-start.h`, so predefining
them on the command line has no effect either.

## Workaround, and why it is not a general answer

`-U_GNU_SOURCE` compiles. It then breaks libstdc++ headers that need `_GNU_SOURCE` for wide-char
support, so `<vector>` and `<string>` fail via `<cwchar>`:

```
/usr/include/c++/16/cwchar:150:11: error: no member named 'fwide' in the global namespace
/usr/include/c++/16/cwchar:151:11: error: no member named 'fwprintf' in the global namespace
```

That is workable for a small C-style reproducer, which is how the probes in my other two tickets
are written, but real code cannot give up the C++ standard library.

## Scope

Invisible on the platforms listed in the install docs (Ubuntu 22.04/24.04, Rocky/RHEL 8/9), all of
which ship older glibc. Anyone on Arch, CachyOS, Fedora Rawhide or a future Ubuntu hits a wall on
their first compile with no obvious path forward, since the error points at glibc's headers rather
than at anything SCALE-shaped.
