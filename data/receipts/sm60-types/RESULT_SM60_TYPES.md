# Result -- on sm_60, IQ2/IQ3 weights run at 0.29-0.36x q8_0's bandwidth per byte at decode; summing measured kernel times per tensor explains the whole GSQ-RCO vs UD-Q2 decode gap (113 %), and 95 % of that gap is 192 small hyper-connection matrices, not the IQ experts

**2026-09-29.** Pre-registration `PREREG_SM60_TYPES.md` (`90dc521`), with Deviation 1 (`89f2a13`, a parser fix; the
raw data and rules were unchanged). Runner `run_sm60_types.sh`, analysis `analyze_sm60_types.py`, output
`RESULT_sm60_types.json`.

- **Raw:** `raw/perf_{E,P}_b{0..5}.txt`, 289 timed cases each, blocks E P P E E P; `raw/decode.jsonl`, 72 rows.
- **Tensor tables:** `tables/`.
- **Host and build:** .194 GPU 0 for kernels, 4 GPUs for decode; buun `0b2789f23` (fleet libraries' md5 unchanged
  by the test build); **E** = 150 W / 1063 MHz, **P** = 150 W / 1328 MHz, read back per block.

## Registered verdicts

| # | claim | result |
|---|---|---|
| T1 | IQ2/IQ3 below 0.7x q8_0's GB/s at n=1 | **holds.** 0.29-0.36x |
| T2 | the IQ types gain >= 10 % from the clock and q8_0 < 5 % | **does not hold.** IQ +13.2 % but q8_0 +6.4 %: every type gains |
| T3 | BF16 >= 1.5x Q8_0's time at both hyper-connection shapes | **does not hold.** 3.55x at k=320, 1.35x at k=10240 |
| T4 | the kernel sum explains >= 50 % of the file gap | **holds.** predicted +6.42 ms/token, measured +5.68 (113 %) |
| T5 | GSQ gains at least as much from the clock as UD | **holds, barely.** +20.2 % vs +19.3 % |

## The per-type table (m=4096, k=14336, stock shape; median of 3 blocks per clock)

| type | n=1 us | **GB/s at 1063** | GB/s at 1328 | n=4 us | n=512 us |
|---|---:|---:|---:|---:|---:|
| f32 | 419.8 | 560 | 574 | 692 | 9,091 |
| f16 / bf16 | 284.6 | **413** | 437-441 | 773 | 11,341 |
| q4_1 | 121.1 | 303 | 312 | 212 | 11,312 |
| **q8_0** | 216.9 | **288** | 306 | 287 | 10,413 |
| q5_1 / q4_0 / q5_0 | 137-175 | 231-260 | 243-275 | 243-278 | ~10,500-11,300 |
| iq4_nl / iq4_xs | 142-149 | 221 | 234 | 230-240 | 11,400 |
| q5_K / q4_K / q6_K | 170-278 | 174-210 | 184-218 | 319-391 | 9,750-10,780 |
| mxfp4 | 172.1 | 181 | 191 | 252 | 11,386 |
| q2_0 (g64) | 117.7 | 140 | 156 | 211 | 10,476 |
| q2_K / q3_K | 185-246 | 102-104 | 110-114 | 388-393 | 9,630-10,740 |
| **iq3_xxs / iq3_s** | 217-251 | **101-104** | 116-118 | 326-361 | 12,560 |
| **iq2_xxs / iq2_xs / iq2_s** | 183-198 | **83-95** | 93-106 | 288-307 | 12,540 |
| iq1_s / iq1_m | 167-185 | 69-70 | 80 | 288-293 | 12,540 |


- **At batch 1, fewer bits is not faster on a P100.** An IQ2 file moves a quarter of q8_0's bytes and takes nearly the
  same time per matrix (183-198 us vs 217). Weight bandwidth runs from 413 GB/s (f16) down to 69 GB/s (iq1), against
  HBM2's 732.
- **Every type gains from the core clock.** The memory clock is fixed, so no batch-1 kernel here is purely bandwidth-bound:
  - the IQ types gain the most, +13 % median, consistent with codebook unpacking under emulated dp4a (sm_60 is
    below `GGML_CUDA_CC_DP4A 610`);
  - but q8_0 (+6.4 %) and f16 (+5.9 %) gain too. T2 fails on that leg.
