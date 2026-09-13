# Prereg — the expert-spill cost curve: what does one layer's experts on the host actually cost? (qwen4exp, Stage 4)

**Written 2026-09-13 ~18:50, before any rung runs.** Follows `PREREG_FLASHNEXT_RESIDENCY.md` Stages 1–3b and
`RESULT_FLASHNEXT_RESIDENCY.md`. Mark's go, this session, after test 11 freed `.194`.

## The question

Stage 1 found **spilling experts costs ~5.5% per layer where spilling whole layers costs ~38%** — measured at
two points, not as a curve. Stage 3 then found the machine's best Flash-Next configuration is UD-IQ4_XS at
`-ncmoe 2` (21.28 tok/s, 61,566 MiB). Both leave the same question open:

**What is the exchange rate — how much VRAM does one spilled layer's experts buy back, and what does it cost in
tokens per second?** That is the number that decides how much context, KV or model a box this size can hold, and
it is the number the campaign has been extrapolating without measuring.

**A second question rides along, and it is the falsifiable one:** the campaign's cost model — spilled experts are
read from host memory at an effective bandwidth, so decode time per token should be *linear* in the number of
spilled layers — was used to reproduce buun's ~40 tok/s on a 3090 + DDR5. **It has never been tested against a
measured curve.** This ladder tests it.

## Setup

- **Node `.194`**, all four P100s, buun **`c7f114d34`** (the build every Stage 1–3b row used), `-sm layer`.
- **Model: Qwen3.8-Flash-Next UD-IQ4_XS only.** GGUF-only, deliberately: the EXL3 snapshot stages a 31 GB temp
  file and `.194` has **61 GB free** — that is the ENOSPC that already cost Stage 2 a run
  ([[buun-safetensors-disk-staging]]).
- **Flags pinned to Stage 3's**, so the rungs are comparable to `S3-X4`: `-c 4096 -np 1 -b 2048 -ub 512 -fa on
  -fit off -sm layer -ctk f16 -ctv f16 -ngl 99`, `GGML_CUDA_ALLREDUCE=internal`, page cache dropped before each
  rung, 3 reps at prompt lengths 500 / 1,800 / 3,600, 128 tokens generated.
- **Rungs (geometric, six):** `-ncmoe` ∈ **{2, 4, 8, 16, 32, 48}**.

**`n_layer = 48` is verified, not assumed** — read from `flashnext_res/verify/load_P-IQ4.log` (`block_count 48`,
`n_expert 512`, `n_expert_used 10`) before writing this. So **rung 48 is genuinely "every layer's experts on the
host"**. The EXL3 snapshot's 50/50 layer count is its own extra head layer and does not apply here.

### Host memory placement is pinned, and this is the reason

`-ncmoe N` places those layers' expert tensors on the **CPU backend** — the matmul runs on host threads out of
host RAM, so the binding resource is **host memory bandwidth**, not PCIe. Stage 1's triad measured it, and the
numbers are not interchangeable:

| placement | GB/s |
|---|---|
| node-local, 10 threads | 22.68 |
| **cross-socket, 10 threads** | **7.00** |
| `interleave=all`, 20 threads | 27.90 |
| **free / first-touch, 20 threads** | **45.14** |

**Every rung runs `--numa distribute`, declared here.** Unpinned, spilled-expert reads land on whichever node the
kernel chose, and a slope that misses the cost model would have two explanations — bandwidth or placement — with
no way to separate them. `--numa distribute` is also the realistic configuration for a four-card two-socket box
and was already characterised in Stage 1 (+6.1% decode, −8–9% prefill on `P-IQ4-numa`).

**Consequence, declared:** `S3-X4` ran *without* it, so **rung 2 is re-measured rather than reused**, and that
re-measurement doubles as a paired numa control at this operating point (P-L4).

### The KV check is real this time

The vacuous-f16-guard defect has now appeared **three times** (`PREREG_FLASHNEXT_RESIDENCY.md` Amendment 2,
`PREREG_EXL3_USABLE.md` Amendment 5): at default verbosity buun's server prints no `K (…)` / `V (…)` lines, so
"abort if a found type is not f16" has nothing to inspect. **Every rung runs at `-lv 4`, and the driver aborts
unless the parsed types are exactly `['f16']` — an empty list now fails.** The fix costs a flag.

## Predictions

| id | prediction |
|---|---|
| P-L0 | **VRAM freed per spilled layer is constant within ±15%** across the ladder — expert tensors are uniform across layers, so each rung should free the same MiB per layer |
| P-L1 | **Decode time per token is linear in `-ncmoe`**, with a marginal cost of **0.5–1.5 ms per spilled layer per token** |
| P-L2 | **Decode at rung 48 lands between 8 and 15 tok/s** |
| P-L3 | **Prefill's fractional slowdown from rung 2 to rung 48 is smaller than decode's** — a 512-token ubatch amortizes each expert read over many tokens, where decode reads them for one |
| P-L4 | **Rung 2 under `--numa distribute` lands within ±10% of `S3-X4`'s 21.28 tok/s** (same flags, no numa pin) |

**Where P-L1 and P-L2's numbers come from, so they can be checked rather than trusted.** Per layer per token the
active experts are 10 × 3 matrices × (2,560 × 640) = **49.15 M weights**; at IQ4_XS's ~4.5 bpw that is
**~27.6 MB per layer per token**. At 22.7–45.1 GB/s (the table above) that is **0.61–1.22 ms**, widened to
0.5–1.5 for quantizer and overhead slack. Rung 2 fixes the intercept; rung 48 then follows.

**P-L1 is the one that can embarrass the campaign, and that is why it is here.** If the curve is not linear —
if it bends up (contention, thread scaling) or flattens (an amortization we have not modelled) — then the
extrapolation that reproduced buun's 3090 number was luck, and every "if all experts spill" estimate in the
receipts needs re-deriving. Recorded whichever way it lands.

## The deliverable is an exchange rate, not a curve

Scored and reported as a table of **MiB freed per tok/s lost**, per rung, in the shape test 10 used for VRAM. The
practical question — *can I buy back enough VRAM for more context, and what does it cost?* — should be readable
without interpolating a plot.

## Declared in advance

- **The intercept is unmeasured.** Stage 3's P-S1 found card 0 at 15,515 of 16,384 MiB at `-ncmoe 2`, so
  `-ncmoe 0` does not fit on IQ4_XS. **The baseline is rung 2, not zero spill.** Any zero-spill figure is an
  extrapolation through a shifted origin and will be labelled as one, never reported as measured.
- **One model, one quant, one box.** IQ4_XS on `.194`. The slope is in *this* machine's DDR4-2133 and these two
  Xeons; the *shape* is the transferable claim, not the milliseconds.
- **Wall-clock abort rule.** High rungs load slower *and* decode slower. **Cap: 2 h 15 m from launch.** If it
  expires, the receipt reports the rungs completed and says so; each rung persists its own rows
  ([[incremental-persistence-rule]]), and an `arm_done` row makes a rung skippable on restart.
- **Not a quality test.** Spill changes placement, not weights; every rung must still answer "17 × 23" or abort.

**Driver:** `flashnext_residency.py --stage4`, extending the file every prior stage used rather than a new one.
**Scorer:** `tools/score_flashnext_spill.py`, committed with this prereg, before the first rung.
