# Result — EXL3 runs correctly on Pascal: +0.55% perplexity against Q6_K on 61% of the bits

> **Clarified 2026-09-12 ~16:00: which "bits".** "61% of the bits" in this receipt is the *nominal*
> bits-per-weight ratio of the quantized linears (4.00 vs ~6.56). The two measured ratios:
> - **VRAM: 64%.** EXL3 held 14,238 vs 22,342 MiB at load, under `-sm tensor` at c 8192 with the same
>   f16 KV in both.
> - **Disk: 74%**, 16.88 vs 22.88 GB.
>
> Two tensor families inflate the disk figure. One is a 2.54 GB bf16 token-embedding table, which
> evidently stays in host memory. The other is a 0.92 GB bf16 vision tower that the native `qwen35`
> loader never loads (`exl3-campaign/CAMPAIGN_EXL3.md`). The finding is unchanged; the basis is now
> named.

**Run 2026-09-12 on `.73`** — 2× Tesla P100-PCIE-16GB (sm_60), driver 580.178.04, CUDA 12.4. Binary:
buun `9ae8f0f40` + the declared `PATCH_e8m0_cuda128_guard.diff`
(`RESULT_SM60_EXL3_QUALIFICATION.md`). Pre-registered in `PREREG_EXL3_SM60_INFERENCE.md` + Amendment 1
and Amendment 2 (`6ea569b`, `85b4f45`, `c6a45c1`, `270d982`), each committed before the data it governs. Driver
`exl3_sm60_qual.py`; raw in `exl3_sm60/`.

## Headline

**EXL3 runs correctly on Pascal, and buun's scalar sm_60 fallbacks are its fast path.** On `.73`'s two
P100s, turboderp's Qwen3.8-27B EXL3 at 4.00 bpw against the daily driver's own Q6_K:

| | EXL3 4.00 bpw | Q6_K GGUF (~6.6 bpw) | EXL3 ÷ Q6_K |
|---|---|---|---|
| perplexity, wikitext-2 | 5.9520 | 5.9195 | **+0.55%** |
| decode, `-sm layer` | 6.96 t/s | 7.81 t/s | 0.89× |
| decode, `-sm tensor` | 11.26 t/s | 13.22 t/s | 0.85× |

**Within 0.55% of Q6_K's perplexity on 61% of the bits, at 85–89% of its decode speed.** The int8
path is 2.9× faster than the reconstruct-and-cuBLAS path on the same weights. **7 predictions confirmed,
2 falsified** — P-X4 (the two kernel paths agree for ~45 tokens, not 64) and P-X9 (tensor split helps
GGUF slightly more than EXL3).

## Instrument

| | |
|---|---|
| `X-06` | `turboderp/Qwen3-0.6B-exl3` @ `4.0bpw` — `model.safetensors` sha256 `fa99060c…2300e8a`, verified on `.73` |
| `X-27` | `turboderp/Qwen3.8-27B-exl3` @ `4.00bpw` — shards `b1e7fcc5…c041e590`, `c6d72f51…f87f8c05`, verified on `.73` |
| `Q6K` | the daily driver's `Qwen3.8-27B-Q6_K.gguf`, 22,884,408,288 bytes — **a withdrawn unsloth upload**: `unsloth/Qwen3.8-27B-GGUF` @ `db81afd1e1` (2026-08-19), published sha256 `562fbf76…486727`, deleted two seconds later in the reorganisation that introduced today's `UD-Q6_K*` files. Header: `quantized_by = Unsloth`, unsloth imatrix. **Local sha256 matches it** — hashed on `.73` after the run |
| flags | `-ngl 99 -sm layer -c 8192 -np 1 -fa on -ctk f16 -ctv f16 --jinja`; `kv_bpv` 16.0 read back from `/slots` on every load |
| text | wikitext-2-raw test, 1,290,590 bytes, sha256 `173c87a5…9e7dd08` — three independent copies agree |
| window | wake proxy paused 14:03:37–14:35:43 and 14:37:20–14:43:23, each span under a dead-man timer; live for 94 s in between (see Deviations) |

**Load times are not comparable across models.** The EXL3 weights live on `/mnt/HDD` (spinning disk,
~53 MB/s through the native loader); the Q6_K file is on NVMe.

## Results

