# Result -- upstream llama.cpp PR #27861's GPU LRU cache for host-offloaded experts works on 4x P100 and speeds up plain (no-MTP) decode of Flash-Next UD-IQ4_XS by 1.17x (14.2 -> 16.6 tok/s); far short of Strata (37.2 with MTP) because it caches only 9 host layers on one card and bypasses the cache whenever MTP verifies a batch

**2026-10-06.** Pre-registration `PREREG_MOECACHE_194.md` (`6aa25b73`), no deviations.
- **Chain:** `moecache_chain.sh` (arms interleaved X0, X1, X0, X1).
- **Raw:** `raw/` (LMX JSON, proxy captures, server logs, clocks, build log).

## Setup

- **Engine:** upstream llama.cpp PR #27861 head `bccbacdb8` (base `4e97ac86eb`, 2026-08-28), built for sm_60 with
  CUDA 12.4 / gcc-13.
- **Weights:** Unsloth Flash-Next UD-IQ4_XS (the spill test's files). Gate/up IQ3_S and down IQ4_NL are separate, as
  the PR requires.
- **Placement, both arms:** `-sm layer -fa on -fit on -fitt 3072 -c 8192 -np 1`, f16 KV, `--reasoning off`, no MTP.
- **Host:** .194, SM clock 1,063 MHz busy in every arm.
- **Measurement:** `lmx` v0.1.48 remote, reasoning-v1, temperature 0, 256 tokens, 1 warmup + 3 timed, median. Every
  arm passed the content gate.

## Results

| arm | tok/s (median) | samples | TTFT ms | VRAM per GPU (MiB) |
|---|---:|---|---:|---|
| X0 start 1 (no cache) | 13.9 | 14, 13.9, 13.9 | 5,220 | 13,087 / 13,179 / 13,165 / 12,889 |
| **X1 start 1** (`--moe-expert-cache 128`) | **16.5** | 16.6, 16.5, 16.2 | 5,236 | 13,087 / 13,179 / 13,165 / **15,671** |
| X0 start 2 | 14.4 | 14.6, 14.3, 14.4 | 5,064 | as X0 |
| **X1 start 2** | **16.7** | 16.8, 16.7, 16.5 | 5,083 | as X1 |

- **The server's report:** "MoE expert cache enabled: 9 layers x 128 slots, 2 inserts/step, 2780.9 MiB device
  memory". The automatic fit left 9 expert layers in host memory, and their cache all went on GPU 3, the card that
  holds those layers' routers.
- **No hit rate is logged** by this PR build.

## Registered verdicts

| # | claim | result |
|---|---|---|
| C1 | X1 at least 1.15x X0 | **holds, narrowly:** 16.6 / 14.15 = **1.17x** |
| C2 | X0 within 15 % of buun's auto-fit no-drafter 16.7 | **does not hold, by a hair:** 14.15 is 15.3 % below. Likely causes: the larger `-fitt 3072` margin (more layers left in host memory) and the PR's August base. Neither is isolated. |

## What it means

- **An adaptive expert cache does help upstream llama.cpp on Pascal** (+17 %), with no new kernels. That is in line
  with the PR's own +31 % on 2x RTX 3090.
- **Against Strata (37.2 tok/s on the same file and host) it is a small step.** Measured differences:
  - Strata caches experts on every card (17,473 slots), where this cache sat on one card (9 layers x 128).
  - Strata keeps MTP working through the cache (~3.3 tokens per pass). This PR's cache is single-token only
    (`n_tokens == 1`), so turning MTP on bypasses it. Not run, per the PR's design.
- **Upstream is two PRs away from Strata-class behaviour on multi-GPU Pascal:**
  - the cache on every device;
  - small-batch (MTP verify) support.
  - TheTom's fork has a more complete cache (heat-protected eviction, calibration, speculative batches), but it
    requires compute capability 7.0+, so it is out of reach for the P100s as it stands.
- **On "pinned experts":** this PR's routing study on Flash-Next found little static skew (a held-out top-32 hot
  list covers ~10 % against 6.2 % uniform). A fixed pin set is unlikely to do what the adaptive cache does; nothing
  here contradicts that.

## Not established

- Larger slot counts or more inserts per step.
- The PR on a newer base.
- MTP (unsupported by the cache).
- Cache hit rate (not logged).
- Single-GPU #29887.
- Pascal support for TheTom's cache.
