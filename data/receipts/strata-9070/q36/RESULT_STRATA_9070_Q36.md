# RESULT: on a 16 GB RX 9070 XT spilling Qwen3.6-35B-A3B, Strata 0.2.7 beats llama.cpp by 1.66x on code and 1.18x on reasoning; with MTP on both, 1.62x on code

**Prereg:** `PREREG_STRATA_9070_Q36.md` (`d1a5907f`), Addendum 1 (`4c7ae8f9`, MTP-variant file), Addendum 2 (`77ccc0cf`,
launch 3 design). **Scored run: launch 3, 2026-10-27 15:48-16:35.** Kernel page-allocation failures during every arm: 0.

**Setup:** Unsloth `Qwen3.6-35B-A3B-MTP-GGUF` UD-Q4_K_XL (22.85 GB, sha256 `55983c5a...`), RX 9070 XT 16 GB, 31 GB RAM.
Strata v0.2.7 (engine compiled from `5e8a4cca`), `--max-context 32768 --vram-reserve-mib 1024`, sampling forced to plain
greedy (no penalties). llama.cpp `f74e2fa` ROCm, `-c 32768 -fa on -ctk f16 -ctv f16 -t 8`, `--presence-penalty 0
--repeat-penalty 1`, `--n-cpu-moe 16` (the fastest of 16/18/20 within Strata's VRAM use + 0.10 GB). lmx custom remote,
temperature 0, 256 tokens, canonical code-v1 and reasoning-v1, median of 6 timed samples (two passes of 1 + 3).

| arm | code-v1 tok/s | reasoning-v1 tok/s |
|---|---|---|
| Strata, no MTP | **88.2** | **62.9** |
| llama.cpp, no MTP (ncmoe 16) | **53.0** | **53.3** |
| Strata + MTP | **135.5** | **78.5** |
| llama.cpp + MTP | **83.5** | **60.4** |
| llama.cpp sweep, code: ncmoe 16 / 18 / 20 | 53.0 / 51.5 / 49.9 (VRAM 16.22 / 15.35 / 14.37 GB) | |

| # | prediction | result |
|---|---|---|
| P1 | Strata >= 1.4x llama.cpp's best split, no MTP, on BOTH prompts | **fails**: code 1.66x, reasoning **1.18x** |
| P2 | Strata's expert cache serves >= 70 % of routed entries from VRAM | **holds**: code 77.8 % (77.3 % with MTP), reasoning 72.5 % (73.3 %) |
| P3 | No OOM under `MemoryMax=26G` | **holds**: unit peak 24.96 GiB, every arm finished |
| P4 | Strata's MTP gain >= 1.2x on code | **holds**: 1.54x (drafts accepted 75-83 %) |
| P5 | Strata + MTP >= 1.4x llama.cpp + MTP on code | **holds**: 1.62x (reasoning 1.30x, not predicted) |

## What it means

- **Strata's lead depends on the prompt, through its expert cache.** llama.cpp's static split runs both prompts at the
  same 53 tok/s. Strata's adaptive cache hits more on code (78 %) than on reasoning (72-73 %), and its speed follows:
  88 vs 63. On this card, code is where the cache earns 1.66x; general reasoning gets 1.18x.
- **With MTP drafting on both engines, Strata reaches 135 tok/s on code**, 1.62x llama.cpp's 83.5, and 1.30x on
  reasoning. Its MTP adds 1.54x on code and 1.25x on reasoning; llama.cpp's adds 1.58x and 1.13x.
- **The cost is memory.** Strata pins all 18.75 GiB of experts in host RAM and takes 7.5-9.5 minutes to load; llama.cpp
  holds ~5 GB of RAM and loads in under a minute. On a 32 GB desktop Strata leaves about 5-6 GB for everything else.

## Two traps found on the way (launches 1-2, not scored)

1. **Strata's Qwen3.6 path needs the MTP-variant GGUF.** The plain Unsloth file fails at load
   (`missing qwen35moe.nextn_predict_layers`).
2. **Strata's server fills in the model card's sampling for unset keys**, so a `temperature: 0` request still gets
   presence penalty 1.5. That forces the host-logits path and switches MTP drafting off ("drafts accepted 0 of 0").
   Benchmarks against Strata must set the penalties explicitly (here in the run config's `sampling` block).

Launch 2 also showed what happens with both engines filling VRAM to the last ~0.2 GB on a live desktop: page-allocation
failures in the shell and display, and decode stalls down to 4 tok/s. A 1 GB reserve removed them.

## Limits

- One model, one card, 256-token answers, one request at a time; two canonical prompts.
- llama.cpp's sweep started at ncmoe 16, as registered; ncmoe 14 (16.98 GB, inside the budget) was not swept in launch 3.
  In launch 2 it read 55.8 on code, so the code ratio could be ~1.58x rather than 1.66x. The reasoning ratio would only
  fall, so P1's failure stands.
- Strata's engine was compiled locally from the release source, not the prebuilt package.

**Files:** `runs/run.log` (launch 3), `summary_launch3.json`; launch 1-2 logs are kept locally.