| stage | `X-06` (0.6B) | `X-27` int8 path | `X-27` cuBLAS path | `Q6K` |
|---|---|---|---|---|
| load | 5 s, 0.9 / 1.2 GB | 302 s, 7.0 / 7.5 GB | 239 s, 7.0 / 7.6 GB | 27 s (NVMe), 11.2 / 11.6 GB |
| fact | `Paris` | `Paris` | `Paris` | `Paris` |
| greedy (64 tok) | "…is a tapestry of triumphs and tragedies…" | "…from its foundation to the fall of the Western Empire, is a rich and complex n…" | **identical to the int8 path for the first 193 of 275 characters**, then a near-tie flip (P-X4) | "…from its foundation to the fall of the Western Empire, is a rich tapestry of p…" (a different model; divergence expected) |
| decode t/s | 69.43 / 69.50 / 69.81 | **6.59 / 6.97 / 6.96** | 2.39 / 2.43 / 2.43 | **7.80 / 7.81 / 7.81** |
| perplexity | 20.2864 ± 0.6672 | **5.9520 ± 0.1419** | — | **5.9195 ± 0.1406** (`-ts 3,2`, Amendment 2) |

### Tensor split (Amendment 1) — `-sm tensor -fit off`

| stage | `X-27` tensor | `Q6K` tensor |
|---|---|---|
| load | 265 s, **7.1 / 7.1 GB** (layer split: 7.0 / 7.5) | 31 s, 11.2 / 11.2 GB |
| fact | `Paris` | `Paris` |
| greedy | the same first 80 characters as `-sm layer` | the same first 80 characters as its `-sm layer` run |
| decode t/s | **10.23 / 11.26 / 11.26** | **13.20 / 13.22 / 13.24** |

| decode, median | `-sm layer` | `-sm tensor` | gain |
|---|---|---|---|
| `X-27` EXL3 4.00bpw | 6.96 | 11.26 | +62% |
| `Q6K` GGUF | 7.81 | 13.22 | +69% |
| **EXL3 ÷ Q6_K** | **0.891** | **0.852** | moves *away* from 1 |

## Why the first Q6_K perplexity run ran out of memory

On sm_60 the MMQ kernels are refused for dense models. `ggml_cuda_should_use_mmq` (`mmq.cu`,
`9ae8f0f40`) returns `cc >= GGML_CUDA_CC_PASCAL && n_experts > 0` whenever the highest compiled arch is
below `GGML_CUDA_CC_DP4A` (610) — MoE only. Qwen3.8-27B is dense, so every batched GGUF matmul
(prefill, perplexity) takes the cuBLAS path on fp16-dequantised weights, which need pool memory; with
~11 GB of Q6_K weights already resident per card, that pool is what ran out. EXL3's reconstruct path
bounds the same step with 256 MB chunks (`exl3.cu`), which is why `X-27` fit at identical settings.
*(The gate is read from source; the buffer sizing is inferred from the code path, not measured.)*

**`llama-perplexity` exited 0 after `failed to decode`.** The driver caught it only because it scores
the `Final estimate` line. Any script that trusts the exit code of that tool would have recorded a
failed run as a success.

**The repair worked on its first option.** `-ts 3,2` produced **5.9195 ± 0.14058**, and the `-ub 8`
fallback was not needed. Placement only: the same binary, text, context, chunk count and KV type.

## Predictions

| id | prediction | result |
|---|---|---|
| P-X1 | `X-06` loads and produces coherent text | **CONFIRMED** |
| P-X2 | `X-27` loads and answers a factual question correctly | **CONFIRMED** — `Paris` |
| P-X3 | `X-27` perplexity within +5% of Q6_K | **CONFIRMED** — 5.9520 vs 5.9195: EXL3 at 4.00 bpw sits **+0.55%** above the ~6.6 bpw Q6_K, a ninth of the registered margin. The Q6_K figure is from the Amendment 2 placement repair (`-ts 3,2`); `X-27` ran at the registered placement |
| P-X4 | int8 and cuBLAS paths agree on the first 64 greedy tokens | **FALSIFIED** — byte-identical for the first 193 of 275 characters, then *"saw the rise of Julius Caesar, who was assassinated in 44 BC"* (int8) against *"saw the rise of powerful figures such as Julius Caesar"* (cuBLAS): a near-tie flip into two coherent continuations. By design the int8 path quantises activations per slice (`exl3.cu`), so it is a different computation, not a reordering of the same one — exact agreement at 64 tokens was the wrong bar. A broken kernel diverges into garbage at once; this ran in lockstep for ~45 tokens. P-X3 is the registered correctness check |
| P-X5 | `X-27` decodes slower than Q6_K under matched flags | **CONFIRMED, narrowly** — 6.96 vs 7.81 t/s median: EXL3 at **0.89×** Q6_K while holding ~61% of the bits (4.00 vs ~6.6 bpw). On sm_60, with no `__dp4a`, the scalar int8 path costs 11% against a GGUF recipe that has had years of Pascal tuning |
| P-X6 | int8 path decodes faster than cuBLAS on `X-27` | **CONFIRMED** — 6.96 vs 2.43 t/s median, **2.9×**. buun's scalar sm_60 byte-dot fallbacks are not only correct but the *fast* path on Pascal; the cuBLAS path rebuilds every weight to fp16 on every token |
| P-X7 | `X-27` loads under `-sm tensor` | **CONFIRMED** — buun's `32c2c1479` guard does not reject it; VRAM splits evenly, 7.1 / 7.1 GB |
| P-X8 | `X-27` decodes faster under `-sm tensor` than `-sm layer` | **CONFIRMED** — median **11.26 vs 6.96 t/s, +62%**. On Pascal the all-reduce runs the butterfly fallback (sm_60 fails the cc ≥ 700 check), so this gain is achieved without the fast path |
| P-X9 | EXL3 ÷ Q6_K decode ratio closer to 1 under tensor split | **FALSIFIED** — 0.891 under layer split, 0.852 under tensor. Both gain a lot; GGUF gains slightly more (+69% vs +62%) |

