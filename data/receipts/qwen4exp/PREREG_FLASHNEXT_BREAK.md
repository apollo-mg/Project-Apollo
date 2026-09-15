# Prereg — where the expert-spill break actually is, and whether NUMA placement causes it

**Written 2026-09-14, before any rung of this stage has produced a number.** Stage 5 of the qwen4exp
campaign. Follows `RESULT_FLASHNEXT_SPILL_LADDER.md` (Stage 4, 2026-09-13), which found two marginal-cost
regimes — ~2.1 ms per spilled layer below `-ncmoe` 16, ~1.3 above — and explicitly could not test why:
*"Testing it needs per-node memory placement captured during a run, which nothing here records."*

## What this stage is for

Stage 4 bracketed the break with **wide** steps (8 → 16 → 32), so "the break is at 16" is an assertion
about an interval, not a measurement. Two questions, in priority order:

1. **Where is the break, and is it a step or a ramp?** Dense rungs through the interval.
2. **Is NUMA placement the mechanism?** Capture per-node placement every rung, then try to *intervene*.

Question 2 is the actionable one. If shallow spill is expensive because a couple of layers' expert
tensors land on one socket (~22.7 GB/s) while deep spill spreads across both (45.1 GB/s aggregate), then
**forcing interleaved placement should make shallow spill as cheap per byte as deep spill** — which would
directly fix the finding that "spilling two layers to just barely fit is the worst deal on the curve."

## Build

> ### Amendment 1 — 2026-09-14, before any rung of this stage has produced a number
>
> **The original text of this section was wrong and is withdrawn.** It said *"The Stage 4 build no longer
> exists on `.194`… there is no same-build option, so every cross-stage comparison needs a bridge"*, and
> selected `tq-pr324/build_sm60_c232` on that basis.
>
> **The Stage 4 build exists**: `/home/mark/buun-c7f114d34/build_sm60/bin/llama-server`, **build 12007,
> commit `c7f114d34`** — the exact binary `flashnext_residency.py` names in `BIN`. I concluded it was
> absent because I listed builds with `find … | head -8` and read absence-from-a-truncated-list as
> absence. **There are 26 `llama-server` builds on `.194`; I looked at 8.** Identical in shape to the
> `DFlash2` false mismatch earlier today and to the whole of `tools/DESIGN_INTENT_CONTINUITY.md`: a
> clean, confident answer from a check that could not have seen the thing it ruled out.
>
> **Consequences, all improvements:**
> - **Stage 5 runs `buun-c7f114d34/build_sm60` — the same binary as Stage 4.** No fork change, no ~800
>   commits, no build variable.
> - **No bridge is needed for build equivalence.** The three shared rungs (8, 16, 32) instead become a
>   **replication check**: same build, same box, one day apart. That measures run-to-run reproducibility,
>   which Stage 4 never established and which every marginal in that receipt silently depends on.
> - `c7f114d34` supports **`-lm` with `dio` explicitly listed**, plus `--numa {distribute,isolate,numactl}`
>   and `-ncmoe`. So Stage 5a still applies unchanged and the intervention knob is available.
> - **Ratio-based bands are kept anyway.** They were adopted to survive a build change that is no longer
>   happening, but a ratio is the right way to state a claim about curvature regardless.
>
> **P-BRIDGE is replaced by P-B7** below.

**This stage runs `buun-c7f114d34/build_sm60` — build 12007, commit `c7f114d34`, the Stage 4 binary.**
Model: `AI/Models/flashnext/Qwen3.8-Flash-Next-UD-IQ4_XS-0000{1,2,3}-of-00003.gguf`.
Hardware: `.194`, 4× P100 sm_60, 2× Xeon E5-2650v3, 2 NUMA nodes (31,772 / 30,197 MB), DDR4-2133,
150 W / 1063 MHz per [[gpu-clock-benchmark-discipline]]. `-sm layer`, KV `f16` verified per rung from
`-lv 4`, page cache dropped before every rung.

**Per Amendment 1 there is no build gap to bridge.** The three shared rungs (8, 16, 32) are instead a
**replication check against Stage 4's own numbers** — same binary, same box, one day apart. Stage 4
reported 17.60 / 13.57 / 10.75 tok/s at those rungs and never established run-to-run reproducibility,
which every marginal in that receipt depends on. Scored as **P-B7**.

