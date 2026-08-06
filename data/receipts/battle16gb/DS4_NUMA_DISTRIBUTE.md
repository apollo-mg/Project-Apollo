# `--numa distribute` buys 22.7% on DS4 decode — the bottleneck was memory placement, not the GPUs

> ## ⚠ SUPERSEDED 2026-08-02 — the headline number is too high
>
> A controlled re-baseline (**`DS4_REBASELINE_NUMA.md`**, arms distribute → none → distribute)
> puts the effect at **+13.6%**, not +22.7%.
>
> - The **control reproduced**: nonuma 4.61 vs the 4.58 below (0.7% apart).
> - The **treatment did not**: distribute measured **5.16 and 5.31**, against **5.62** below.
>   Across three independent loads distribute spans ~9%, so the 5.62 here was a high outlier.
>
> Cause is the exact limitation flagged in the Limits section below — *"K=1 per policy. The tight
> spreads describe within-arm stability, not run-to-run reproducibility of the whole
> load-and-measure cycle."* The 0.5% within-arm spread made a K=1 result look precise.
>
> Two further corrections from the re-baseline:
> - **`distribute` is ~2× worse on the cold first draw** (1.13 t/s vs 2.30), reproducibly. It is
>   a throughput-vs-latency trade, not a free win.
> - **The "adopt as standard" recommendation is withdrawn as unqualified.** Use it for sustained
>   warm generation; avoid it for first-response latency; prefill impact is unresolved and both
>   distribute arms were *slower* than the control.
>
> Everything below is left unedited as the original record.

`.194`, 4× Tesla P100-PCIE-16GB, **1063 MHz / 150 W**, 2× Xeon E5-2650 v3 (Haswell-EP, 2 NUMA
nodes), 64 GB DDR4-2133 ECC. DS4-Flash UD-IQ1_S 82.5 GB, build `331981025`.
`-c 8192 -ngl 99 -sm layer -ts 3,4,4,1 -fit off -fa on -ncmoe 40`. Date 2026-08-02.

## Result

| arm | decode | measured draws | spread |
|---|---|---|---|
| baseline (no NUMA policy) | 4.58 t/s | 4.57, 4.56, 4.58, 4.59 | 0.7% |
| **`--numa distribute`** | **5.62 t/s** | 5.61, 5.62, 5.64, 5.61 | 0.5% |
| `--numa numactl` + `numactl --interleave=all` | 4.89 t/s | 4.85, 4.90, 4.89, 4.91 | 1.2% |

**`--numa distribute` is +22.7% over baseline** and +19% over the warm no-policy reference
(4.71–4.74 t/s). One flag, no quality change: gzip ratio is **0.4743 on every draw of every
arm** — byte-stable output, purely faster.

## Why this was worth testing

GPU utilisation during decode measures **6.5% mean / 8% max** across the four cards. With
`-ncmoe 40`, the routed experts live in CPU RAM and are read every token; the P100s are acting
as a memory pool while two Haswell-EP sockets do the work. Rough arithmetic: 82.5 GB / 284B
params = 2.32 bpw, so ~21B active params ≈ 6.1 GB of weight reads per token; at 4.6 t/s that is
~28 GB/s crossing the CPU memory subsystem.

E5-2650 v3 is Haswell-EP, so the inter-socket link is **QPI, not UPI** — 2 links @ 9.6 GT/s
≈ 19.2 GB/s per direction, and `numactl` reports node distance **21 vs 10** (remote ~2.1×
local). Every prior DS4 measurement on this fleet ran with **no `--numa` flag**, i.e. default
first-touch: mmap'd expert pages land wherever the faulting thread ran, with threads spread
across both sockets. For a workload that reads *every* expert *every* token, that is close to
worst-case placement.

The result is consistent with that being the binding constraint: a **memory-placement flag**
moves throughput 22.7% while the GPUs sit at 6.5%.

## Design notes

- **Caches dropped before every arm**, including baseline. `llama-server --help` warns that
  switching NUMA mode with a populated page cache measures the *old* placement. The cache held
  ~67 GB of expert pages under the previous policy, so not dropping would have made NUMA look
  inert. This also means the baseline here (4.58) is legitimately below the warm no-policy
  figure (4.71–4.74) — all arms start cold and equal.
- 4 pre-warm draws discarded, then 4 measured; any arm spreading >8% would be reported UNSTABLE
  rather than averaged. (Warming moves this config 2.7× — see `DS4_DECODE_WARMUP.md`.)
- `isolate` was **not** tested: one node has 31.8 GB and the CPU-side experts are ~67 GB, so it
  cannot fit and would fault remotely regardless.

## Drift control — the weak point of this design, and why the result survives it

Unlike `DS4_DECODE_WARMUP.md`'s A/B, this run has **no repeat-control arm**: each policy ran
once, in the order baseline → distribute → interleave. A monotonic drift (thermal, cache, clock)
could in principle masquerade as an effect.

The ordering rules it out: **the last arm placed in the middle.** Monotonic drift would have put
`interleave` (run third, ~25 min after baseline) highest; it came in at 4.89, between the other
two. Combined with within-arm spreads of 0.5–1.2% against a 22.7% effect — roughly 30× the
noise — drift is not a plausible explanation.

A repeat-control arm (baseline → distribute → baseline) would settle it outright and is the
obvious upgrade if this number is ever load-bearing for a published claim.

## Limits

- One configuration, one prompt, 200 tokens, one machine, one model. The magnitude is specific
  to `-ncmoe 40` on this box's RAM, disk, and socket topology.
- **`distribute` beating `interleave` is unexplained.** Both spread memory across nodes; they
  differ in thread placement and in who does the interleaving. Not investigated.
- This does **not** show QPI bandwidth is saturated — only that default first-touch placement
  was leaving ~20% on the table. Confirming a QPI ceiling would need per-link counters
  (`perf` uncore events), which were not collected.
- K=1 per policy. The tight spreads describe within-arm stability, not run-to-run reproducibility
  of the whole load-and-measure cycle.

## Consequence

**Adopt `--numa distribute` as standard for DS4 work on `.194`.** Every subsequent measurement
on this node gets ~20% cheaper in wall-clock, and prior DS4 decode figures on this fleet should
be understood as having run under default (bad) placement.

## Provenance

- `.194:~/ds4_numa/` — `numa.log`, `server_{baseline,distribute,interleave}.log`, `resp_*.json`
- `.194:~/ds4_tsspeed/` — `tsspeed.log` (GPU-utilisation sampling, `layer_n40` arm)
- Scripts `scratchpad/ds4_numa.sh`, `scratchpad/ds4_tensorsplit_speed.sh`,
  `scratchpad/chain194.sh`
- Collected output: `scratchpad/chain194_results.txt`
