# Pre-registration — does EXL3 inference run correctly on Pascal (sm_60)?

**Logged 2026-09-12, before any EXL3 model has been loaded on any GPU.** Follows
`RESULT_SM60_EXL3_QUALIFICATION.md`, which qualified one kernel family (EXL3 byte-dot) with buun's
unit test. This registers the next tier: real models, end to end. buun asked for it directly: *"maybe
you wanna give an EXL3 safetensors a try? I don't have pascal to test with."*

## What sm_60 will actually execute — read from source before running

From `ggml/src/ggml-cuda/exl3.cu` at `9ae8f0f40`:

| condition | path on sm_60 |
|---|---|
| codebook `mul1` (`cb == 2`), m ≤ 8 (decode), `GGML_EXL3_INT8` unset | **int8 path** — the scalar `__dp4a` fallbacks that `test-exl3-byte-dot` qualified |
| anything else, or `GGML_EXL3_INT8=0` | **reconstruct + cuBLAS** — each matmul rebuilds its weights to fp16 in 256 MB chunks, then `cublasGemmEx` |
| the Ampere GEMV fast path | **never** — gated `compiled_cc >= GGML_CUDA_CC_AMPERE` |

`ggml_cuda_exl3_supports_mul_mat` has no compute-capability gate, so EXL3 matmuls stay on the GPU;
there is no silent CPU fallback to mistake for a pass.

## Models — both fetched with `tools/hf_fetch.py`, every file verified

| id | repo @ branch | arch | EXL3 format | codebook | exercises |
|---|---|---|---|---|---|
| `X-06` | `turboderp/Qwen3-0.6B-exl3` @ `4.0bpw` | `qwen3` | `0.0.1` | none (default) | loader + **reconstruct/cuBLAS** only |
| `X-27` | `turboderp/Qwen3.8-27B-exl3` @ `4.00bpw` | `qwen3_5` | `1.4.2` | **`mul1`** | **int8 path** (decode) + reconstruct/cuBLAS (prefill) |

**`X-06` cannot qualify the int8 path** — it has no `mul1` codebook — so a pass on it alone is a
loader result, not a kernel result. `X-27` is the real test, and is the same base model `.73` already
serves as Q6_K GGUF.

## Instrument

- **Binary:** `.73:~/buun-sm60-qual/build_sm60qual/bin/llama-server` and `llama-perplexity`, built from
  `9ae8f0f40` **with the declared local `PATCH_e8m0_cuda128_guard.diff`**.
- **Box:** `.73`, 2× P100 (sm_60), driver 580.178.04, CUDA 12.4. **The wake proxy is paused and the
  daily-driver server stopped for the window** — the proxy runs `pkill -x llama-server` before every
  idle suspend and would kill a test server.
- **Matched server flags for every model:** `-ngl 99 -sm layer -c 8192 -np 1 -fa on -ctk f16 -ctv f16
  --jinja`, no speculative decoding. KV verified from `/slots` (buun defaults to VBR otherwise).
- **Baseline:** the daily driver's own file, `Qwen3.8-27B-Q6_K.gguf`, under the same flags. **This is
  not a bit-matched comparison** — 4.00 bpw EXL3 against ~6.6 bpw Q6_K. It answers "what does EXL3 cost
  or save on this box against what runs here today", not "is EXL3 better than GGUF".
- **Correctness text:** wikitext-2-raw test, `-c 512 --chunks 40`, identical for every model; the
  file's sha256 is recorded in the receipt.

## Predictions

| id | prediction | conf |
|---|---|---|
| P-X1 | `X-06` loads and produces coherent text on sm_60 | 75% |
| P-X2 | `X-27` loads and answers a factual question correctly on sm_60 | 75% |
| P-X3 | `X-27` perplexity is within **+5%** of the Q6_K GGUF on the same text | 70% |
| P-X4 | forcing `GGML_EXL3_INT8=0` (reconstruct/cuBLAS) gives the **same greedy output** as the default int8 path for the first 64 tokens of a fixed prompt | 55% |
| P-X5 | `X-27` decodes **slower** than Q6_K under matched flags — scalar byte-dot on sm_60 has no `__dp4a` | 80% |
| P-X6 | on `X-27`, the int8 path decodes faster than reconstruct/cuBLAS | 85% |

**P-X3 is the correctness claim that matters.** A wrong sm_60 fallback does not produce a slightly
worse model; it produces garbage, and perplexity would show it in orders of magnitude, not percent.
**P-X4 is the second, independent check:** two unrelated kernel paths agreeing on greedy output is hard
to achieve by accident.

## Declared in advance

- **If `llama-perplexity` cannot load a native safetensors directory**, P-X3 is reported unscoreable
  rather than substituted with a different measure after the fact.
- **Speed is 3 reps of 256 decoded tokens per configuration**, read from the server's own timings.
- **Nothing about the MTP head** (`mtp_bits: 4` in `X-27`), tensor split, or any other box.
- **One model per quant family, one box, one toolkit.**
