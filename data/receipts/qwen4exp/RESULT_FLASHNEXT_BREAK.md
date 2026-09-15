# Result — the spill curve has a ~3% noise floor, and dense sampling is the wrong instrument for it

> **Note on this document's own history.** Its original title was *"the expert-spill curve cannot be
> measured on this box until memory is pinned."* **Stage 5c falsified that**: pinning works perfectly
> (placement reproducible to 0.2 MiB) and makes throughput **worse** by 5–6%, while decode still varies
> up to 3.7% run-to-run under byte-identical placement. The placement narrative in the middle sections
> was written before 5c ran and is **over-attributed** — it is kept, with this warning, because the
> reasoning is auditable and the corrections are the point. **Read the Stage 5c section for what the
> evidence actually supports.**

**Run 2026-09-14, 20:07–23:09, `.194`** (4× P100 sm_60, 2× Xeon E5-2650v3, 2 NUMA nodes, DDR4-2133).
Pre-registered in `PREREG_FLASHNEXT_BREAK.md` with five amendments, every one dated and committed before
the rungs it affected. Build **12007 / `c7f114d34`** — the same binary as Stage 4, so the three shared
rungs are a replication check, not a bridge. Driver `flashnext_residency.py --stage5a/--stage5b`, scorer
`tools/score_flashnext_break.py`, both committed before the first rung produced a number.
**14 runs. All loaded, answered "17 × 23", and completed. KV verified `f16` on every arm.**

## Headline

Stage 5 set out to locate a marginal-cost break that Stage 4 had bracketed between `-ncmoe` 8 and 32.
**It could not, and the reason is the finding:** adjacent-rung marginals on this ladder run from
**−1.109 to +2.795 ms per spilled layer**, a range that includes two physically impossible values.

**The cause is a ~2–4% run-to-run noise floor, measured in 5c under byte-identical placement** — not
placement, which was this stage's working hypothesis for three hours and is over-attributed throughout
the middle of this document. Dense rungs shrink the signal per step while the noise floor stays fixed:
Stage 4's 16→32 step moves decode 21% (SNR ≈ 7), this stage's 8→10 step moves it 4.6% (SNR ≈ 1.5).
**Finer sampling is what broke the measurement.**

| step | ms / layer | implied GB/s |
|---|---:|---:|
| 8 → 10 | 1.469 | 18.8 |
| **10 → 12** | **0.166** | **166.3** |
| 12 → 14 | 2.795 | 9.9 |
| 14 → 16 | 2.275 | 12.1 |
| 16 → 18 | 1.660 | 16.6 |
| 18 → 20 | 1.407 | 19.6 |
| 20 → 24 | 1.812 | 15.2 |
| 24 → 28 | 2.362 | 11.7 |
| **28 → 32** | **−1.109** | — |

**166 GB/s is impossible** on DDR4-2133 (measured 22.68 node-local, 45.1 aggregate first-touch).
**A negative marginal is impossible full stop** — spilling four more layers cannot make decoding faster.
Both steps coincide with a large placement shift, which is what led this stage to blame placement —
but 5c showed two runs at **identical** placement differ by up to 3.7%, which is enough to produce both
artifacts on its own. The placement coincidence is real and is not sufficient evidence of causation:

- **10 → 12**: D-12 landed at `I = 0.028`, the most balanced rung measured. Better locality paid for two
  extra spilled layers almost exactly.
- **28 → 32**: D-28 held 80% on node 0 while *having node-1 consumers* (layers 24–31 feed CUDA2 on node
  1); D-32 landed 44/56, which is close to correct for its depth. Placement beat four layers.

**Both signatures were predicted in advance**, at 21:29, before the rungs ran: *"the marginal should come
out implausibly cheap — possibly near zero or negative … a negative marginal would be the giveaway."*

## What is solid

**P-B5 CONFIRMED: 1,145 MiB freed per spilled layer, worst deviation 3.7%** across ten rungs.
Host residency is equally clean at **~1,142 MiB per layer**. **The memory side of expert spill is
precisely reproducible.** Stage 4's P-L0 found the same thing at 3.1%.

**Two of the three shared rungs replicate Stage 4 to within 1.4%** at every context length — D-16
(+0.9 / −0.1 / +0.8%) and D-32 (+1.0 / +1.4 / +0.1%).

