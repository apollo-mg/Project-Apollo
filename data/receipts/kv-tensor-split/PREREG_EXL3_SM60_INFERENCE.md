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

---

## Amendment 1 — add `-sm tensor` (2026-09-12 ~14:13, before any tensor-split EXL3 data)

buun asked for it directly — *"try with -sm tensor, why not"* — and his fork carries EXL3 tensor and
expert splitting (`dc41967d3`) alongside a guard that **rejects** unsupported multi-device EXL3 splits
(`32c2c1479`). Two stages are added, run after the registered set in the same window on the same box:

| label | model | flags |
|---|---|---|
| `X-27-tensor` | `X-27` | as registered, but `-sm tensor -fit off` |
| `Q6K-tensor` | `Q6K` | as registered, but `-sm tensor -fit off` — its matched baseline |

`-fit off` is copied from the daily driver's known-good tensor-split launch on this box. At explicit
`-c 8192 -ngl 99` it is expected to be inert; it is declared rather than assumed away. The added
stages run from a separate copy of the driver (`v2`) so that the registered stages still in flight
read an unchanged script (v1's md5 on `.73` was re-checked against its commit, `f3d83655`). For the
registered labels the two copies run the same flags and the same code path, but the files are **not**
byte-identical: `v2` threads a `flags` argument through `start()` and `run_model()`, defaulting to
the registered `FLAGS`. *(The first version of this amendment said "byte-identical"; it was not.)*

**Seen so far, in full:** `X-06` (all stages) and `X-27` under `-sm layer` — loaded in 302 s, answered
`Paris`, coherent greedy text, decode 6.59 / 6.97 / 6.96 t/s. Nothing from any tensor-split run, and
nothing from `X-27-cublas`, `Q6K` or perplexity.

| id | prediction | conf |
|---|---|---|
| P-X7 | `X-27` loads under `-sm tensor` — i.e. `32c2c1479` does not reject it | 60% |
| P-X8 | if it loads, `X-27` decodes faster under `-sm tensor` than under `-sm layer` | 70% |
| P-X9 | the EXL3 ÷ Q6_K decode ratio is closer to 1 under tensor split than under layer split | 50% |

The proxy pause is extended to cover these stages; the 90-minute dead-man timer (armed 14:03:36)
still bounds it.

---

## Amendment 2 — the Q6_K perplexity run failed; placement repair (2026-09-12 ~14:34, before any repaired data)

**What happened.** `llama-perplexity` on `Q6K` at the registered settings died on its first batch —
`CUDA pool allocation failed (out of VRAM)` → `perplexity : failed to decode` — **and exited 0.** The
driver caught it only because it scores the `Final estimate` line rather than the exit code. `X-27` at
identical settings completed: **5.9520 ± 0.14188.** The Q6_K weights occupy ~11 GB per GPU against
EXL3's ~7 GB, which leaves less room for compute buffers; the mechanism is checked against source and
reported in the receipt, not asserted here.

**The repair, in order:**
1. `-ts 3,2` — shift layers off the second GPU, which holds the output projection. Placement only:
   same binary, text, context, chunk count and KV type, every weight still on a GPU.
2. **Only if (1) also fails to produce an estimate:** `-ub 8`, which keeps every batched matmul on the
   vector kernel. A different kernel path, and slower, but no whole-matrix buffers.

Perplexity is a property of the weights, not of where they sit; any placement effect is far inside the
±0.14 standard error. **`X-27` is not re-run.** P-X3's threshold (+5%) and scoring are unchanged. If
neither repair produces an estimate, P-X3 is reported unscoreable.

**Seen so far, in full:** X-27 perplexity 5.9520 ± 0.14188; Q6K perplexity not produced. Everything
listed in Amendment 1 as seen, plus `X-27-cublas` (239 s load, `Paris`, greedy identical to int8 for
193 of 275 chars, 2.39/2.43/2.43 t/s) and `Q6K` (27 s load, `Paris`, 7.80/7.81/7.81 t/s).
