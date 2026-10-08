# Result -- `-ub` on the .73 daily driver: 2048 costs +2,168 MiB per card and fails every real request (MTP draft context out of VRAM on GPU 0, HTTP 500); 1024 costs +698 MiB per card and buys 1.14-1.16x prefill, but VBR drops to ~4.75 bits/value at 32k (from ~15.5) and the 128k request fails at 102k tokens. Keep the default 512

**2026-10-08.** Pre-registration `PREREG_UB_DAILY_73.md` (`86d4d3fd`), no deviations.
- **Runner:** `run_wrap.sh` -> `run_ub.sh` -> `launch73_ub.sh` (on .73) + `ubbench.py`.
- **Raw:** `raw/U*.jsonl`, one record per request with timings, collapse stats, text and per-GPU `memory.used`.
  `raw/logs/` holds the server logs, commands, pre-leg clocks, and 2 s power/clock/memory logs.
- **Node state:** the wake proxy was down from 14:58 to 15:55:56. A completion through `:8099` at 15:58 returned "OK"
  from a cold start in 46 s.

## Validity

| check | result |
|---|---|
| **V1** replication | **pass**: U512's five completions are byte-identical to `kmic-p100-73` D1's (draft counts identical too), so the control is the daily config and nothing drifted between 13:17 and 14:58 |
| **V2** no collapse | **pass**: longest run 2-16 characters, 59-72 distinct characters, on every completion that returned text |
| **V3** clocks | **pass**: 150 W and 1,328 MHz application clocks on both GPUs before each leg |
| **V4** survived | **pass**: all three servers alive at the end with no abort/assert line. The failures below are per-request errors the server recovered from. |

## VRAM

Per-GPU `memory.used` (MiB) after `/health` is ok, before any request; cards are 16,384 MiB:

| cell | GPU 0 | GPU 1 | sum | vs U512 | GPU 0 free | peak GPU 0 during the leg |
|---|---|---|---|---|---|---|
| U512 | 13,689 | 12,553 | 26,242 | -- | 2,695 | 15,817 (at 128k) |
| U1024 | 14,387 | 13,251 | 27,638 | **+1,396** (+698 per card) | 1,997 | 16,267 (at the failure) |
| U2048 | 15,857 | 14,721 | 30,578 | **+4,336** (+2,168 per card) | **527** | 16,151 |

- **The increase is the same on both cards** (tensor split shares the compute buffer). It grows slightly faster than linearly
  in ubatch: about 1.36 MiB per ubatch token per card from 512 to 1024, and 1.44 from 1024 to 2048.
- **GPU 0 always carries 1,136 MiB more than GPU 1**, identical in every cell. GPU 0 is therefore the card that runs
  out, and both failures below are on device 0.

## Speed and KV precision

| depth | | U512 | U1024 | U1024/U512 |
|---|---|---|---|---|
| 2k (seeds 1-2) | prefill t/s | 177.3 | 205.9 | **1.16x** |
| | decode t/s | 26.6 | 23.6 | 0.89x |
| | `kv_bpv` | 16.0 | 16.0 | |
| 32k (seeds 1-2) | prefill t/s | 158.8 | 180.3 | **1.14x** |
| | decode t/s | 21.7 | 18.3 | 0.84x |
| | `kv_bpv` | 15.75 / 15.26 | **5.15 / 4.34** | |
| 128k (seed 1) | prefill t/s | 98.3 (complete) | **failed at 102,400 tokens** (116.6 t/s average to that point) | -- |
| | decode t/s | 11.24 | -- | |

- **U2048 has no speed rows.** The 5-token warmup worked; all five real requests returned HTTP 500 within ~10 s.
- **The 2k decode drop is a text effect, not a mechanism.**
  - At equal `kv_bpv` (16.0), U1024's seeded text diverges from U512's after 14-434 characters. A different ubatch
    changes the prefill numerics.
  - U1024's MTP acceptance is 0.659 / 0.648 against 0.674 / 0.834.
- **At 32k the decode drop has a plausible cause, not verified:** U1024's KV sits near the floor (4.3-5.2 bits/value),
  and degraded tiers are materialized to f16 at attention time on Pascal.

## The two failure modes (server logs)

