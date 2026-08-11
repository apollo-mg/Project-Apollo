# Pre-registration — MoE expert cache on RDNA4: HIP vs Vulkan, matched

Written **before** either build completed. Target: giveen/llama-cpp-turboquant
`moe-cache` (the branch behind turboquant PRs #287/#288/#289).

**Why this is worth doing:** Jabba built the Vulkan and Metal cache paths and
cannot test them. Tom and Jabba cover CUDA; h4rm0n1c plausibly covers Metal;
Defilan's Strix Halo is a *unified-memory* APU where the CPU→GPU copy this
feature exists to avoid is nearly free. **A discrete AMD card on PCIe is the
regime where the feature should show its largest win, and nobody else in the
group has one.** Same card, same model, two backends is the comparison this
group is otherwise missing.

## Hardware and the constraint that shapes the design

RX 9070 XT, **16 GiB VRAM**, gfx1201, RADV (Mesa) for Vulkan / ROCm 7.2.4 for HIP.
Host: 5700X3D, **32 GiB DDR4-3600** (~57 GB/s, dual channel).

The host RAM is the binding constraint, not the VRAM:

- `Darwin-36B ... i1-Q6_K` — 26.6 GiB. Best *shared* model (120/120 experts
  uniformly Q6_K) but leaves ~5 GiB for OS + page cache on this box.
- `Qwopus3.6-35B-A3B-v1.i1-Q4_K_M` — **19.7 GiB**. Experts are mixed
  (100 × Q4_K + 20 × Q6_K), so it also exercises the mixed-type dispatch path.

**Plan: Qwopus Q4_K_M as the primary arm here**, Darwin Q6_K only if headroom
allows. Darwin stays the recommendation for testers with more RAM — the group's
shared-model choice and this box's runnable choice are not the same thing, and
conflating them was an error in my earlier advice.

**Do not copy Jabba's `--no-mmap`.** He has the RAM for it; forcing a 20–27 GiB
model fully resident in 32 GiB alongside the OS invites the OOM killer. mmap on,
let the page cache do its job.

## The confound that has to be controlled

`arg.cpp:839` — *"explicit MoE cache mode disables weight repacking."* Per the
help text: `auto` **preserves** repacking; `on`, `soft` and `N` do **not**.

So `auto` vs `soft` moves two variables at once. The controlled ladder is
**`off` → `N`**, both repacking-disabled, at a **fixed MiB budget** so the arms
are matched and so other testers on other hardware can match them too.
`auto` is measured but reported separately, not as the baseline.

## Predictions

| ID | Prediction | Confidence |
|---|---|---|
| **P1** | The HIP build completes for gfx1201 without source edits | 0.75 |
| **P2** | The Vulkan build completes without source edits | 0.80 |
| **P3** | Vulkan MoE cache **runs without crashing** on first attempt (author could not test it on any AMD card) | 0.50 |
| **P4** | At a matched cache budget, `N` beats `off` on TG by **≥15%** on at least one backend | 0.70 |
| **P5** | HIP beats Vulkan on TG by **≥20%** (ROCm is the tuned path on AMD) | 0.65 |
| **P6** | The +30–50% TG Jabba measured on CUDA does **not** reproduce at that magnitude here | 0.60 |
| **P7** | Output is **byte-identical** between `--moe-cache off` and `--moe-cache N` at temp 0, same seed — a cache is a residency optimisation and must not change results | 0.70 |

**P7 is the one that matters most.** Every other number is performance; P7 is
correctness. A cache that speeds things up and quietly changes logits is the
failure mode this campaign keeps finding, and it is the thing the author has no
AMD hardware to check.

## Gates

- **G1 — clocks.** sclk/mclk/power recorded per arm; perf level pinned for the
  timed runs and restored to `auto` after. Per `gpu-clock-benchmark-discipline`.
- **G2 — correctness before throughput.** P7 is checked first. If output diverges
  between cache modes, that is the finding and the TG numbers are a footnote.
- **G3 — same binary provenance.** Both backends built from the same commit of
  the same clone, recorded by sha.
- **G4 — the cache must actually engage.** Confirm from the load log that the
  expert cache initialises and reports a budget. "It ran and nothing crashed" is
  not evidence the feature was exercised — see the IQ2_M near-miss.

## Limits, declared up front

- One card, one host, K=1 architecture. gfx1201 + RADV only; says nothing about
  RDNA3, and nothing about Metal.
- 16 GiB VRAM against a 20–27 GiB model means every arm runs partially offloaded.
  Results describe the *oversubscribed* regime, which is the feature's intended
  case but not the only one.
- Not a comparison against CUDA — no NVIDIA card in this box.
