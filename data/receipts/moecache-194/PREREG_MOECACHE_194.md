# Pre-registration: does an adaptive GPU cache for host-offloaded experts (upstream llama.cpp PR #27861) speed up plain decode of Flash-Next UD-IQ4_XS on 4x P100?

**Registered 2026-10-06, before any row.** Mark: "I'd be curious to see if we can get anywhere with pinned
experts" -> "Sure might as well."

**Prior art checked:**
- `strata-194/RESULT_STRATA_194_SPILL.md` (10-06): Strata 37.2 vs buun auto-fit + MTP 20.0 vs buun auto-fit with no
  drafter 16.7, on this file and host.
- The PR's own data: Flash-Next UD-Q4_K_XL on 2x RTX 3090 goes 18.4 -> 24.2 tok/s (+31 %) with 48 slots per layer.
  Static hot lists cover ~10 % (uniform 6.2 %); an LRU-64/128 would hit ~67/81 %.
- **Why not the alternatives:** TheTom's fork has `--moe-cache` but requires compute capability >= 7.0, so it does
  not run on the P100. PR #29887 refuses multiple devices.
- **What this adds:** the cache effect on Pascal, across 4 GPUs, against the same auto-fit baseline.

## Instrument

- **Engine:** upstream llama.cpp PR #27861 head `bccbacdb89`.
  - Built for sm_60 with CUDA 12.4 and gcc-13.
  - Its flags: `--moe-expert-cache N` (slots per host-resident expert layer) and `--moe-expert-cache-inserts`
    (default), as named in `--help`.
- **Weights:** `unsloth/Qwen3.8-Flash-Next-GGUF` UD-IQ4_XS, the same files as the spill test. Gate/up/down are
  separate (IQ3_S / IQ3_S / IQ4_NL), as the PR requires.
- **Placement, both arms identical:** `-sm layer -fa on -fit on -fitt 3072 -c 8192 -np 1`, f16 KV, `--reasoning off`.
  - The 3 GB margin leaves room for the cache tensors.
  - **No MTP:** the PR's cache is single-token decode only.
- **Measurement:** `lmx` v0.1.48 remote via `run194.sh`.
  - Canonical reasoning-v1; temperature 0; 256 tokens; 1 warmup + 3 timed; median; proxy capture; clocks.
  - The cache's hit statistics are taken from the server log, if it logs them.

## Arms

| arm | cache | starts |
|---|---|---|
| **X0** | off | 2 |
| **X1** | `--moe-expert-cache 128` | 2 |

## Predictions

| # | claim | confidence |
|---|---|---|
| C1 | X1 decodes at least 1.15x X0 (median of starts) | 0.55 |
| C2 | X0 lands within 15 % of buun's auto-fit no-drafter 16.7 tok/s (a sanity link to the spill test) | 0.6 |

## Not tested

- MTP with the cache (unsupported by the PR).
- Other slot counts, beyond one fallback recorded as a deviation if 128 does not fit.
- Quality: the PR states the split is exact by construction; not re-verified here.

## Deviations

Any change after the first row gets a numbered Deviation here before the affected rows run.