- **n=4 (MTP verification width) costs little for the quantized types** (q8_0 217 -> 287 us). For f16/bf16 it costs
  2.7x (285 -> 773 us). The float path does not batch as well.
- **Prefill (n=512) runs 9-12.6 ms for every type**; IQ types are the slowest (12.5 ms) through the dequantize-then-BLAS
  path.

## The Flash-Next shapes, and the file-level model

**The hyper-connection matrices:**

| shape | BF16 | Q8_0 |
|---|---:|---:|
| `hc_up`: k=320, m=10240 | **82.2 us** | 23.1 us |
| `hc_down`: k=10240, m=320 | 21.0 us | 15.5 us |

At `hc_up`'s shape BF16 is 3.55x slower. BF16 at the stock shape matches f16 exactly, so BF16 itself is not the
problem; the short rows are. `PREREG_HC_Q8.md`'s control confirmed it with F16 and F32.

**Expert matmuls (MUL_MAT_ID, 512 experts, 10 used, n=1):**
- 58-94 us per call, weakly dependent on type (IQ gate/up 83-94 us, IQ4_NL down 73, Q2_0 down 64);
- that is 48 layers x 3 calls, ~11-13 ms per token in either file.

**Kernel sum per token vs measured token time:**

| file | matmul sum at 1063 | measured | share | at 1328 | measured |
|---|---:|---:|---:|---:|---:|
| UD-Q2_K_XL | 35.26 ms | 47.44 ms (21.08 tok/s) | 74 % | 29.79 ms | 39.75 ms (25.15 tok/s) |
| GSQ-RCO IQ3_XXS | 41.68 ms | 53.12 ms (18.82 tok/s) | 78 % | 35.03 ms | 44.20 ms (22.63 tok/s) |

**The predicted gap by tensor family** (GSQ minus UD, ms per token at 1063):

| family | ms/token |
|---|---:|
| **hyper-connections** | **+6.13** |
| attention / ssm / other | +0.39 |
| output | +0.20 |
| shared expert | +0.08 |
| routers | -0.08 |
| experts | **-0.31** |
| **total** | **+6.42** |

The measured gap is +5.68 ms. The kernel sum over-predicts it slightly, which is expected: it ignores overlap and
the non-matmul ops.

## What it means

- **What to look at in a file on sm_60:**
  - **dense tensor types and shapes**, which are read on every token (4.4-4.7 GB of Flash-Next's per-token reads);
  - **not the expert codebook.** With 10 of 512 experts active, GSQ-RCO's IQ2/IQ3 experts cost *less* than UD's
    IQ2_XS/IQ3_XXS/IQ4_NL ones.
- **The GSQ-RCO penalty is 192 small BF16 matrices** (1.26 GB/token) in a shape the float mat-vec kernel handles badly.
  `RESULT_HC_Q8.md` converts them and measures the effect directly.
- **The clock matters for decode on this box:** +19-20 % for both files from 1063 -> 1328 MHz, twice what
  `qwen4exp/RESULT_FLASHNEXT_MTP_CLOCK.md` measured for plain UD-Q2 decode (~11 %). That run used `-c 8192` and a
  different request mix. The discrepancy is noted here, not resolved.
- **A process note, not a result:** after each fresh server, the first ~6 requests ran 5-10 % slow (UD-Q2 18.7-19.8
  tok/s, then a flat 21.07-21.10). **`NOTE_WARMUP_DIAGNOSIS.md` shows this is page faults, not warm-up.** The
  mmapped 28.8 GB `per_layer_token_embd` is read from SATA on each token's first use. Pre-reading it gives the cached
  rate from the first request. The medians here are dominated by cached requests (2 of 3 blocks per file).

## Not established

- One GPU model (P100, sm_60) and one build. The kernel table says nothing about Volta and later, which have real dp4a,
  tensor cores and CUDA graphs.
- The file model uses MUL_MAT(_ID) only; attention, SSM, norms and hyper-connection mixing ops are the remaining
  22-26 %.