## What is not

**P-B7 (replication) FALSIFIED**, worst deviation **7.0%**, and the failure is entirely **D-08**
(−7.0 / −4.5 / −3.9%). D-08 landed **21% on node 0** while D-16 landed 83%. The scorer's automatic
consequence — *"Stage 4's marginals are not reproducible"* — was written assuming uniform noise and is
**too strong**: 6 of 9 measured cells fall within ±1.4%. The defensible statement is that **Stage 4
reproduces closely when placement is favourable, and Stage 4 never measured placement.**

**P-B1 and P-B3 report CONFIRMED and both verdicts are worthless.** P-B1's deep mean includes the
−1.109 step; P-B3's "56% of the decline in one step" *is* that step. **A verdict computed from a
physically impossible input is not evidence**, and neither is banked. P-B2 is FALSIFIED by the same
artifact ("largest drop at midpoint 30").

## Placement: the uncontrolled variable

| rung | host MiB | node-0 share | `I` |
|---:|---:|---:|---:|
| 8 | 11,739 | 21% | 0.588 |
| 10 | 13,996 | 23% | 0.540 |
| 12 | 15,530 | 47% | **0.028** |
| 14 | 17,817 | 31% | 0.353 |
| 16 | 20,816 | 83% | 0.654 |
| 18 | 22,366 | 21% | 0.560 |
| 20 | 25,367 | 77% | 0.547 |
| 24 | 29,923 | 82% | 0.635 |
| 28 | 34,463 | 80% | 0.608 |
| 32 | 39,450 | 44% | 0.118 |

**Node-0 share ranges 21%–83% with no relationship to rung.** Root cause is source-verified
([[numa-distribute-is-threads-only]]): `GGML_NUMA_STRATEGY_DISTRIBUTE` only calls
`pthread_setaffinity_np`, and the sole `mbind` in ggml sits in the AllReduce path that is inert on
sm_60. **Nothing in this stack places memory.** `--numa distribute` spreads *threads*; allocation is
left to first touch, and thread scheduling is not reproducible.

Two runs of the *same* rung (16) gave `I` = 0.7564 and 0.6543 — a swing of 0.10 at fixed configuration.

### Three hypotheses, all tested, none supported

Committed at 21:02 with two rungs measured and eight to go, so the criterion could not be fitted.

- **H1 (DMA locality to the consuming GPU)** — within-ladder residual vs node-0 share, eight shallow
  rungs: **r = +0.119**. Predicted positive; got negligible. *Not supported.*
- **H2 (thread locality, sign-blind)** — r = −0.438 on three baselined rungs; also contradicted by D-08
  and D-16 having near-equal `|I|` (0.588 / 0.654), opposite direction, and 5.6 points of difference.
  *Not supported.*
- **H3 (lottery)** — best fit to the evidence. *Placement varies, it matters, and it is not a function of
  anything this stage measured.*

Caveat on my own test: the residual regresses decode linearly against rung, and the curve is not linear,
so residuals carry curvature as well as placement.

### H4 (capacity), proposed and falsified within two hours

Amendment 5 proposed that rungs whose host memory exceeds one node (31,772 MiB) are *forced* to spread.
**P-B9 FALSIFIED**: `I(24)` 0.635 (wanted > 0.35) and `I(28)` **0.608** (wanted < 0.35). Rung 28 exceeded
one node's capacity and still landed 80/20 — first touch fills node 0, then spills the remainder; it does
not pull toward balance. The forced minimum on node 1 is 5.8% at rung 28 and 19.5% at rung 32, while
**observed** shares were 20% and 56%. **Every rung spread more than capacity required**, so D-32's balance
— the observation that inspired H4 — was mostly chance.

