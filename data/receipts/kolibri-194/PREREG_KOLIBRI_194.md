# Pre-registration: does Aleph Alpha's Kolibri-1 (78B-A3.46B MoE) run correctly and how fast, fully VRAM-resident on 4x P100, through the unofficial llama.cpp port?

**Registered 2026-10-06, before any row.** BACKLOG N21 (Mark: "Sure").

**Prior art checked:** `ledger_precheck.py "Kolibri Aleph Alpha MoE sliding window P100"` -> nothing on Kolibri.
- **Nearest:** Flash-Next / GLM-5.3 MoE speed on .194 (qwen4exp, glm53-flash). **What this adds:** the first
  measurement of this model on Pascal, and a sanity check of an unofficial port that 11.6k downloaders are running.
- **No upstream llama.cpp support:** #29922 is open and no PR exists.

## Instrument

- **Model:** `Hob-forge/Kolibri-1-GGUF` @ `47fb91b2`, `Kolibri-1-Q4_K_M.gguf`, 47,454,113,472 B.
  - sha256 `c2ac1301…6062e` (HF LFS), checked on .194 before any row.
  - Its card: converted from Aleph Alpha's FP8 checkpoint, dequantized to BF16, then quantized.
- **Engine:** upstream llama.cpp `836d571` + `kolibri1-llama.cpp.patch` from the same repo revision (4 commits,
  HEAD `60d1d51cc`). Built for sm_60 with CUDA 12.4 and gcc-13 as host. The patch was read before building: model
  code, converter, vocab and one test only.
- **Server:** `-ngl 99 -sm layer -fa on -fit off -c 8192 -np 1 -ctk f16 -ctv f16 --jinja`, thinking off (`--reasoning
  off` if the template has a toggle, recorded either way).
- **Host:** .194 as in `strata-194/` (same boot); clocks recorded.

## Arms and gates

1. **K_load:** the server loads, all layers on GPU (log), `/props` model path.
2. **K_sane:** three fixed questions, greedy, 128 tokens.
   - 2+2.
   - The capital of Germany, asked in German.
   - Define photosynthesis in one sentence.
   - **Gate:** coherent answers in `content`, and the German question answered in German.
3. **K_ppl:** `llama-perplexity` on wikitext-2 test, 16 x 512, `-b 512`. Recorded as a sanity number, not a quality
   claim (no reference to compare with).
4. **K_speed:** `lmx` remote (`run194.sh`-style) on canonical reasoning-v1 and code-v1.
   - 1 warmup + 3 timed, median, one server start each.
   - Evidence captured by `g4_proxy.py`.

## Predictions

| # | claim | confidence |
|---|---|---|
| K1 | the port loads and K_sane passes (coherent, German answered in German) | 0.75 |
| K2 | wikitext-2 PPL is below 15 (the port is not badly broken) | 0.7 |
| K3 | decode on reasoning-v1 is at least 30 tok/s (3.46B active, fully resident) | 0.5 |

## Not tested

- Agreement with the second unofficial port (Eliasfpv28's patch). This is the planned follow-up, since there is no
  runnable reference here.
- Quality against Aleph Alpha's reference.
- Long contexts.
- Reasoning mode.

## Deviations

Any change after the first row gets a numbered Deviation here before the affected rows run.
