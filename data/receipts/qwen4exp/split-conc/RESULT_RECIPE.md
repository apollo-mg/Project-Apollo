# Result -- today's Flash-Next wins do not all stack in one server on 4x P100: MTP's drafter under tensor split cannot fit its compute buffer on GPU 0 at any ubatch above 512. Without MTP the multi-user recipe works: tensor split + `-ub 4096` + `--kv-unified` + `-np 4` gives 430 tok/s prefill at 8k and 48.9 tok/s at 4 streams, every pass stable.

**2026-10-02.** Pre-registration `PREREG_RECIPE.md` (`0a6a936b`), with Deviation 1: the exploratory R1b/R1c,
registered after R1 failed and before they ran (`c6e09a09`). Runner `run_recipe.sh`, probes `pf_probe.py` +
`conc_probe.py`, analysis `analyze_recipe.py` (self-tested), output `RESULT_recipe.json`.

- **Raw:** `raw_recipe/` (rows, server logs).
- **Setup:** .194, 4x P100 at 150 W / 1063 MHz, buun `0b2789f23`, Flash-Next UD-Q2_K_XL fully resident, f16 KV,
  C0 binding, file pages interleaved.

## Servers

| server | config | result |
|---|---|---|
| **R1** | tensor `-ts 1,1,1,0.75` + MTP (draft 3), `-ub 4096`, `-np 2`, `--kv-unified` | **OOM at load:** 4,085 MiB on GPU 0 |
| R1b (exploratory) | as R1, `-ub 2048` | **OOM at load:** 2,042 MiB on GPU 1 |
| R1c (exploratory) | as R1, `-ub 1024` | **drafter context fails:** needs ~1.0 GB of compute buffer on GPU 0, 719 MB free |
| **R2** | tensor, no MTP, `-ub 4096`, `-np 4`, `--kv-unified` | **works** |

**R2:**
- **Prefill:** 411 tok/s at 2k, **430 at 8k**.
- **Decode:**

  | streams | total tok/s | per stream |
  |---:|---:|---:|
  | 1 | 14.1-14.4 | |
  | 2 | **28.5-28.7** | 15.4 |
  | 4 | **47.6-49.6** | |

- **Zero failures.** 2-stream passes are within 1 % of each other, 4-stream within 4 %.
- **With `--kv-unified`, each slot's context is the whole pool:** `n_ctx_slot = 16384`, not 4096.

## Registered verdicts

| # | claim | result |
|---|---|---|
| Q1 | R1 fits and keeps most of the prefill | **does not hold.** R1 does not load |
| Q2 | R1 keeps MTP's single-stream decode | **not testable** (scored as not holding) |
| Q3 | R2 keeps multi-stream throughput (>= 46 total, >= 13 per stream at 2) | **holds.** 48.9 and 15.4 |
| Q4 | no slot bistability with `--kv-unified` | **holds for R2** (28.46-28.73). Not testable for R1, so it does not hold as registered |

## What it means

- **On 4x P100, pick one Flash-Next server per job:**

  | for | config | prefill (8k) | decode |
  |---|---|---:|---|
  | one user, decode-heavy | tensor + MTP, default `-ub` 512 (10-01 T3) | ~287 tok/s | 27.4 tok/s |
  | prefill-heavy or several users | tensor, `-ub 4096`, `--kv-unified`, `-np 4` (R2) | 430 tok/s | 14.3 single, 48.9 at 4 streams |

- **Why MTP and a wide ubatch collide:** the drafter's compute buffer lands on GPU 0 and scales with the ubatch, and
  GPU 0 is already full under tensor split. This is the `drafter-gates-kv-budget` pattern again.
  - Not tested: shifting weight off GPU 0 (e.g. `-ts 0.8,1,1,0.75`) to make room. That is the obvious next try if a
    combined server is wanted.
- **`--kv-unified` costs nothing measurable under tensor split** (R2 2-stream 15.4 per stream against 10-01's 14.5
  without it), and it gives each slot the full context.

## Not established

- MTP with an evened `-ts` at ub 1024-2048.
- Whether 10-01's caveat that tensor split disables prompt-cache reuse still holds on this build (INDEX L36 says buun
  fixed it).
- Contexts above 8k.
