# DFlash2 does not fit a Q6_K 27B on 32 GB — six configurations, all OOM

**2026-08-23**, `.194`, 2× Tesla P100 (sm_60), 1063 MHz / 150 W. buun `7d30a7244`
(`build_sm60_new`, sm_60 routing fix present). Raw `~/df2_*.log`, `~/dfr_*.log` on `.194`.

## What we built first

**There is no published DFlash2 GGUF anywhere.** `z-lab/Qwen3.8-27B-DFlash2` ships safetensors
only. We converted it:

- `convert_hf_to_gguf.py` from buun master registers **`DFlash2DraftModel`** — our config's exact
  architecture
- it needs `--target-model-dir` for tokenizer + `config.json`, **not the target weights**:
  22 MB of metadata instead of the 54 GB HF repo
- produced `Qwen3.8-27B-DFlash2-BF16.gguf` (3.86 GB, 81 tensors), then
  `Qwen3.8-27B-DFlash2-Q8_0.gguf` (2.18 GB) via `llama-quantize`

Both files are believed to be the first of their kind.

## The result

Baseline, no speculation, reproduced **three times across separate server launches**:
**13.24 / 13.25 / 13.26 t/s** — and independently **13.00** from `llama-bench` yesterday. The
harness is not in question.

| # | target | draft | split | VMM | outcome |
|---|---|---|---|---|---|
| 1 | Q6_K 22.88 GB | BF16 3.86 | tensor | on | OOM — *"failed to create DFlash draft context"* |
| 2 | Q6_K | BF16, `-devd CUDA0,CUDA1` | tensor | on | hard abort, OOM |
| 3 | Q6_K | **Q8_0 2.18** | tensor | on | hard abort, OOM |
| 4 | Q6_K | Q8_0 | tensor | **off** | OOM |
| 5 | Q6_K | Q8_0 | **layer** | on | OOM |
| 6 | Q6_K | Q8_0 | layer | off | OOM |

**Six configurations. Two draft quantisations, two split modes, VMM on and off. All fail.**

## Where it fails, and why that matters

Not at KV allocation. The stack trace puts it inside a **warmup decode** during
`common_speculative_impl_draft_dflash`'s constructor:

```
ggml_cuda_pool_vmm::alloc → ggml_cuda_mul_mat_cublas → ggml_backend_cuda_graph_compute
→ llama_decode → common_speculative_impl_draft_dflash::common_speculative_impl_draft_dflash
```

So it is a **transient cuBLAS workspace**, not a persistent buffer — which is why disabling the
VMM pool did not help and why the arithmetic (25.06 GB of 32.5) looked survivable.

**A separate, reproducible finding:** the auto device selector announces
`[spec] auto-selected CUDA1 as the primary draft device` and places the whole draft head on one
card. Under tensor split that card is already ~11.4 GB full, so it dies allocating **90 MiB**.
The selector assumes the draft head has a GPU to itself.

## What this does and does not say

- **It does NOT say DFlash2 is broken on sm_60.** No arm ever reached generation, so no
  statement about correctness or speed on Pascal is supported. `AFM-24`: the claim is only as
  wide as the envelope tested, and this envelope is *a 22.88 GB target on 32 GB*.
- **It does say the published pairing is load-bearing.** buun's announcement uses
  `-m Qwen3.8-27B-Q4_K_M -md Qwen3.8-27B-DFlash2-Q8_0.gguf` — a 4-bit target with an 8-bit
  draft. We tried a 6-bit target with a 16-bit draft, ~9 GB heavier. **That configuration is not
  arbitrary; it is what fits.**
- The operative constraint for local deployment: on a 32 GB pair the draft head competes
  directly with context. At `turbo3_tcq` its 2.18 GB is ~175k tokens of KV.

## Open

A smaller target (`UD-IQ2_M`, 10.32 GB) is running now purely to answer *"does it run at all on
sm_60."* That number will **not** be comparable to the 13.24 t/s Q6_K baseline — different
model. The comparable test needs a **Q4_K_M target**, which we do not hold.
