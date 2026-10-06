# Result -- Strata decodes Flash-Next Coder at 52.6 tok/s (code) and 65.5 (reasoning) on a 16 GB RX 9070 XT with 31 GB of RAM, 2.6x llama.cpp's static offload (20.5); but it runs ~19 forward passes/s against llama.cpp's 20.5, so the measured lead is MTP's tokens per pass, and the adaptive expert cache is not yet shown to beat static offload

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
| P3 | Strata at least 3x llama.cpp static offload | **does not hold:** 2.57x (52.6 / 20.5) |

## What it means

- **The decode lead is speculation, not (yet demonstrably) the cache.**
  - Strata: 52.6 / 2.7 ≈ 19.5 passes/s on code and 65.5 / 3.45 ≈ 19 on reasoning.
  - llama.cpp's static offload: 20.5 single-token passes/s.
  - Each Strata pass verifies a window of up to 4 tokens, so it is doing more work per pass: its expert handling is
    more efficient per verified token.
  - But the 2.6x end to end is what MTP's 2.7 tokens per pass would give llama.cpp too, IF llama.cpp had a usable MTP
    head for this model. Whether the adaptive cache beats static `-ncmoe` once speculation is matched is the open
    question this run could not answer.
- **Prompts are Strata's weak spot at short lengths:** 135-166 tok/s on 242-306-token prompts (TTFT ~1.8 s), against
  llama.cpp's 240-270 (TTFT ~1.0 s). Its 1,420 tok/s claim is for 32K prompts, where its 8,192-token chunks amortize.
- **RAM is the real constraint on this desktop.** The installer's config leaves ~7 GB available. That was enough to
  trigger a global OOM while the desktop was in use (the incident in the prereg).

## Not established

- **The adaptive cache's own contribution.** That needs speculation matched: llama.cpp with a usable MTP head on the
  same weights, e.g. the full Flash-Next (whose unsloth GGUFs carry MTP layers we have used before) on .194, against
  Strata's P100 path, or a box with the RAM for Strata's full packs.
- **Quality** (see INDEX L186 for this Coder).
- **Long contexts and 32K prompts.**
- **Strata's own figures under its own benchmark.**
- **Nothing was submitted.**