## Arms

Executed in this order so the cheap gates fail first.

**Stage 5a — load-mode probe (gate, 2 runs).** `-ncmoe 16`, `--numa distribute`, `-lm mmap` vs `-lm dio`.
mmap leaves spilled expert bytes as file-backed pages placed by first touch — which is the very thing
`--numa distribute` manipulates — while `dio` reads into buffers placed by the allocating thread.
**Taking `dio` for its 4.3× load win while measuring placement would confound the load mode with P-B4.**
This probe settles it empirically instead. `dio` must also be confirmed *engaged* from the log, not
merely parsed: `-lm dio` is accepted by this build but absent from its `--help` mode list.

**Stage 5b — dense ladder (10 runs).** `-ncmoe` ∈ **{8, 10, 12, 14, 16, 18, 20, 24, 28, 32}**,
`--numa distribute`, load mode as decided by 5a. Per rung: GPU MiB after load, decode and prefill at
500 / 1800 / 3600 ctx, and **per-node placement** from `numastat -p` plus aggregated `/proc/<pid>/numa_maps`.

**Stage 5c — intervention (2 runs).** At `-ncmoe` **8** and **24**: external `numactl --interleave=all`
with **`--numa numactl`** (the mode that defers to the external CPU map), against the 5b `--numa distribute`
runs at the same rungs as controls. **Not** `numactl --interleave=all` wrapped around `--numa distribute`,
which would have the two strategies fighting.

## Predictions

Bands are **ratios wherever possible**, because absolute ms/layer figures come from a build this stage is
not running.

| id | prediction | falsified if |
|---|---|---|
| **P-B0** | load mode does not move placement: node-imbalance `I` differs by ≤ 0.05 absolute between mmap and dio at rung 16, and decode within ±3% | either exceeded → **ladder runs `mmap`**, recorded as a planned deviation, load time eaten |
| **P-B1** | the two regimes reproduce: mean marginal ms/layer over 8→16 ≥ **1.4×** the mean over 20→32 | ratio < 1.4 |
| **P-B2** | the break sits where Stage 4 put it: the largest single step-to-step drop in marginal ms/layer has its midpoint in **[14, 24]** | midpoint outside |
| **P-B3** | the transition is a **step, not a ramp**: ≥ 50% of the total shallow→deep marginal decline occurs across one step | decline spread over ≥ 4 consecutive steps each carrying < 25% |
| **P-B4** | placement tracks depth: `I = |T₀ − T₁| / (T₀ + T₁)` over **total** resident pages falls with spill depth, `I(8) − I(32) ≥ 0.10` | difference < 0.10 |
| **P-B5** | MiB freed per spilled layer constant within ±15% (replicates Stage 4's P-L0, which held at 3.1%) | any rung outside |
| **P-B6** | **the actionable one.** If P-B4 confirms, interleave at rung 8 improves decode ≥ 5% vs the distribute control | < 5% improvement |
| **P-B7** | **replication** (replaces P-BRIDGE, Amendment 1): rungs 8 / 16 / 32 reproduce Stage 4's 17.60 / 13.57 / 10.75 tok/s within **±5%** each, same binary one day apart | any of the three outside ±5% |

**P-B7 failing would be the most consequential outcome in this stage.** Stage 4's entire marginal
structure — the 2.11-vs-1.21 ms/layer break that motivated Stage 5 — assumes those numbers are
reproducible. Nothing has ever tested that. If a rung moves more than 5% on an identical binary and box,
the break may be run-to-run noise rather than structure, and **P-B1 through P-B3 become uninterpretable
regardless of how they score.** Read P-B7 first.

**P-B6 is scored only if `numa_maps` shows placement actually differed between the intervention and its
control.** If the two placements are indistinguishable the intervention was inert and P-B6 is **NOT
TESTABLE**, never "no effect" — an inert knob reporting a null is the [[readiness-probes-lie]] shape this
campaign has hit repeatedly, most recently when `offloaded 49/49 layers` proved unusable as a spill probe.

**P-B2 and P-B3 are independent.** Stage 4 can locate the break only to within 8→32; it cannot
distinguish a sharp step at 16 from a smooth ramp across the whole interval. **P-B3 is the question the
dense sampling exists to answer**, and a ramp would be the more interesting outcome — it would mean there
is no single "correct" operating point, only a gradient.

> ### Amendment 2 — 2026-09-14, before any rung of this stage has produced a number
>
> **P-B4's imbalance `I` is defined on TOTAL resident pages, not anonymous pages** (the original text said
> anon). Writing the parser exposed the problem: under `mmap` the spilled expert bytes are **file-backed**
> pages and under `dio` they are **anonymous** buffers, so an anon-only `I` would measure a different
> quantity in each arm — and would read as near-zero under mmap for reasons that have nothing to do with
> placement. Total is the only class-agnostic figure. **Anon and file are recorded separately alongside
> it**, so a shift between classes stays visible instead of silently changing what `I` means.
>
> This is the same confound P-B0 gates, showing up a second time in the metric's own definition.
>
> **Also recorded:** `-lm dio` is verified **functionally, not by log string.** The flag is accepted by
> builds that do not document it, so "it parsed" proves nothing ([[readiness-probes-lie]]). The evidence
> that DirectIO engaged is `M-dio`'s **load time against `M-mmap`'s** — a probe that cannot succeed unless
> the thing happened. Log hits for `direct-io` are counted and recorded, but they do not gate anything.

