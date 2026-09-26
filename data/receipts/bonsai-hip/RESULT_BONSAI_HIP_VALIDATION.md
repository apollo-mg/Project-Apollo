# Bonsai 2 PQ2_0 decodes correctly on HIP (RX 9070 XT) in both buun and prism: the two agree to KLD 0.00015, and both sit 0.004 from the P100 CUDA reference

**2026-09-25.** Prereg `PREREG_BONSAI_HIP_VALIDATION.md` (+ Deviation 1: the repo's `wiki.test.raw` is a 404 stub,
so the real WikiText-2 test file was used, sha256 `173c87a5...`).
- **Model:** `Ternary-Bonsai-2-27B-PQ2_0.gguf`, sha256 `3907dc1658db1f78...` (hashed on both nodes).
- **Settings:** `llama-perplexity -c 512 -b 512 --chunks 10`, f16 KV, `-ngl 99`.
- **Logs:** `raw/`, with home paths redacted.

## Result

| arm | build | mean KLD vs CUDA ref | median | max | same-top | PPL(Q)/PPL(ref) | verdict |
|---|---|---:|---:|---:|---:|---:|---|
| **H1** | buun `38ada0e1b` `build_rocm` (PQ2_0 -> `q2_0_g128`, 402 tensors) | **0.00408** | 0.00298 | 0.0525 | **96.24 %** | 0.9971 | **PASS** |
| **H2** | prism `9a9394a` `build_hip` (`pq2_0`, 402 tensors) | **0.00412** | 0.00305 | 0.0582 | **96.24 %** | 0.9975 | **PASS** |
| *reference* | prism `9a9394a` sm_60 CUDA on .194 GPUs 0,1, `-sm layer` | -- | -- | -- | -- | PPL 10.4112 +/- 0.561 | -- |

The bar was set before any HIP pass: KLD <= 0.01, same-top >= 95 %, PPL within 2 %. Every load log reports the
402 ternary tensors under the expected type and a final estimate, with no NaN.

## The control: the two HIP implementations against each other

H1 saved its own logits, and H2 was scored against them.

| | mean KLD | median | max | same-top | PPL ratio |
|---|---:|---:|---:|---:|---:|
| H2 vs H1 | **0.000149** | 0.000099 | 0.0042 | **99.41 %** | 1.0005 |

- **Two independent HIP decoders agree about 27x more closely than either agrees with CUDA.** buun remaps PQ2_0 onto
  its own group-128 ternary type; prism decodes its private type directly.
- **So the 0.004 KLD offset lies between the CUDA (sm_60) and HIP backends, not in either HIP decoder.** It is the
  same scale as the known Pascal fp16 path error (median 0.0023 before the FAST_FP16 fix, `pascal-kv-finding`).
  This run does not prove that is the cause: that would need a non-Pascal CUDA reference.
- **For our purposes:** Bonsai judgements measured on the 9070 with either fork are measurements of the same model
  that ran the marker-penalty rows on .194, within backend noise.

## Speed (descriptive, one run each, not registered)

- **Prompt eval, 5,120 tokens:**
  - buun: 1,425 t/s (0.58 s per pass);
  - prism: 1,104 t/s (0.66 s per pass).

  A repeat prism run measured 0.57 s per pass, so the gap between the forks is within run-to-run noise here.
- The 2x P100 reference took 4.63 s per pass, **about 8x slower** than the 9070 on either fork.

## What this answers

buun's `docs/bonsai.md` says HIP "shares fallback code but has not been hardware-validated here." It is now
validated for correctness on gfx1201 (RDNA4) at this commit, for prompt processing at `-b 512`. This run does not
exercise single-token decode (MMVQ) or long context.

## Not established

- 10 chunks x 512 tokens, one text, f16 KV.
- Prompt processing only, no generation.
- One commit of each fork.