## Deviations, declared

- **`X-06` ran with the wake proxy still running.** It was idle in its `suspended` state with no
  server on the node; the proxy log shows no launch between 13:49:00 and 13:49:18. No registered
  prediction depends on `X-06`'s speed.
- **Orchestration, in full — four hand-offs, one of them wrong.**
  1. The first orchestrator would have restored the proxy the moment the registered stages ended; it
     was replaced at ~14:14 so the Amendment 1 stages could run first. The dead-man was re-armed at
     +120 min *before* the old one was retired.
  2. At ~14:24 the harness killed that orchestrator on "low memory"; a detached successor took over.
  3. **At ~14:35 I killed the successor by PID to add the Q6_K repair, not knowing it had already
     launched the tensor stages (14:31:58).** Its replacement found the registered-stage pid dead,
     launched a duplicate tensor job — which the driver's preflight refused on every stage
     (*"llama-server already running"*) — and, reading that as done, **restarted the wake proxy and
     disarmed the dead-man at 14:35:43 while the real tensor job was still running.** The proxy was
     re-paused at 14:37:20 under a fresh dead-man; `.73` showed exactly one llama-server (ours), so
     nothing collided in those 94 seconds. A third orchestrator waited on the real job by explicit pid.
  4. **`exl3_sm60_qual_v2.py` was overwritten on `.73` while `X-27-tensor` was executing it.** My
     pre-overwrite check printed "3 processes" and did not abort. Python had already loaded the file,
     and the change was additive (it touched only `ppl()` and added a stage), so `Q6K-tensor` — which
     started from the new file — ran the same code path. It is still a mid-run instrument edit, and is
     declared as one. **A check that prints instead of aborting is not a check.**

## What is not claimed

- **One box, one toolkit, one driver, and not upstream-identical.** `.73`, CUDA 12.4, driver
  580.178.04, built with the declared `PATCH_e8m0_cuda128_guard.diff`.
- **Not a bit-matched EXL3-vs-GGUF comparison.** One EXL3 file at 4.00 bpw against one GGUF file at
  ~6.6 bpw — itself a withdrawn unsloth upload. It answers "EXL3 against what runs on this box today",
  not "EXL3 against GGUF".
- **Speed is 3 × 256 decoded tokens after a short prompt**, f16 KV, `-c 8192`, no speculative decoding.
  The EXL3 27B carries a 4-bit MTP head that was not used. Nothing about long context, prefill at
  scale, VBR, or MTP.
- **The tensor-split runs add `-fit off`**, copied from the daily driver's launch and assumed inert at
  explicit `-c`/`-ngl`. That assumption was not tested.
- **The int8-path correctness evidence is end-to-end**: a correct factual answer, coherent text, ~45
  tokens of greedy agreement with an unrelated kernel path, and perplexity. It is not a per-kernel
  numerical comparison against a reference implementation.
- **Nothing about other Pascal parts** (sm_61 has `__dp4a` and takes a different path), the MoE expert
  path (`mul_mat_id`, CPU expert execution, the MoE cache), or the 0.6B beyond load-and-generate.
- **Load times are not comparable**: EXL3 from spinning disk, Q6_K from NVMe.
