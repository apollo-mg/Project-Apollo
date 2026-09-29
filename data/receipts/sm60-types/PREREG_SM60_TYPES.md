# Pre-registration: what each weight type costs on sm_60 at decode, and whether that explains the GSQ-RCO vs UD-Q2 gap

**Registered 2026-09-29, before any row.** Today (`viability/RESULT_SWIFT_FLASHNEXT.md`) base Flash-Next GSQ-RCO IQ3_XXS
put 3 GB less on the GPUs than UD-Q2_K_XL and decoded **11 % slower** (18.48 vs 20.8 tok/s). The receipt left the cause
open with two candidates. Mark picked this as tonight's run: "I can already guess it'll end up leading us down some
kind of rabbit hole".

**Prior art checked:** `ledger_precheck.py "test-backend-ops perf mul_mat per quant type GB/s"` -> no per-type table on
this fleet. Related:
- `pulsar/PASCAL_MMID_GUARD_COST.md`: a Pascal `mul_mat_id` guard in another fork halved MoE decode. I checked that
  it is **absent** from buun `0b2789f23`: at batch 1 the MoE path is MMVQ with ids, and only fusion is disabled on
  Pascal (`ggml-cuda.cu`, "fusion is not universally faster on Pascal");
- `qwen4exp/RESULT_FLASHNEXT_MTP_CLOCK.md`: plain decode of UD-Q2 loses ~10 % at the 1063 MHz pin;
- memory `pascal-never-uses-cuda-graphs`: every kernel is launched one by one on sm_60.

**What this adds:** the first per-type, per-shape kernel table on sm_60, and a test of whether kernel times predict a
whole file's decode speed.

## What the tensor tables already show (read before registration; no timing involved)

Per decoded token, only 10 of 512 experts run, so **dense tensors dominate the bytes read**:

| per token | UD-Q2_K_XL | GSQ-RCO IQ3_XXS |
|---|---:|---:|
| weights read (2-D matmuls, experts at 10/512) | 4.43 GB | 4.68 GB |
| of which BF16 | 0.04 GB | **1.53 GB** |

- The difference is concentrated in the **192 hyper-connection matrices** (`hc_{attn,ffn}_{up,down}`, 10240x320 and
  320x10240, four per layer). They are **BF16 in GSQ-RCO and Q8_0 in UD-Q2**: 1.26 GB vs 0.67 GB per token.
- The 48 routers are BF16 in GSQ (F32 in UD). The experts are IQ2/IQ3/IQ4_NL/Q2_0 in GSQ and IQ2_XS/IQ3_XXS/IQ4_NL
  in UD.
- So the two candidates from the Swift receipt have a concrete test: BF16 matrix-vector (sm_60 has no native BF16)
  against IQ unpacking under emulated dp4a (sm_60 is below `GGML_CUDA_CC_DP4A 610`).

## Instrument

- **Host and build:** .194, GPU 0 only for kernels, buun `0b2789f23` (`~/buun-0b278`). `test-backend-ops` built in
  `build_sm60`; the fleet libraries' md5 were checked unchanged before and after.
- **Case list:** a copy of `test-backend-ops` (`~/test-backend-ops-fn`) adds 58 perf cases for Flash-Next's actual
  decode shapes (`fn_cases.py` -> `fn_cases.inc`, generated from both files' tensor tables):
  - 51 dense `MUL_MAT` (type, k, m, n=1);
  - 7 `MUL_MAT_ID` for the expert tensors, 512 experts, 10 used, n=1.
  The stock perf list is unchanged: every type at m=4096, k=14336, n = 1, 2, 3, 4, 5, 8, 512. The source tree was
  restored after the build.
- **Clock configs** (switched live, read back before each block): **E** = 150 W / 715,1063 (fleet default);
  **P** = 150 W / 715,1328. Blocks E P P E E P, each running `perf -o MUL_MAT` and `perf -o MUL_MAT_ID -p n_mats=512`.
  The efficiency config is restored on exit.
- **File-level decode:** UD-Q2_K_XL and GSQ-RCO base, each on a fresh verified server (the Swift run's flags:
  `-ngl 99 -sm layer -ts 1,1,1,0.6 -c 16384`, f16 KV, `-np 1`, 4 GPUs). One warm-up, then the 6 fixed speed prompts x 2
  (`viability/swift_fn_probe.py`) in blocks **E, P, E**.
- **Instrument checks before registration:**
  - one smoke run each of `q8_0` and `iq3_s` at the stock shape, to learn the output format (the `iq3_s` timing
    was seen: 251 us);
  - a MUL_MAT_ID case count.

## The model (`analyze_sm60_types.py`)

- **Predicted matmul time per token for a file** = sum over its 2-D weights of the measured time of that exact
  (type, k, m) case (the shared experts, routers and hyper-connections are 2-D and included), plus the expert
  tensors' MUL_MAT_ID times (48 layers x 3).
- Excluded: `token_embd`, `per_layer_token_embd` (lookups, host-resident) and `ssm_conv1d` (a conv).
- **Measured time per token** = 1 / decode tok/s, median of the 12 probe requests.
- Weight bandwidth for the stock shape = m x k x (bytes per block / block size) / time.

## Predictions (self-tested on synthetic perf output before any row)

| # | claim | rule | confidence |
|---|---|---|---|
| T1 | **IQ2/IQ3 are slow per byte on sm_60** | stock shape, n=1, E: iq2_xxs, iq2_xs, iq2_s, iq3_xxs and iq3_s each below 0.7x q8_0's weight GB/s | 0.6 |
| T2 | **...because they are compute-bound** (emulated dp4a) | E -> P (+24.9 % clock): median GB/s gain of those five >= +10 %, and q8_0's < +5 % | 0.5 |
| T3 | **BF16 is slow per byte on sm_60** | at both hyper-connection shapes (k=10240/m=320 and k=320/m=10240), BF16 time >= 1.5x Q8_0 time (its bytes are 1.88x) | 0.5 |
| T4 | **Kernel times explain the file gap** | predicted per-token matmul time, GSQ minus UD, >= 50 % of the measured per-token gap, at E | 0.4 |
| T5 | **GSQ is the more clock-bound file** | decode gain E -> P: GSQ >= UD | 0.5 |

**Reported without a prediction:**
- the full per-type table at n = 1, 4 (MTP verification width) and 512 (prefill), at E and P;
- the attribution of the predicted gap by tensor family (hyper-connections, routers, experts, attention);
- the share of each file's measured token time that the matmul sum accounts for.

**If T3 and T4 hold, the causal test is a follow-up:** convert GSQ-RCO's 192 hyper-connection tensors from BF16 to
Q8_0, change nothing else, and measure decode.

## Deviations

Any change after the first row gets a numbered Deviation here before the affected rows run.
