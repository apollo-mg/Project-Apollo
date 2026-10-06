# Result -- Strata decodes Flash-Next Coder at 52.6 tok/s (code) and 65.5 (reasoning) on a 16 GB RX 9070 XT with 31 GB of RAM, 2.57x llama.cpp's static offload (20.5). Its adaptive expert cache serves 83 % of routed-expert lookups from the GPU with ~40 % of the experts resident, against static -ncmoe's fixed 42 %, and it verifies 4-token MTP windows at ~19 passes/s where a 4-token pass costs llama.cpp here >=10x a single token

**2026-10-05.** Pre-registration `PREREG_STRATA_9070.md` (`544e3106`), with an OOM incident, Deviations 1-2 and a
wording clarification recorded there before their rows.
- **Runners:** `run_strata.sh`, `run_llama.sh`, `chain1.sh`, `chain2.sh`.
- **Raw:** `runs/` (LMX JSON, proxy captures, server logs), with the summary in `RESULT_strata.json`.

## Setup

- **Strata** v0.1.39 (`6f32ec0`), built here for gfx1201 against ROCm 7.2.
  - The installer's config for 31 GB: Coder IQ1_M pack, low-RAM mode, `--spec 4 --spec-min-p 0.5` with its own MTP
    draft layer, int8 KV, 65,536 max context.
  - Load takes 22-28 s. Loaded: ~23-24 GB RAM used (7 GB available), 16.97 GB VRAM. The expert cache holds about
    4,600-5,200 experts.
- **llama.cpp** upstream b11433 (`50569eb87`) on the same two GGUF shards: `-ngl 99 -fa on -c 8192 -ncmoe 28`
  (26 did not fit), f16 KV, `--reasoning off`, 16.75 GB VRAM.
- **Measurement:** LocalMaxxing's `lmx` v0.1.48, remote mode.
  - Canonical prompts code-v1 / reasoning-v1; temperature 0, 256 tokens, 1 warmup + 3 timed, median.
  - Evidence captured by the proxy.
  - Strata ran with thinking off through its shared setting `reasoning_effort: none`. The gate passed: every timed
    request returned answer text in `content`.

## Results

| arm | tok/s out (median) | samples | TTFT ms | prompt tok | accepted / drafted (timed) | tokens per pass | prompt tok/s (server) |
|---|---:|---|---:|---:|---|---|---:|
| **S_code start 1** | 53.0 | 53, 54.5, 49.9 | 1,767 | 243 | 159/232, 160/231, 160/236 | 2.64-2.67 | 137-141 |
| **S_code start 2** | 52.2 | 50.7, 52.2, 54.7 | 1,812 | 242 | 160/229, 163/229, 162/231 | 2.67-2.75 | 135-142 |
| **S_reason** | 65.5 | 65.5, 68.8, 65.1 | 1,874 | 306 | 183/212, 183/213, 179/219 | 3.32-3.51 | 160-166 |
| **L_code** (llama.cpp static, no drafter) | 20.5 | 20.5, 20.3, 20.6 | 1,027 | 242 | - | 1 | 241-269 |
| S_nomtp (both forms) | not runnable | | | | | | |
| L_code_mtp | not runnable | | | | | | |

**Tokens per pass** = 256 / (256 - accepted).
- **S_nomtp:** the native pack needs `--spec >= 2`, and serve mode needs `--mtp`.
- **L_code_mtp:** the Coder GGUF has no MTP layers llama.cpp can load ("model doesn't contain MTP layers"). Strata
  ships its own separately built draft layer.

## Registered verdicts

| # | claim | result |
|---|---|---|
| P1 | S_code at 30-50 tok/s | **does not hold, faster:** 52.6 (two starts, 53.0 / 52.2). Strata's README claims 44 for this card and pack, measured at 4K answers on 0.1.26. |
| P2 | MTP worth at least 1.4x | **holds as an upper bound only:** 2.6-2.8 tokens per pass on code and 3.3-3.5 on reasoning. A no-MTP arm cannot run (Deviation 2), so it is not measured directly. |
| P3 | Strata at least 3x llama.cpp static offload | **does not hold:** 2.57x (52.6 / 20.5). The cache is still a measured contributor (checks below). |

## Checks added after review (Deviation 3)

**Check 1, from the existing logs.** Strata's "decode expert cache hit rate" per request:
- **82.7-83.2 %** (129-132k hits of 154-160k lookups), with 69.1 % on each run's first request while the cache warms.
- It keeps about 4,600-5,200 of the Coder's 12,288 experts (48 layers x 256) on the GPU, ~40 %.
- llama.cpp's `-ncmoe 28` puts a similar count there (20 layers x 256 = 5,120), but as whole layers. That is a FIXED
  41.7 % of routed-expert work.
- **So for about the same VRAM, the adaptive cache serves twice the share of expert work from the GPU (83 vs 42 %).**
  That is the cache's contribution, measured directly.

**Check 2, L_verify** (`llama-bench` b11433, shard 1, `-ngl 99 -fa 1 -ncmoe 28`, x5):

| test | tok/s | time per pass |
|---|---:|---:|
| 4-token batch (`-p 4 -ub 4 -b 4`) | 2.86 ± 1.22 | ~1.4 s |
| 1-token decode (`-n 32`) | 13.57 ± 3.08 | ~74 ms |

- **Both are noisy:** the 54 GB model cannot stay in the page cache with 31 GB of RAM. The steady server decode was
  20.5.
- **Even at the extremes of both ranges, a 4-token pass costs at least 10x a 1-token pass here.**
- **Prior art agrees:** INDEX L438 has llama.cpp MTP on Flash-Next under heavy offload (`-ncmoe 44`, P100s) at only
  1.30x (2 GPUs) / 1.44x (4), because verifying a draft reads more host-resident experts.

## What it means

- **Strata's lead is the combination, and the cache is a measured part of it.**
  - MTP gives it 2.6-3.5 tokens per pass.
  - What makes those multi-token verify passes affordable (~19/s, close to llama.cpp's single-token 20.5) is the
    cache's 83 % GPU hit rate and the CPU computing its misses in place.
  - llama.cpp's static offload pays at least 10x for a 4-token pass here, so adding MTP to it would not reproduce
    Strata's result. An earlier draft of this receipt said "the lead is MTP, not the cache". That was wrong, withdrawn
    after review.
- **The transferable idea is the popularity-based VRAM expert cache.** On this model's routing, ~40 % of the experts
  catch 83 % of the lookups. Whether other MoEs are as skewed is the next test (simulate it from routing traces).
- **Prompts, short ones especially:** 135-166 tok/s on 242-306-token prompts (TTFT ~1.8 s) against llama.cpp's
  240-270 (TTFT ~1.0 s).
  - **Caveat:** setup warned that it has no hipBLASLt tuning table for this ROCm version, so Strata's dense prompt
    products ran on plain hipBLAS. Its 1,420 tok/s claim is also for 32K prompts. Not a fair verdict on Strata's
    prefill.
- **RAM is the real constraint on this desktop.** The installer's config leaves ~7 GB available, enough to trigger a
  global OOM while the desktop was in use (see the incident in the prereg).

## Not established

- **A speculation-matched engine comparison** (check 1 measures the cache directly; an end-to-end match still needs llama.cpp with a usable MTP head on the
  same weights, llama.cpp with a usable MTP head on the same weights, e.g. the full Flash-Next on .194 against Strata's P100 path).
- **Quality** (see INDEX L186 for this Coder).
- **Long contexts and 32K prompts.**
- **Strata's own figures under its own benchmark.**
- **Nothing was submitted.**
