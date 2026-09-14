# Result — the dense sm_60 fallback reaches ~30% of FP16 peak, and the memory argument for a new kernel is weak

**Run 2026-09-14 16:22–16:46, `.194`**, two P100s (`CUDA_VISIBLE_DEVICES=0,1`), buun `c7f114d34`,
`-sm layer -fit off -ngl 99 -c 4096 -b 2048`, f16 KV, `GGML_CUDA_ALLREDUCE=internal`. Pre-registered in
`PREREG_SM60_DENSE_PATH.md` (`4be4453`), committed before any arm ran. Prefill of a fixed 2,048-token
wikitext prompt, median of 3 reps. **Every arm's three reps agreed to within 0.3 tok/s.**

For an80sPWNstar's sm_60 kernel thread.

## The sweep

| `-ub` | Q6_K prefill | Q6_K peak VRAM | EXL3 3.00bpw prefill | EXL3 peak VRAM |
|---|---|---|---|---|
| 8 | 27.7 tok/s | 21,500 MiB | 18.1 tok/s | 10,660 MiB |
| 64 | 58.4 | 22,204 | 74.1 | 11,032 |
| 128 | 71.4 | 22,248 | 88.5 | 11,080 |
| 256 | 97.5 | 22,336 | 100.0 | 11,176 |
| **512** | **106.3** | 22,516 | **106.3** | **11,372** |

## Predictions

| id | prediction | result |
|---|---|---|
| P-H1 | Q6_K peak VRAM grows monotonically with `-ub` | **CONFIRMED** — monotonic, but the whole 64× sweep costs only **1,016 MiB** |
| P-H2 | EXL3 peak VRAM flat within 500 MiB | **FALSIFIED** — it grows **712 MiB**, nearly as much as the dense path |
| P-H3 | Q6_K OOMs at some `-ub` ≤ 512 on two cards | **FALSIFIED** — nothing failed; peak 22,516 of 32,768 MiB, ~10 GB spare |
| P-H4 | Q6_K prefill improves with `-ub` through 128 | **CONFIRMED** — 3.8× from `-ub` 8 to 512 |

## 1. The memory argument for a new kernel is weak

P-H1 is technically confirmed and practically uninteresting: **a 64× increase in micro-batch costs about
1 GB.** P-H2's failure matters more — **EXL3's "256 MB bounded chunks" does not produce flat VRAM either**
(712 MiB span). Whatever grows with `-ub` is largely common to both paths, so it is not the dequantisation
pool the design note points at.

**P-H3 also refines an earlier claim.** `RESULT_EXL3_SM60_INFERENCE.md` attributed a Q6_K OOM to this path.
That OOM was in **`llama-perplexity` at `-c 512`**, a different graph shape; at `-c 4096 -b 2048` in
`llama-server` the same model on the same two cards has ~10 GB of headroom. **The dequant path is real; the
memory pressure is configuration-specific, not a general property.** An HGEMM-56 pitch built on "prevents
OOMs" would be overstating it.

## 2. Both paths converge on exactly the same ceiling

At `-ub 512`, **Q6_K and EXL3 both reach 106.3 tok/s** — to 0.1 — despite EXL3 carrying **half the VRAM**
(11,372 vs 22,516 MiB) and a different quantisation entirely. Both ultimately hand fp16 matrices to BLAS.

**That convergence suggests 106.3 tok/s is a property of the fp16 GEMM path on this hardware, not of
dequantisation overhead** — which is exactly the thing a fused packed-half2 kernel would bypass.

## 3. The number a kernel would have to beat, and the headroom

Prefill of 2,048 tokens through a 27B model is ≈ 2 × 27e9 × 2048 = **110.6 TFLOP**. At 106.3 tok/s that is
19.3 s, so **≈ 5.7 TFLOPS achieved**. GP100's FP16 peak is **19.0 TFLOPS**, and under `-sm layer` one card
computes at a time, so the relevant peak is one card's.

**≈ 30% of FP16 peak.** Well-tuned GEMM normally reaches 70–90%, so **the headroom is real and roughly
2–3×** — but it is a *throughput* argument, not a memory one.

**Caveats on that estimate, which is arithmetic and not a profile:** 2·N·T ignores attention and treats all
27B parameters as participating; layer split means the second card idles rather than adding peak; and no
profiler was run, so the 30% is an upper-bound-style figure rather than a measured occupancy.

## 4. Incidental: EXL3 loses at tiny micro-batch and wins in the middle

At `-ub 8` EXL3 is **slower** (18.1 vs 27.7) — its chunked reconstruction has nothing to amortise over. By
`-ub 64` it leads (74.1 vs 58.4) and stays ahead until the two converge at 512. **Anyone benchmarking EXL3
prefill at small `-ub` will draw the wrong conclusion**; test 10's KLD arms all ran at `-ub 8`.

## Limits

- **This measures memory behaviour and throughput, not which kernel launched.** Proving MMQ is absent needs
  a profiler or a `GGML_CUDA_FORCE_MMQ` build; neither was run, and the prereg said so in advance.
- Peak VRAM is `nvidia-smi` sampled at 2 s and under-reports brief spikes.
- One model per format, one prompt length, two cards, prefill only. Decode is a different path.
- Q6_K and EXL3 3.00bpw are **not** fidelity-matched; EXL3 is here as a *memory-scaling and path* control,
  not as a quality comparison.

Artifacts: `densepath/` — `rows.jsonl`, `run.log`, `densepath.sh`.
