# Pre-registered predictions: TQ weight types on sm_60, pre/post PR #256

**Logged 2026-08-03 BEFORE any run.** Node `.73`, 2× Tesla P100-PCIE-16GB (sm_60), 150 W / 1063 MHz,
persistence mode ON. Builds compared:

| label | tree | commit | TQ fixes |
|---|---|---|---|
| OLD | `~/tom_rebase` | `d0e2a8b64` | **absent** |
| NEW | `~/tom_sync`   | `6aa97d810` (post-#256, v116) | `c29f0d1cd` + `2293b1da6` **present** (verified by `merge-base --is-ancestor`) |

The two fixes:
- `c29f0d1cd` — disable the fused TQ3_1S `mul_mat` kernel (DSv4 CUDA garbage output)
- `2293b1da6` — gate fused TQ `mul_mat` paths on contiguous `src1`/`dst`

## Models under test (header probe, never read whole)

| file | arch | blk | MTP | TQ type id | TQ tensors | size |
|---|---|---|---|---|---|---|
| `Qwen3.6-27B-MTP-TQ4_1S.gguf` (MidnightPhreaker) | qwen35 dense | 65 | **yes**, `nextn_predict_layers=1` | **46** = TQ4_1S | 180 | 19.93 GiB |
| `Qwen3.6-35B-A3B-UD-Q8_K_XL-TQ4_1S.gguf` (MarcelloG) | qwen35moe | 40 | **no** | **45** = TQ3_1S | 108 (72 `_exps`, **36 non-expert**) | 21.89 GiB |

⚠️ **The MoE file is named `TQ4_1S` but carries tensor type 45, which on TheTom's fork is `TQ3_1S`** —
the exact type `c29f0d1cd` disables. Filenames are not authoritative for TQ interchange; the type id is.

Why the fix is live here: expert tensors dispatch through `MUL_MAT_ID`, which per Tom's own comment
already uses "dequant-to-f16 cuBLAS path only (no mmvq/mmq kernels)". The **36 non-expert** type-45
tensors go through plain `ggml_cuda_mul_mat` — the fused path `c29f0d1cd` removes.

## Predictions

**P-TQ1 (0.55): the MoE produces visibly degraded/incoherent output on the OLD build at temp 0.**
Mechanism: 36 non-expert TQ3_1S tensors route through the fused warp-scalar kernel Tom measured
diverging ~2%/layer. Held near a coin flip deliberately — Tom root-caused on `blk.N.attn_q_a`, a
**DeepSeek MLA low-rank bottleneck that qwen35moe does not have**, and only 36/733 tensors are
affected here versus DSv4 where TQ3_1S carries all attn+ffn weights. Divergence may stay under the
coherence threshold.

**P-TQ2 (0.85): the MoE is coherent on the NEW build.** The fix routes TQ3_1S `MUL_MAT` to
`dequantize_tq3_1s` + cuBLAS, which Tom verified correct against a CPU oracle.

**P-TQ3 (0.7): NEW is slower than OLD on the MoE, by 5–20%.** Replacing a fused kernel with
dequant-to-f16 + cuBLAS costs a materialised f16 buffer and extra memory traffic. This is the price
of the correctness fix, and nobody has measured it on Pascal.

**P-TQ4 (0.7): the dense TQ4_1S 27B is SLOWER than the same model at Q6_K** (13.36 t/s, `-sm tensor`,
measured today). Counterintuitive, so the mechanism explicitly: TQ4_1S is only **6.5% smaller** on
disk (19.93 vs 21.31 GiB), so there is almost no bandwidth win to collect, while TQ decode does a
per-block WHT rotation + centroid dot product — strictly more ALU than Q6_K dequant. Pascal is
ALU-poor relative to its bandwidth, so a 6.5% traffic saving should not pay for the extra math.

**P-TQ5 (0.6): MTP on the dense TQ4_1S yields a smaller multiplier than the 1.487× measured on the
IQ4_NL MoE.** Mechanism: `2293b1da6` gates the fused TQ path on **contiguous `src1`/`dst`**, and MTP
verify batches are precisely where non-contiguous `src1` arises — so some fraction of MTP steps fall
back to the slow path on the NEW build. This predicts an interaction between the correctness fix and
speculative decoding that would not show up in any single-token benchmark.

## The 2×2 coherence gate is diagnostic, not just a safety check

Running both models on both builds distinguishes four outcomes:

| OLD | NEW | reading |
|---|---|---|
| coherent | coherent | the fused-kernel bug does not manifest on `qwen35moe` |
| **garbage** | coherent | Tom's DSv4 bug reproduces on a second arch **and** on Pascal — a real confirmation |
| **garbage** | **garbage** | the file is not Tom-format TQ3_1S; type 45 means something else in the producing fork — **enum-collision interop hazard confirmed** |
| coherent | garbage | the fix broke something; would need reporting immediately |

## Scoring rules (fixed now)

- Coherence judged on temp-0 text, K=2 identical prompts, both builds same prompt.
- Throughput K=3 after a discarded warm draw; report full spread, not a mean.
- `-ngl 99` pinned explicitly on every run (`-sm tensor` aborts the auto-fitter — `TENSOR_SPLIT_NGL`).
- CUDA error count grepped from every server log; a load failure is a result, not a missing datum.
- Clock state recorded: 150 W / 1063 MHz, persistence ON.
