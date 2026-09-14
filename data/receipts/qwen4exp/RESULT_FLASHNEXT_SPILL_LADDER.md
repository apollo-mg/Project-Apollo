# Result — Flash-Next runs in 7.4 GB of VRAM at 8.6 tok/s, and expert spill gets *cheaper* the more of it you do

**Run 2026-09-13, 18:52:45–20:21:38, `.194`** (4× P100, sm_60), qwen4exp Stage 4. Pre-registered in
`PREREG_FLASHNEXT_SPILL_LADDER.md` (`80c87aa`, Amendment 1 `5c0e348`, both before any rung produced a number).
Driver `flashnext_residency.py --stage4`, scorer `tools/score_flashnext_spill.py`, both committed before the
first rung. buun `c7f114d34`, Flash-Next UD-IQ4_XS, `-sm layer`, `--numa distribute`, `-lv 4`, page cache
dropped before every rung. **All six rungs loaded, answered "17 × 23", and completed.**

## The ladder

| rung | `-ncmoe` | GPU MiB after load | decode 500 / 1800 / 3600 | prefill 500 / 1800 / 3600 |
|---|---|---|---|---|
| L-02 | 2 | **61,566** | 22.33 / 22.43 / 19.60 | 145.6 / 140.4 / 145.2 |
| L-04 | 4 | **59,128** | 20.30 / 20.12 / 18.56 | 132.6 / 128.1 / 133.4 |
| L-08 | 8 | **54,186** | 17.60 / 17.39 / 15.84 | 115.7 / 110.7 / 116.9 |
| L-16 | 16 | **45,094** | 13.57 / 13.60 / 12.84 | 71.7 / 65.6 / 72.1 |
| L-32 | 32 | **26,616** | 10.75 / 10.72 / 10.29 | 67.9 / 64.7 / 71.1 |
| L-48 | 48 | **7,448** | 8.64 / 8.55 / 8.24 | 56.8 / 50.6 / 57.2 |

**Every rung's KV was verified as `K (f16), V (f16)` from its own `-lv 4` log** — the first stage in this campaign
where the f16 guard had lines to inspect during the run rather than in a post-hoc reload.

## 1. The headline: a ~90 GB model class serving from 7.4 GB of VRAM

At full spill Flash-Next holds **7,448 MiB across four cards — 1,862 MiB each — and still decodes 8.64 tok/s.**
That is a configuration that fits on **one 8 GB card**, from a model whose IQ4_XS weights are 88 GB on disk.
Everything but the experts is tiny; the experts are all of the size and, at 10 active of 512, almost none of the
per-token work.

**Full spill frees 54,118 MiB for 13.69 tok/s.**

## 2. The exchange rate inverts the intuition: spill is cheapest in bulk

| rung | layers spilled vs base | MiB freed | MiB / layer | tok/s lost | **MiB freed per tok/s lost** |
|---|---|---|---|---|---|
| L-04 | 2 | 2,438 | 1,219 | +2.03 | **1,203** |
| L-08 | 6 | 7,380 | 1,230 | +4.73 | **1,562** |
| L-16 | 14 | 16,472 | 1,177 | +8.76 | **1,881** |
| L-32 | 30 | 34,950 | 1,165 | +11.58 | **3,019** |
| L-48 | 46 | 54,118 | 1,176 | +13.69 | **3,953** |

**The rate improves 3.3× from the shallowest spill to the deepest.** VRAM freed per layer is nearly constant
(1,193 MiB ± 3.1%, P-L0), so the whole effect is in the denominator: deep spill costs less per layer than
shallow spill.

**The practical consequence is the opposite of the usual tactic.** Spilling two layers to "just barely fit" is
the *worst* deal on the whole curve — 1,203 MiB per tok/s. If a configuration needs spill at all, spilling
generously is more efficient per byte than spilling minimally.

## 3. There are two regimes, and a single slope hides them

| step | marginal ms per spilled layer | implied effective GB/s |
|---|---|---|
| 2 → 4 | 2.24 | 12.3 |
| 4 → 8 | 1.89 | 14.6 |
| 8 → 16 | 2.11 | 13.1 |
| **16 → 32** | **1.21** | **22.8** |
| **32 → 48** | **1.42** | **19.4** |

**Below rung 16 the marginal cost is ~2.1 ms/layer; above it, ~1.3.** The break is sharp and holds across both
wide steps.

**A linear fit through all six points returns R² = 0.9907** — and that is the trap in this data. The linear
model *appears* excellent while the residuals carry a real structural break, because the two regimes average
out. **Quote the marginals, not the fit.**

**Why the low-spill regime is expensive is a hypothesis, not a result.** The most likely mechanism is NUMA
placement: with only a couple of layers' expert tensors on the host they plausibly land on one node
(~22.7 GB/s), and as more spill they spread across both sockets toward first-touch's 45.1 GB/s aggregate. The
implied bandwidths are consistent with that — ~13 GB/s early, ~20–23 GB/s late — but this ladder cannot
separate it from alternatives (better CPU thread utilisation at depth, GPU-side per-layer cost being removed as
CPU cost is added). **Testing it needs per-node memory placement captured during a run**, which nothing here
records.

