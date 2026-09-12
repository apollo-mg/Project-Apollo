# Result — buun's Pascal restore qualifies on real P100 silicon, once a CUDA-12.8 dependency is guarded

**2026-09-12, `.73`** — 2× Tesla P100-PCIE-16GB (sm_60), driver 580.178.04, **CUDA 12.4**, gcc 15.2.0.
Requested by buun: *"merged SM60 support. maybe you wanna give an EXL3 safetensors a try? I don't
have pascal to test with"*, and in the commit itself: *"Runtime fallback and cache checks passed on
an RTX 3090; **actual Pascal hardware qualification remains pending.**"*

**Tree:** clean worktree at `origin/master` = `9ae8f0f40`, containing `4d90517b1` *"cuda: restore
Pascal builds for native quantization"*. Verified 0 modified tracked files before patching, so our
superseded `LOCAL_PATCH_sm60_guards.diff` could not contaminate the result.

## Headline

| step | outcome |
|---|---|
| build `ggml-cuda` for sm_60, unpatched | **FAILS** — but on a CUDA-version dependency, not a Pascal one (see `NOTE_HUMMING_FP8_NEEDS_CUDA_128.md`) |
| build with the 2-line `CUDART_VERSION >= 12080` guard | **`test-exl3-byte-dot` rc=0 (31 min), `llama-server` rc=0 (1 min)** |
| run `test-exl3-byte-dot` **on P100 hardware** | **PASS** |

```
PASS: all 65536 codebook products, unsigned byte sums, mixed byte dots and wrapping accumulation
=== EXIT CODE: 0 ===
```

**The exit code was checked explicitly against 77.** `tests/CMakeLists.txt` sets
`SKIP_RETURN_CODE 77` on this test, so a skipped test would otherwise be indistinguishable from a
pass in any `&&`-chained script. It returned **0**, and it printed a positive assertion naming what
it verified — both GPUs were idle at 0 MiB when it ran.

**So buun's scalar sm_60 fallbacks for EXL3 byte-dot are numerically correct on real Pascal.** That
is the specific thing `4d90517b1` could not self-certify, and it now has an answer.

## What is NOT qualified

- **No EXL3 model has been run.** This is a kernel-level unit test, not inference. Nothing here says
  an EXL3 safetensors model loads, generates, or is fast on sm_60. That is the next tier and needs a
  model we do not yet hold.
- **`llama-server` was built, not exercised.** rc=0 on the link is not a running server.
- **One toolkit, one driver, one box.** CUDA 12.4 + gcc 15.2.0 is an unusual pairing and differs from
  buun's 12.8 environment in more ways than the one we isolated.
- **Built with a declared local patch** (`PATCH_e8m0_cuda128_guard.diff`). The guard removes a
  template specialisation that neither humming translation unit references; it changes nothing they
  compile. But the tree is not byte-identical to upstream and the result must be read that way.

## Build environment hazard worth recording

**`.73` was suspended mid-build by our own wake proxy.** Its 30-minute idle timer counts only API
requests, so it cannot see a compile, or any other work, running on the node:

```
2026-09-12T12:39:17  wake_proxy: idle 1858s >= 1800s — suspending     (control plane)
Sep 12 12:39:28      kernel: PM: suspend entry (deep)                 (.73, 11 s later)
Sep 12 12:51:58      kernel: waking up from S3                        (magic packet from the control plane)
```

**All five of `.73`'s suspends on 2026-09-12 follow a proxy `suspending` line by ~11 s** (00:38, 01:38,
02:37, 04:38, 12:39); there is no suspend the proxy did not initiate. **The first version of this
receipt blamed KDE input-idle. That was an unverified guess, and wrong.**

The build **survived intact** (S3 preserves process state) and completed normally, but:

- **The "31 min" above is wall-clock and includes ~12.5 minutes of suspend**; active compile time was
  about 18.5 minutes. The first version said it *excluded* the suspend, which was also wrong.
- The node's `llama-server` did not come back because the proxy deliberately stops it before
  suspending (a VRAM spill would not fit in `/var`). That is designed behaviour, not a fault, and it
  is why the GPUs were free for the test.
- `systemd-inhibit` over non-interactive ssh is refused by polkit, but that is beside the point: the
  suspend is requested by the proxy. **The fix belongs in `modules/wake_proxy.py`** — for example,
  skip the idle suspend while a non-proxy GPU or build process is running, or while an inhibit file
  exists. Not changed here: it is a live service and Mark's call.
- The workaround used, a WoL watchdog on the control plane, worked — by waking the node back up after
  our own proxy had put it to sleep.

## Reproduction

`sm60_qual.sh` (build, in a fresh worktree), `patch_e8m0.py` (the guard, refuses to patch a block
that does not contain `e8m0`), `PATCH_e8m0_cuda128_guard.diff` (the resulting 2-line diff) are all
committed alongside this receipt.

Build flags: `-DGGML_CUDA=ON -DCMAKE_CUDA_COMPILER=/usr/bin/nvcc -DGGML_CUDA_FA=ON
-DGGML_CUDA_FA_ALL_QUANTS=OFF -DCMAKE_CUDA_ARCHITECTURES=60 -DCMAKE_BUILD_TYPE=Release
-DLLAMA_BUILD_TESTS=ON`, built `nice -n 15 -j4` to protect a 15 GB box running a desktop session.