- **U2048, every request.**
  - The MTP draft context cannot allocate its compute pool: `ggml_backend_cuda_graph_compute: CUDA pool allocation
    failed (out of VRAM)`.
  - That surfaces as `llama_decode(ctx_dft) head=0 failed rc=-2`, then `decode() failed: failed to process
    speculative batch`, then HTTP 500.
  - GPU 0 had 527 MiB free after load.
- **U1024, at 102,400 tokens of the 128k prefill.**
  - `vbr_scratch_reserve: f16 dequant scratch reserve of 136.0 + 136.0 MiB failed on device 0`, then `prepare_with_slots:
    f16 dequant scratch reserve failed (device memory exhausted)`.
  - The server retries with smaller batches (1024, then 512) that fail the same way, then returns HTTP 500 after
    896 s.
- **Why the auto budget does not prevent either.**
  - Every cell logs the same `VBR budget 9088.00 MiB exceeded ... clamped at the --vbr-floor` warning. 9,088 MiB is
    the live-free snapshot taken when the KV cache is constructed, before the compute buffers allocate (the source
    comment at `llama-kv-cache.cpp` ~1855 says that number "over-states reach").
  - Two consumers draw outside the KV budget, and both are what failed:
    - the drafter's compute pool;
    - the f16 dequant scratch (`fit.cpp` ~1100, "lives OUTSIDE the KV budget").
  - The live clamp keeps KV *mapping* inside free memory, but it cannot shrink those two. A larger ubatch therefore
    turns into a hard failure, not a quality degrade.
  - The warning also prints the stale 9,088 rather than the effective budget. In U2048 it reads "exceeded ...
    (projected 148.00 MiB at 4096 cells)".

## Registered verdicts

| # | claim | conf. | result |
|---|---|---|---|
| P1 | all three cells load at 262k and complete the 128k request | 0.65 | **fails**: all load, but U2048 serves no request and U1024 fails at 102k |
| P2 | U2048 uses +1.0 to +5.0 GiB post-load, summed | 0.6 | **holds: +4.23 GiB** (+4,336 MiB) |
| P3 | U2048 prefill >= 1.15x at 2k and 32k | 0.65 | **not measurable** (U2048 served nothing). Unregistered: U1024 reached 1.16x / 1.14x |
| P4 | U2048 prefill >= 1.10x at 128k | 0.55 | **not measurable**. U1024 failed at 102k |
| P5 | U2048 `kv_bpv` at 32k <= U512 | 0.5 | **not measurable**. Unregistered: U1024 4.75 vs 15.51, far below |
| P6 | U2048 decode within +/-5 % | 0.6 | **not measurable**. Unregistered: U1024 decode 0.87x over 2k/32k, partly text divergence |

## What it means

- **Keep the daily driver at the default `-ub 512`.** The 262k + MTP + vision + `-np 2` config has 2.7 GB free on
  GPU 0 after load, and 0.57 GB at a 128k fill.
  - **2048 does not fit at all.**
  - **1024 fits only to roughly 100k tokens.** Even below that, it buys its 14-16 % prefill by pushing the KV cache
    from ~15.5 to ~4.75 bits/value at 32k: a quality cost on every long conversation.
- **The prefill gap to Kaden's fork is not recoverable by flags on this config.** His `-ub 2048` works because his KV
  is a fixed q4_0 cache at `-np 1`. Here, the VBR budget, the MTP drafter and the dequant scratch all compete for the
  same last 2.7 GB on GPU 0.
- **Untested levers if prefill matters:**
  - `-ts` to move weight off GPU 0, which always has 1.1 GB less free than GPU 1 (per `buun-issue134`, `-ts` sized to
    the *free* VRAM moved the VBR clamp 20x);
  - `-np 1`;
  - a smaller `-c`.
- **Prior art:** this confirms `qwen4exp/split-conc/RESULT_RECIPE.md` (Flash-Next, 4x P100) on a second architecture
  (dense 27B, 2 cards): under tensor split + MTP, the drafter's compute buffer is what fails first as ubatch grows. It
  adds a second failure mode at depth (the f16 dequant scratch) and the per-card VRAM cost per ubatch step.
- **A buun report candidate:** with auto `--vbr-vram`, out-of-VRAM in the drafter's pool or the dequant scratch
  surfaces as HTTP 500, not a degrade. The budget warning prints the stale init snapshot (9,088 MiB) rather than the
  effective budget.