## 4. What this does to the campaign's cost model

The model — spilled experts read from host memory, decode time linear in spilled layers — was used to reproduce
buun's ~40 tok/s on a 3090 + DDR5. **Its form is roughly right and its constant is not.**

- Predicted 0.5–1.5 ms/layer from 27.6 MB/layer/token over 22.7–45.1 GB/s. **Measured 1.2–2.2**, i.e. an
  effective **12–23 GB/s**, never the first-touch figure.
- The bandwidth-only assumption omits that the CPU must **dequantize and multiply** IQ4_XS expert weights, not
  merely read them, and that the GPU stalls on each spilled layer's result.
- **Any receipt extrapolating "if all experts spill" should use ~1.3 ms/layer/token in the deep-spill regime and
  ~2.1 shallow**, on this box, rather than a bandwidth quotient.

## 5. Prefill: a much worse mid-ladder collapse that converges by the end

Prefill falls from 145.6 to 56.8 tok/s (−61.0%) against decode's 22.33 → 8.64 (−61.3%) — **a tie at the
endpoints**. But the paths differ sharply: at rung 16 prefill was down **50.7%** where decode was down only
**39.2%**. Prefill collapses early (−38% over the 8→16 step alone) and then nearly flattens (−5.7% over 16→32).

**Hypothesis for the early collapse, untested here:** a 512-token ubatch touches nearly all 512 experts per
layer, so prefill moves few bytes per token (~2.8 MB against decode's 27.6) but enormous arithmetic — ~50 GFLOP
per layer per ubatch. The implied ~113 GFLOP/s at rung 16 is about what 20 Haswell cores do on quantized GEMM.
**Spill hands decode a bandwidth problem and prefill a compute problem**, which is why they degrade on
different schedules. Confirming it needs a CPU-side profile, not a throughput number.

## Predictions

| id | prediction | result |
|---|---|---|
| P-L0 | MiB freed per spilled layer constant within ±15% | **CONFIRMED** — mean 1,193 MiB/layer, worst deviation **3.1%** (1,165–1,230) |
| P-L1 | decode ms/token linear in `-ncmoe`, marginal 0.5–1.5 ms/layer | **FALSIFIED** — 1.519 ms/layer, R² = 0.9907. See below: the miss is 1.3% and is *not* the finding |
| P-L2 | decode at rung 48 in 8–15 tok/s | **CONFIRMED** — **8.64 tok/s** |
| P-L3 | prefill's fractional slowdown < decode's | **CONFIRMED as coded, a tie in substance** — 61.0% vs 61.3%, a margin of 0.3 points |
| P-L4 | rung 2 under `--numa distribute` within ±10% of S3-X4's 21.28 | **CONFIRMED** — 22.33 tok/s, **+4.9%** |

**P-L1's verdict is an artifact of where the band's edge fell.** The fitted 1.519 misses the 1.5 ceiling by
**1.3%** — well inside what a different rung spacing would move. **The substantive result is that the
single-slope model is wrong in shape**, with a 1.7× break at rung 16 that a 0.99 R² conceals. Had the band been
drawn at 1.6 the prediction would have "passed" while being just as wrong about the physics. Recorded this way
deliberately: the falsification is real but trivial; the curvature is the finding.

**P-L3 is scored as written and should be read as a tie**, the same shape as test 10's P-C2 — confirmed by the
rule, with a margin too small to mean anything. The informative part is the mid-ladder divergence in §5, which
the endpoint comparison the prereg specified cannot see.

## Deviations and limits

- **Amendment 1: `-lv 4` was on during the timed requests**, not just at load. Uniform across all six rungs, so
  the marginals and exchange rate are unaffected; it lands in the intercept. **P-L4 was demoted in advance** from
  a numa control to a sanity check because rung 2 differs from `S3-X4` in two ways (numa pin *and* `-lv 4`); its
  +4.9% is consistent with Stage 1's +6.1% for `--numa distribute`, but is not clean attribution.
- **The baseline is rung 2, not zero spill** — `-ncmoe 0` does not fit (Stage 3 P-S1). The 44.4 ms intercept is
  an extrapolation through a shifted origin and is **not** a measured zero-spill figure.
- **`offloaded 49/49 layers` is identical on every rung** while VRAM ranges 61,566 → 7,448 MiB. That log line
  reports layer offload and says nothing about whether a layer's experts were overridden to CPU — **it cannot be
  used as a spill probe** ([[readiness-probes-lie]]).
- **One model, one quant, one box.** IQ4_XS on `.194`'s DDR4-2133 and two Xeon E5-2650v3. The *shape* — two
  regimes, constant MiB per layer, an improving exchange rate — is the transferable claim; the milliseconds are
  not.
- **Both mechanisms in §3 and §5 are hypotheses**, labelled as such, with the measurement each would need.
- Fidelity is unchanged across the ladder: spill moves tensors, not weights. This is not a quality test.

Artifacts: `spill/` — `results.jsonl`, `driver.log`, `kvsum_server_L-*.txt` (per-rung KV and offload lines).
