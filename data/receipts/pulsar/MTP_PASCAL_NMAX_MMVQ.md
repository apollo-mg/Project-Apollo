# MTP on a Qwen3.6-35B-A3B MoE, 2× P100: **70.5 t/s**, and the n-max ceiling is set by the MMVQ batch table

Date 2026-08-03. Node `.73`, 2× Tesla P100-PCIE-16GB (sm_60), **150 W / 1063 MHz, persistence on**.
Build `TheTom/llama-cpp-turboquant` @ `d0e2a8b64` (upstream base 10281).
Model `Qwen3.6-35B-A3B-UD-IQ4_NL-MTP.gguf` — `qwen35moe`, 41 blocks,
`nextn_predict_layers=1`, 4 nextn tensors at `blk.40`, **17.26 GiB**.
Flags per Unsloth: `-c 8192 -fa on -np 1` (`-np > 1` and `--mmproj` unsupported with MTP),
plus `-ngl 99 -sm tensor`. n_predict 128, temp 0, K=3, alternating base/new.

## Headline

**MTP takes this MoE from 47.4 → 70.5 t/s (1.487×) on 2016 hardware.**

| arm | tok/s (K=3) | accept | mean len | verify batch | tok/cycle→ms |
|---|---|---|---|---|---|
| baseline `--spec-type none` | 45.99 / **47.42 / 47.42** | — | — | 1 | — |
| baseline (repeat) | 45.60 / **47.56 / 47.31** | — | — | 1 | — |
| MTP n-max 1 | 67.07 / **67.39 / 67.44** | 58/69 = 84.1% | 1.84 | 2 | 27.3 ms |
| MTP n-max 2 *(Unsloth default)* | 65.92 / **68.76 / 68.68** | 76/100 = 76.0% | 2.52 | 3 | 36.7 ms |
| **MTP n-max 3** | 70.28 / **70.50 / 70.52** | 87/120 = 72.5% | 3.17 | **4** | 45.0 ms |
| MTP n-max 4 | 35.20 / **35.43 / 35.26** | 90/145 = 62.1% | 3.43 | **5** | **97.2 ms** |

Prediction under test — Mark: *"Bet that box would do 70 t/s with MTP on a Qwen 3.6 35B based MoE."*
**Confirmed at n-max 3: 70.50 t/s.**

## The n-max 4 collapse is a kernel cliff, not a drafting failure

Throughput halves (70.5 → 35.3) but **`mean len` keeps rising** (3.17 → 3.43): MTP is delivering
*more* accepted tokens per cycle while total throughput falls. Cycle time therefore jumped
**45.0 ms → 97.2 ms (2.16×)** for one extra draft token. That is a discontinuity, not a gradient.

**Cause — `mmvq_mmid_max` on sm_60.** MUL_MAT_ID falls off its fast path once the batch exceeds a
per-quant-type limit (`get_mmvq_mmid_max_batch_pascal_older`, `ggml/src/ggml-cuda/mmvq.cu:114`).
The verify pass batches `n_max + 1` tokens. The model's **expert** tensors are mixed:

| `_exps` tensor type | count | limit |
|---|---|---|
| **IQ3_S** | **78** | **4** |
| IQ4_NL | 39 | 6 |
| Q6_K | 3 | 4 |
| Q3_K | 2 | 4 |
| Q4_K | 1 | 5 |

The binding constraint is the **minimum over expert types = 4**. n-max 3 → batch 4 (at the limit,
peak throughput); n-max 4 → batch 5 (over, 2× collapse). Exact match to the observed cliff.

### Predictive rule

> **optimal `--spec-draft-n-max` = min(`mmvq_mmid_max`) over the model's `_exps` tensor types − 1**

⚠️ **Read the tensor types, not the filename.** This file is named `UD-IQ4_NL` (limit 6, implying
n-max 5), but 78 of 123 expert tensors are **IQ3_S** (limit 4), so the real ceiling is 3. Unsloth
Dynamic quants mix types per tensor; the name reflects the headline type only.
Probe: `~/gguf_types.py <model.gguf>` (header-only read, never touches the tensor region).

⚠️ **Scope:** the table read here is `_pascal_older` (sm_60). Newer architectures use different
tables with higher limits, so the *cliff position* is Pascal-specific — but the *rule* (take the
min over expert types, subtract one) applies wherever a batch table gates MUL_MAT_ID.

⚠️ A prior hypothesis in this session — "IQ4_NL's limit is 4" — was **wrong** (it is 6). The
mixed-quant reading is what makes the arithmetic work.

## `-sm tensor` vs `-sm layer`, with and without MTP

| config | `-sm layer` | `-sm tensor` | gain | acceptance |
|---|---|---|---|---|
| baseline | 45.35 / 45.32 | **47.56 / 47.31** | +4.4% | — |
| MTP n-max 2 | 60.21 / 60.20 | **68.76 / 68.60** | **+14.0%** | 0.77 vs 0.76 |

**Tensor split's advantage more than triples when MTP is on**, and acceptance is unchanged
(0.77 vs 0.76) — so this is pure execution efficiency, not draft quality. Mechanism: MTP's verify
pass is a batched, compute-denser forward pass, which rewards having both GPUs work on every
tensor. VRAM placement confirms: layer split is uneven (8963/8815, 9031/9431), tensor split exact
(8955/8955, 9313/9313).

## Practical recommendation for this fleet

```
-c 8192 -fa on -np 1 -ngl 99 -sm tensor --spec-type draft-mtp --spec-draft-n-max 3
```

`-ngl 99` is **required** with `-sm tensor`: the auto-fitter aborts
(`llama_params_fit is not implemented for SPLIT_MODE_TENSOR`) and without it the load fails in a
way that looks like missing architecture support.

## Limits

- One model, one prompt, n_predict 128, greedy. Acceptance is prompt-dependent; a different
  workload will shift the accept rate though not the batch-table cliff.
- The 2.16× cycle-time jump is inferred from `mean len` and tok/s, not from kernel profiling.
  Direct confirmation would be an `ncu` trace or a build with the fallback path instrumented.
- No quality check was run on MTP output. Speculative decode should be output-identical to greedy
  by construction, but that was not verified here.

## Provenance

`.73:~/mtptest/` — `mtp.log`, `r_*.json`, `srv_*.log`; scripts `~/mtp_moe_ab.sh`, `~/gguf_types.py`.
Predictions logged before the run: `MTP_TENSORSPLIT_PREDICTIONS.md`.