H4 was also wrong in *sign*, retracted at 21:35 before rungs 24/28 ran: bad placement at a shallow rung
*raises* its latency, which *lowers* the shallow marginal and **shrinks** the apparent break. Tonight has
the badly-placed rung 8 and the smaller ratio (1.46× vs Stage 4's 1.74× on the same spans).
**Placement noise understates the break; it cannot be its cause.**

## Stage 5a — the load-mode gate, and why it was worth 25 minutes

| arm | load | `I` | node 0 / node 1 | decode 500 / 1800 / 3600 |
|---|---:|---:|---|---:|
| `M-mmap` | 606.7 s | 0.7564 | 17,633 / 2,445 | 12.61 / 12.58 / 11.97 |
| `M-dio` | **155.3 s** | **0.9963** | 20,683 / **38** | 12.08 / 12.12 / 11.53 |

**P-B0 FALSIFIED on both limbs.** `dio` loads **3.91× faster** and is genuinely engaged — but pins
**99.6%** of pages to one node (node 1 holds 38 MiB) and costs **3.6–4.2%** of decode. Had the ladder
taken `dio` for its load-time win, every placement number above would have measured the load mode.

**`dio_log_hits = 0` on both arms.** The log never mentions DirectIO even while it plainly works. **A
log-string probe would have reported the exact opposite of the truth**; load time was the probe that
could not succeed unless the thing happened ([[readiness-probes-lie]]).

## A clock confound, caught only because gates record clocks

Stage 4 ran at **1189 MHz / 250 W**. `.194` rebooted 2026-09-14 08:52:45 and came up at the fleet's
**1063 MHz / 150 W** boot default ([[gpu-clock-benchmark-discipline]]), which Stage 5a ran at — cards
39–46 °C, throttle reasons `0x0`, so a cap and not thermal. The apparent 10% replication gap matched the
10.6% clock cut almost exactly. **Restored to 1189/250 before 5b.** Without that one line in `gates()`
this stage would have concluded Stage 4 was irreproducible and destroyed a correct result.

Anchor for the clock arm, still to run: at rung 16 a 10.6% clock cut cost **7.5%** of decode — decode is
roughly 70% clock-elastic there, so ~30% of the time is already host-bound.

## Stage 5c — pinning, and the finding that reframes everything above

`numactl --membind=0` with `--numa distribute`, identical to the 5b arms in every other respect.

| arm | rung | node 0 / node 1 | `I` | decode 500 / 1800 / 3600 |
|---|---|---|---:|---:|
| `B-16a` | 16 | 20,072.0 / **5.0** | 0.9995 | 12.89 / 12.71 / 12.26 |
| `B-16b` | 16 | 20,071.8 / **4.9** | 0.9995 | 12.56 / 12.69 / 11.80 |
| `D-16` (control) | 16 | 17,278 / 3,538 | 0.654 | 13.69 / 13.58 / 12.95 |
| `B-08` | 8 | 10,975.4 / **2.0** | 0.9996 | 16.13 / 16.04 / 14.94 |
| `D-08` (control) | 8 | 2,416 / 9,322 | 0.588 | 16.37 / 16.61 / 15.22 |

**P-B10 CONFIRMED, decisively.** Two pinned runs placed memory identically to **0.2 MiB out of 20 GB**
(20,072.0 vs 20,071.8), against an unpinned swing of 0.10 in imbalance at the same rung. Pinning works.

**P-B11 FALSIFIED.** With byte-identical placement, decode still differs by **−2.59% / −0.22% / −3.74%**
against a ±1.5% band. **Placement was never the main source of run-to-run variance.**

**P-B12 FALSIFIED.** Pinning made the badly-placed rung **slower** (−1.5 to −3.4% vs D-08), not faster.
And at rung 16, pinning cost **5–6%** against the unpinned 83/17 control. **Concentrating all pages on
the consuming GPU's node is worse than the lottery's typical outcome** — consistent with memory-
controller contention or a straggler effect, which this stage cannot separate.

### The dense ladder was the wrong instrument, and the arithmetic says so

There is **~2–4% irreducible run-to-run variance at fixed configuration and fixed placement.** Propagate
that through a marginal:

| span | decode change | signal | noise | SNR |
|---|---|---:|---:|---:|
| Stage 4, 16 → 32 | 13.60 → 10.72 | **21%** | ~3% | **≈ 7** |
| Stage 5, 8 → 10 | 16.61 → 15.84 | **4.6%** | ~3% | **≈ 1.5** |

**Closer rungs shrink the signal while the noise floor stays put.** The 166 GB/s step and the negative
−1.109 ms/layer step are not placement artifacts — they are two rungs' worth of ±3% noise compounding
across a 4% signal. **Stage 4's wide geometric rungs were the correct design; this stage's dense ladder
was self-defeating**, and computing the SNR beforehand would have shown it in five minutes.

**The placement story in the sections above is over-attributed.** Placement genuinely varies (21–83%),
pinning genuinely fixes it byte-exactly, and pinning genuinely does not help throughput. Those are three
separate true facts, and none of them is the explanation for the marginal chaos. The explanation is the
noise floor.

## Stage 5d — the clock arm. P-B8 falsified with the sign inverted, and the night's cleanest signal

Rungs 8 and 32 at **1063 MHz / 150 W** against the 5b arms at **1189 MHz / 250 W** (a 10.6% clock cut
and a 40% power cut). Rung 16 at the low clock comes from `M-mmap`. Run at Mark's request for the
efficiency chart.

| rung | 500 | 1800 | 3600 | mean loss | elasticity |
|---:|---:|---:|---:|---:|---:|
| 8 | −0.7% | +0.1% | −0.3% | **−0.3%** | **−0.03** |
| 16 | +7.9% | +7.4% | +7.5% | **+7.6%** | **0.72** |
| 32 | +9.6% | +10.1% | +9.4% | **+9.7%** | **0.92** |

**P-B8 FALSIFIED.** It predicted elasticity would *fall* with spill depth by ≥ 3 points, reasoning that
deep spill is host-bound and should care less about GPU clock. **Elasticity rises monotonically from
zero to nearly proportional** — a 10.0 point move in the opposite direction.

**This is the only result tonight comfortably clear of the noise floor.** 7.6% and 9.7% against ~3%,
and consistent to within 0.7 points across three context lengths. Rung 8's zero is equally consistent
(−0.7 / +0.1 / −0.3). Everything else this stage measured was 1–2× the floor; this is 2–3×.

**The practical finding: at `-ncmoe 8`, the 250 W → 150 W cut costs nothing measurable.** Four cards at
150 W instead of 250 is **400 W saved** for **1.67× the tokens per watt**, which is the fleet's own boot
default. At rung 32 the same cut costs ~10% — still a perf-per-watt gain, no longer free.

**No mechanism is claimed.** The intuitive account (more spill → more CPU work → GPU clock matters less)
predicts the opposite of the measurement, so how the spilled and resident paths overlap is not what this
stage assumed. That deserves its own experiment, not a paragraph of speculation.

## What to do next

**Superseded by 5c.** The list below was written before the pinning arms ran and its first item is
wrong: pinning does not rescue the measurement, it costs 5-6%. What replaces it:

1. **Publish an error bar, then design to it.** The measured noise floor is **~2-4% at fixed everything**.
   Every marginal, exchange rate and cost model in this campaign has been quoted without one.
   `RESULT_FLASHNEXT_SPILL_LADDER.md`'s exchange-rate table needs revisiting on this basis -- its
   MiB-per-tok/s figures divide by a *difference* in tok/s, which is exactly where a 3% noise floor does
   the most damage.
2. **Size steps by SNR, not by curiosity.** A step must move decode by **>= 15%** to carry a marginal
   worth quoting against a 3% floor. That means geometric rungs, as Stage 4 used, and it means the break
   cannot be localised more finely than one geometric step without many repeats per rung.
3. **Repeats, not resolution.** Five runs at each of three widely spaced rungs would settle the break
   better than ten rungs measured once. This stage spent its budget on the wrong axis.
4. **`PREREG_DIMM_UPGRADE.md` needs a noise floor before Wednesday.** Its predictions were written
   without one. A DIMM upgrade that moves throughput less than ~4% is **not measurable by the method
   this campaign has been using**, regardless of channel count -- and that threshold should be in the
   prereg before the RAM arrives, not discovered afterwards.
5. **Fix the warmup.** Rep 0 is 4-10% slow in every arm because a 64-token completion never faults in
   the spilled experts. A real generation as warmup would remove a known bias for free.

## Limits

One model, one quant, one box, **one run per rung**. Stage 4 recorded no placement, so its baseline
carries its own unmeasured placement. The 5c intervention and the 5d clock arm had not run when this was
written. `-ncmoe 0` does not fit, so the ladder's base is rung 8, not zero spill.