> ### Amendment 3 — 2026-09-14 20:30, after Stage 5a, before any 5b/5c/5d rung
>
> **1. P-B0 is FALSIFIED on both limbs. The ladder runs `mmap`, as the prereg pre-declared.**
>
> | arm | load | imbalance `I` | node 0 / node 1 MiB | decode 500 / 1800 / 3600 |
> |---|---:|---:|---|---:|
> | `M-mmap` | 606.7 s | **0.7564** | 17,633 / 2,445 | **12.61 / 12.58 / 11.97** |
> | `M-dio` | **155.3 s** | **0.9963** | 20,683 / **38** | 12.08 / 12.12 / 11.53 |
> | delta | −3.91× | +0.2399 | | **−4.18% / −3.61% / −3.67%** |
>
> **The two limbs fail very differently, and the distinction matters.**
> **Placement fails overwhelmingly**: `dio` puts **99.6%** of resident pages on one node against mmap's
> 87.8% — `ΔI = 0.2399` against a ≤ 0.05 band, nearly 5× over, with node 1 holding 38 MiB.
> **Decode fails narrowly**: −3.6 to −4.2% against a ±3% band — consistent in sign and size across all
> three context lengths, but thin enough that different rep spacing could move it across the line.
>
> The decision rests on the placement limb, which is what the gate exists for and is not close. Taking
> `dio` for its load-time win would have made P-B4 a measurement of the load mode.
> **The gate was worth its 25 minutes.**
>
> **Correction, appended not edited away:** this amendment first recorded the decode deficit as **6.8%**.
> That figure came from **rep 0 alone** at ctx 1800 (11.32 tok/s) while the arm was still running — the
> median over three reps is 12.12, so the real deficit is **3.6%**. Written twenty minutes after I had
> warned in this same session not to read a single rep as a result. The scorer takes medians precisely
> because one slow rep is a stall, not a measurement.
>
> **`dio` is nonetheless real and fast: 3.91× on load (606.7 s → 155.3 s), close to the 4.3× on record.**
> Both things are true, and the fleet-wide adoption note now carries a caveat: fast to load, hostile to
> NUMA balance, measurably slower to decode when experts are spilled.
>
> **`dio_log_hits = 0` on both arms.** The log never mentions direct-io even though DirectIO plainly
> engaged. **A log-string probe would have reported the opposite of the truth.** Load time was the probe
> that could not succeed unless the thing happened ([[readiness-probes-lie]]).
>
> **2. Clock state changed between stages, and it is not a replication failure.** Stage 4 ran at
> **1189 MHz / 250 W**; `.194` rebooted **2026-09-14 08:52:45** and came up at the fleet's
> **1063 MHz / 150 W** boot default ([[gpu-clock-benchmark-discipline]]), which is what Stage 5a ran at.
> Caught only because `gates()` records clocks. Cards were 39–46 °C with throttle reasons `0x0`, so this
> is a cap, not thermal. **5b and 5c restore 1189 MHz / 250 W to match Stage 4**, which is what makes
> P-B7 a real test.
>
> **3. New arm — Stage 5d, the clock ladder (Mark's call, for the efficiency chart).** Rungs **8 and 32
> at 1063 MHz / 150 W**; rung 16 at that clock is already measured (`M-mmap`, 12.58). Paired against the
> same rungs at 1189 MHz / 250 W from 5b.
>
> | id | prediction | falsified if |
> |---|---|---|
> | **P-B8** | **clock sensitivity falls with spill depth**: decode's fractional response to the 10.6% clock cut is **smaller at rung 32 than at rung 8**, by ≥ 3 points — deep spill is host-bound and should care less about GPU MHz | rung 32's sensitivity ≥ rung 8's − 3 points |
>
> **Anchor already in hand:** at rung 16 the 10.6% clock cut cost **7.5%** (13.60 → 12.58), i.e. decode
> is roughly 70% clock-elastic there. P-B8 predicts that elasticity keeps dropping as spill deepens.
> **If P-B8 confirms, the efficiency chart gains a second axis**: deep-spill configurations can be
> underclocked for perf-per-watt at a smaller throughput cost than shallow ones.

> ### Amendment 4 — 2026-09-14 20:58, mid-run. **P-B4 is DEMOTED to descriptive.**
>
> Written after D-16's placement and **before its decode numbers existed**, so this is a reaction to a
> defect in the prediction, not to the result it would have produced.
>
> **P-B4's effect size is smaller than the noise in its own metric.** Two runs of the *same rung* with
> the same flags:
>
> | run | rung | clock | node 0 / node 1 MiB | total | `I` |
> |---|---|---|---|---:|---:|
> | `M-mmap` | 16 | 1063 | 17,633 / 2,445 | 20,079 | **0.7564** |
> | `D-16` | 16 | 1189 | 16,468 / 3,609 | 20,077 | **0.6405** |
>
> **The total host residency is deterministic to 2 MiB. The split across sockets swung 0.116** — larger
> than the ≥ 0.10 difference P-B4 predicts across the *whole* ladder. With one observation per rung,
> P-B4 can be confirmed or falsified by the placement lottery alone.
>
> Caveat kept honest: those two runs differ in clock as well as in run, so clock timing may shift which
> thread faults first. That would be its own finding, and it still does not rescue a 0.10 band measured
> once per rung.
>
> **What changes:** P-B4 is reported as a **description of the observed placement distribution across
> ten rungs**, with no CONFIRMED/FALSIFIED verdict. **The band is not being widened** — loosening a band
> after seeing data is the move preregistration exists to prevent. The ladder establishes the variance
> for the first time so that a *future* stage can state a band that means something, ideally with
> repeated runs at a fixed rung.
>
> **P-B6 is unaffected and gains importance.** `numactl --interleave=all` sets an actual memory policy,
> so it should drive `I` toward zero — an effect far outside this ±0.12 noise. It remains gated on
> `numa_maps` showing placement actually moved.
>
> **Root cause is now on record** ([[numa-distribute-is-threads-only]]): `GGML_NUMA_STRATEGY_DISTRIBUTE`
> only calls `pthread_setaffinity_np`, and the sole `mbind` in ggml sits in the AllReduce path that is
> inert on sm_60. **Nothing in this stack places memory.** First touch decides, and thread scheduling
> is not reproducible — so the lottery is the expected behaviour, not an anomaly.

> ### Amendment 5 — 2026-09-14 21:14. **New prediction P-B9, committed before rungs 18/20/24/28 run.**
>
> Written from the first three rungs (8, 16, 32). **Rungs 10, 12, 14, 18, 20, 24 and 28 have not
> started**, and P-B9 is decided entirely by 24 and 28, so this is a genuine forward prediction.
>
> **Observation.** Host residency and placement across the three rungs measured so far:
>
> | rung | host MiB | node-0 share | `I` |
> |---:|---:|---:|---:|
> | 8 | 11,001 | 21% | 0.588 |
> | 16 | 20,077 | 83% | 0.654 |
> | 32 | **38,711** | 44% | **0.122** |
>
> **Host residency is ~1,150 MiB per spilled layer** (9,076 / 8 = 1,134.5; 18,634 / 16 = 1,164.6 —
> consistent to 2.6%), so `host_mib(n) ≈ 1150·n + 1800`.
>
> **Hypothesis H4 — the regimes are a CAPACITY effect, not a bandwidth or scheduling one.** Node 0 holds
> **31,772 MiB**, node 1 **30,197 MiB**. A rung whose host residency fits inside one node *can* land
> almost entirely on one node, and with nothing in ggml placing memory
> ([[numa-distribute-is-threads-only]]) it often does — a lottery that is wrong more often than right,
> since all consumers sit on node 0 below rung ~24. **A rung that exceeds one node's capacity has no
> choice but to straddle both**, and average locality improves by force.
>
> By the fit, residency passes ~30,000 MiB usable (node total minus OS and page cache) at **rung ≈ 25**.
> **Stage 4 put its marginal-cost break between 16 and 32.**
>
> | id | prediction | falsified if |
> |---|---|---|
> | **P-B9** | imbalance collapses at the capacity boundary, not gradually: **`I` > 0.35 at rung 24 and `I` < 0.35 at rung 28** | either rung falls the other side of 0.35 |
>
> Predicted residency: rung 18 ≈ 22,500 · rung 20 ≈ 24,800 · **rung 24 ≈ 29,400 (still fits)** ·
> **rung 28 ≈ 34,000 (cannot fit)**.
>
> ~~**If P-B9 confirms, Stage 4's headline needs rewriting.** "Spill gets 3.3× cheaper per byte with
> depth" would become *"below ~25 layers the allocator can put everything on the wrong socket and
> usually does; above it, it cannot."* That reframes the result from a property of expert spill into a
> **fixable placement artifact** — and predicts `numactl --membind=0` recovers most of the shallow-rung
> penalty, which no arm in this stage currently tests.~~
>
> **RETRACTED 2026-09-14 21:35, before rungs 24 and 28 ran. The inference has the sign backwards.**
>
> | span | tonight | Stage 4 |
> |---|---:|---:|
> | 8 → 16 marginal | **1.676** ms/layer | 2.11 |
> | 16 → 32 marginal | **1.150** | 1.21 |
> | break ratio | **1.46×** | **1.74×** |
>
> The deep marginal replicates within 5%. The shallow one is 21% low **because D-08's bad placement made
> rung 8 slower**, and a slower shallow endpoint *lowers* the 8→16 slope. **Bad shallow placement makes
> the shallow regime look cheaper, shrinking the break.** Tonight's run has the badly-placed rung 8 and
> the *smaller* break (1.46× vs 1.74×).
>
> So placement noise **understates** the break; it cannot be its cause. **The two-regime break is real
> and is not a placement artifact.**
>
> **What survives:** P-B9 is still a live test — it predicts `I` collapses at the capacity boundary, and
> rungs 24/28 still decide it. The capacity arithmetic is untouched. **What dies:** the claim that
> confirming P-B9 would reframe Stage 4's headline. That inference does not follow either way.
>
> A `numactl --membind=0` arm is still worth running, but for the opposite reason to the one given
> above: **to remove the lottery so the break can be measured cleanly**, not to explain it away. On
> tonight's evidence a clean measurement would show a break **larger** than 1.74×.
>
> **Relationship to P-B4, stated plainly:** the demotion in Amendment 4 stands on method — a ≥ 0.10 band
> was indefensible against 0.116 run-to-run noise. But the *observed* spread is **0.466** (I(8) 0.588 vs
> I(32) 0.122), four times that noise, so the underlying claim that placement varies with depth looks
> true and was simply predicted with a band too tight to mean anything. **The band was wrong, not the
> idea** — and P-B9 now says *why* it varies, which P-B4 never did.

## Scoring

`tools/score_flashnext_break.py`, committed before the first rung produces a number. Marginal ms/layer is
computed between *adjacent* rungs, never from a fit — Stage 4's headline was nearly lost to a linear model
returning R² = 0.9907 across a real structural break. **Quote marginals; a fitted slope is not evidence of
linearity.**

## Cost

6 rungs took 89 minutes in Stage 4. 14 runs here ≈ **3 hours at mmap load times**, less if 5a clears `dio`.

## Known limits, stated in advance

- One model, one quant, one box. IQ4_XS on DDR4-2133 and two Haswell-EP sockets.
- The baseline is rung 8, not zero spill — `-ncmoe 0` does not fit (Stage 3 P-S1).
- `numastat -p` attributes file-backed and anonymous pages differently by load mode, which is exactly why
  P-B0 gates the stage rather than being assumed.
- A confirmed P-B6 would be a result about *this* NUMA topology, not a general claim about expert spill.
