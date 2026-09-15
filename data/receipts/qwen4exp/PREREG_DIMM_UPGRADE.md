# Prereg — does doubling `.194`'s memory channels move the expert-spill path? (qwen4exp, Stage 5)

**Written 2026-09-14 ~08:45, before the DIMMs are purchased and before anything is opened.** Mark has two
local leads on the parts; nothing has changed hands. Predictions are committed here first because the
upgrade is not reversible in an afternoon and the baseline it will be compared against already exists.

## The question, and why the upgrade is the instrument

Stage 4 (`RESULT_FLASHNEXT_SPILL_LADDER.md`) left one thing genuinely undecided. In the deep-spill regime the
marginal cost of a spilled layer implied an **effective 22.8 GB/s** — and `.194`'s measured **node-local
bandwidth is 22.68 GB/s**. Within half a percent.

Either:

- **(A) the spill path is host-bandwidth-bound** and saturating a single socket's two channels, or
- **(B) it is CPU-compute-bound** — dequantizing and multiplying IQ4_XS experts rather than merely reading
  them — and that agreement is a coincidence.

**Stage 4 cannot separate these.** Doubling the populated channels per socket does: under (A) decode at deep
spill improves proportionally, under (B) it barely moves while the triad benchmark rises anyway. **The
falsifiable fork is P-D5.**

## The change

| | before | after |
|---|---|---|
| populated | **4×** Hynix HMA42GR7MFR4N-TF, 16 GB **2Rx4** PC4-2133P, in P1_DIMMA1/B1 + P2_DIMME1/F1 | + **4×** Kingston KVR24R17S4/16I, 16 GB **1Rx4** PC4-2400T RDIMM, into **C1/D1/G1/H1** |
| channels | 2 of 4 per socket | **4 of 4 per socket** |
| capacity | 64 GB (60 usable) | **128 GB** |

Both parts are registered ECC (`KVR24**R**17S4`, `PC4-2400T-**R**C1-11`). The Kingston sticks are DDR4-2400
and **will downclock to 2133**, the E5-2650v3's ceiling. **Ranks are mixed across channels** — 2Rx4 on
A1/B1/E1/F1, 1Rx4 on C1/D1/G1/H1 — but never within a channel, since every channel holds exactly one DIMM.

## Gates, before any prediction is scored

1. **Re-baseline first.** Re-run the Stage 1 membw triad (`membw.c`, same binary, same args) immediately
   before the machine is opened. **It must reproduce 2026-09-13's numbers within 5%**; if it does not, the
   fresh run becomes the baseline and that is recorded. Guards against a month of drift being scored as an
   upgrade effect.
2. **`dmidecode -t memory`** must show 8 populated slots and the configured speed.
3. **`numactl --hardware`** must show ~64 GB per node. A lopsided split means a stick is in the wrong bank.
4. Any ECC error in `dmesg`/EDAC aborts the comparison — a marginal stick invalidates every timing below.

## Baselines (measured 2026-09-13, committed)

| quantity | value |
|---|---|
| triad, node-local, 10 threads (B-L0 / B-L1) | **22.68 / 22.68 GB/s** |
| triad, cross-socket (B-R01) | **7.00 GB/s** |
| triad, `interleave=all`, 20 threads (B-IL) | **27.90 GB/s** |
| triad, free/first-touch, 20 threads (B-FT) | **45.14 GB/s** |
| ladder rung 2 decode @500 | **22.33 tok/s** |
| ladder rung 48 decode @500 | **8.64 tok/s** |
| deep-regime marginal spill cost | **~1.3 ms per layer per token** |

## Predictions

| id | prediction |
|---|---|
| P-D1 | `dmidecode` reports **8 populated at 2133** configured speed — not 1866, which is what an unbalanced or mis-mixed population produces |
| P-D2 | node-local triad rises 22.68 → **≥ 35 GB/s** (expected 38–43: ~2× the channels, less the 1R interleaving penalty on half of them) |
| P-D3 | first-touch, both nodes, rises 45.14 → **≥ 70 GB/s** |
| P-D4 | **CONTROL — cross-socket stays 7.00 ± 10%.** That path is QPI-limited, not channel-limited, so it must **not** improve. If it does, the model of this machine is wrong and P-D2/P-D3 need re-reading |
| P-D5 | **THE FORK — rung 48 decode 8.64 → ≥ 11 tok/s** if the spill path is bandwidth-bound |
| P-D6 | **CONTROL — rung 2 decode stays 22.33 ± 5%.** Two layers spilled is almost no host traffic, so the upgrade should not touch it. If rung 2 also speeds up, something other than the spill path changed and P-D5 is contaminated |

**How P-D5 is read, declared now so the bands are not drawn after the data:**

- **≥ 11.0 tok/s → bandwidth-bound (A).** Arithmetic: rung 48 is 115.7 ms/token, of which 71.3 ms is
  spill-attributable above the 44.4 ms intercept. At 1.76× bandwidth that becomes ~40.5 ms → ~11.8 tok/s.
- **≤ 9.5 tok/s → compute-bound (B)**, and the NUMA-spreading explanation offered in Stage 4 §3 is wrong.
- **9.5–11.0 → mixed**, reported as mixed, with the implied split stated. Not resolved either way.

## Declared in advance

- **P-D2 and P-D3 are near-certain and are not the point.** More channels raise a streaming benchmark; that
  is physics, not a finding. They exist to confirm the upgrade worked so that **P-D5 means something**. A
  confirmed P-D2 with a falsified P-D5 is the informative outcome, not a contradiction.
- **Ranks are mixed, and the 1R sticks are the weaker ones.** Expect the four new channels to deliver
  somewhat less than the four existing ones. This suppresses P-D2/P-D3 slightly and is why the bars sit
  below a naive 2×.
- **A second, independent benefit is not measured here.** At full spill the working set is ~55.9 GB of expert
  weights plus the 28.8 GB CPU-resident PLE table — **~84.7 GB against 60 GB usable today**, so part of it is
  served from page cache over a SATA SSD. 128 GB removes that. **This confounds P-D5**: a rung-48 improvement
  could be bandwidth *or* capacity. **Disambiguator, declared now — rung 16 (18.6 GB of experts + 28.8 PLE =
  47.4 GB) already fits in 60 GB today**, so any improvement there is bandwidth and cannot be capacity. Score
  rung 16 alongside rung 48 and report both.
- **Reruns are the already-committed instruments** — `membw.c` and `flashnext_residency.py --stage4`, both
  unchanged, both under the Stage 4 prereg's conditions (`--numa distribute`, `-lv 4`, page cache dropped).
  No new code is written for this comparison.
- **Not a quality test.** Nothing about the weights changes.
- **Not yet purchased.** Two local leads on the identical Kingston SKU. If the parts that arrive differ from
  the table above — different rank, LRDIMM, a different capacity — **this prereg is void and is rewritten**,
  not quietly amended.

**Scorer:** the Stage 4 scorer (`tools/score_flashnext_spill.py`) is reused unchanged for the ladder half;
the triad half is a direct table comparison against the baselines above.

---

## Amendment 1 — 2026-09-14 09:47, before purchase: capacity also shows up at **load time**, and that is free to measure

Observed live while starting Flash-Next UD-IQ4_XS `-ncmoe 2` from a cold page cache (the tensor-split tests
had displaced it with Q2_K_XL). **This was not anticipated in the prereg above, and it is recorded before the
DIMMs are bought.**

The GPU side finished quickly — all four cards reached their ~60 GB `-ncmoe 2` footprint early. What took the
remaining time was the **28.8 GB CPU-resident PLE table** competing for a page cache that was already full
(`free`: 60 total, **0 free**, 57 buff/cache). Measured mid-load:

| quantity | value |
|---|---|
| **major faults** | **14,147,784** and climbing (~4 KB each ≈ 54 GB faulted from disk) |
| sustained read throughput | **~95 MB/s** — about 24k IOPS at 4 KB, i.e. *random* reads |
| the same SSD, sequential | ~500 MB/s |
| cold load, insufficient RAM | **10 min 53 s** (this run, 09:37:41 → 09:48:34) |
| warm load, same model and flags | **~2 min** (`RESULT_FLASHNEXT_RESIDENCY.md`) |

**Eviction pressure converts a sequential load into a random one, costing ~5×.** The decode ladder sees this
capacity limit only as a marginal-cost bump at rung 48; load time shows it as a **5.4×** penalty (10m53s
against ~2 min warm) — consistent with the ~5.3× sequential-to-random read penalty above.

**P-D7, committed now:** after the upgrade, a **cold-cache** load of Flash-Next UD-IQ4_XS at `-ncmoe 2`
completes in **≤ 6 minutes**, with major faults **below 4 million**. At 128 GB the 84.7 GB working set fits,
so the access pattern should revert to sequential.

**Corrected 09:52, same day:** this row first read "~16 min", extrapolated mid-load from the ~95 MB/s
read rate. **The run actually completed in 10 min 53 s** — the tail read faster than the middle, so the
projection was pessimistic by ~1.5×. P-D7's ≤ 6 min bar is unchanged and still a real prediction (1.8×
against the corrected baseline), but the motivating figure was wrong and is fixed here rather than left to
be compared against.

**Declared limits on P-D7:** cold-cache load time is noisier than the decode measurements — it depends on what
the page cache happened to hold and on SSD state — so it is scored as a **single ordinal check, not a ratio**,
and it is **not** evidence for or against P-D5. Drop caches (`echo 3 > /proc/sys/vm/drop_caches`) immediately
before both the baseline and the post-upgrade run, or the comparison is meaningless. **The pre-upgrade
baseline for P-D7 must be re-measured under that dropped-cache protocol** — the ~16 min above was an
incidental observation, not a controlled one, and is quoted here only as the motivation.

---

## Amendment 2 — 2026-09-14 11:15: **P-D7 is WITHDRAWN, and Amendment 1's mechanism was wrong**

Measured before purchase, which is the only reason this was caught. `loadmode/` holds the run.

**Three load modes, Flash-Next UD-IQ4_XS `-ncmoe 2`, `drop_caches` before each:**

| `-lm` | load | major faults | read | throughput |
|---|---|---|---|---|
| **auto** (mmap, the default) | **595 s** | **15,674,082** | 59.9 GB | ~103 MB/s |
| **none** | **141 s** | 1,147 | 60.6 GB | ~430 MB/s |
| **dio** | **137 s** | 1,140 | 60.5 GB | ~442 MB/s |

**mmap costs 4.3×.** `none` and `dio` are equivalent within noise.

### Amendment 1's explanation was wrong

It said: *"Eviction pressure converts a sequential load into a random one, costing ~5×."* **There was no
eviction pressure.** The `auto` run above began with **44 GB free** after a forced `drop_caches` and still
took 595 s with 15.7 M major faults. Compared against the earlier incidental run (653 s with the page cache
full), **having 44 GB free bought only ~9%** — nothing like what a capacity mechanism would give.

**The real mechanism: mmap faults the file in 4 KB at a time.** 15.7 M faults is what caps throughput near
100 MB/s on a drive that streams at ~450. Free RAM does not help because the faults are the cost, not the
eviction. llama.cpp prints the fix on every one of these loads — *"tensor overrides to CPU are used with
mmap enabled — consider using --load-mode none"* — and it was scrolled past three times today.

### P-D7 is withdrawn, not scored

P-D7 predicted a cold load **≤ 6 min** and **< 4 M major faults** after the upgrade. **`-lm dio` achieves
137 s and 1,140 faults on the existing 64 GB.** The prediction would have confirmed trivially and the
receipt would have credited the DIMMs for a flag. **It is withdrawn as confounded rather than scored**, and
**load time is no longer an argument for buying RAM.**

### What this does and does not do to the purchase

- **P-D5 (the bandwidth fork) is untouched.** It is the reason to buy, and it remains open.
- **The runtime capacity question is untouched and now sharper.** `-lm none`/`dio` must hold the CPU-side
  tensors *resident* — no file to page from. At `-ncmoe 2` that is ~30 GB (27.5 PLE + 2 layers) and fits in
  60 GB. **At rung 48 the CPU side is ~83 GB and cannot fit**, so deep spill may still require mmap and its
  4.3× penalty, or fail outright under `none`. **Untested — asserted as an open question, not a finding.**
  If it holds, the honest form of the capacity argument is *"128 GB lets deep-spill configurations use the
  fast loader"*, which is narrower and more specific than what Amendment 1 claimed.
- **Every measurement in Stage 4 used mmap**, including all six ladder rungs. Load times there are inflated;
  **decode numbers are unaffected** (loading finishes before any request is served).

### Consequence for Stage 5's protocol

**The post-upgrade reruns must pin `-lm` explicitly** and use the same mode as the baseline, or a 4.3×
loader difference will contaminate the comparison. The Stage 4 ladder rerun should pin **`-lm dio`**, and
the pre-upgrade baseline for any load-time claim must be re-measured under it.

## Amendment 3 — 2026-09-15 00:20. **A measured noise floor, and two gates that cannot survive it**

Written **before the DIMMs are purchased and before any arm of this experiment runs**, from evidence
produced by a different experiment (`RESULT_FLASHNEXT_BREAK.md`, Stage 5, 2026-09-14). This is new
information about the instrument, not a reaction to this experiment's data.

**Measured: decode on `.194` varies 2-4% run-to-run at fixed configuration, fixed binary, fixed clock
and byte-identical NUMA placement** (`B-16a` vs `B-16b`: -2.59% / -0.22% / -3.74%). Observed excursions
reach **7.0%** (`D-08` at ctx 500 against its own Stage 4 point). Nothing in this campaign had ever
measured this; every band written before today assumed it was negligible.

**P-D5 is unaffected and remains the reason to buy.** It predicts 8.64 -> >= 11 tok/s, **+27%**, which is
roughly 7x the noise floor. Likewise P-D2 (+54%) and P-D3 (+55%).

**Two gates are threatened, both of them tight bands on single runs:**

| gate | band as written | risk |
|---|---|---|
| pre-upgrade bridge, "must reproduce 2026-09-13 within **5%**" | 5% | **A noise excursion aborts a valid experiment before the machine is opened.** Tonight an identical-binary rung missed by 7.0% at ctx 500 |
| **P-D6 control**, rung 2 stays 22.33 **+-5%** | 5% | A chance breach is *defined* to mean "P-D5 is contaminated", so noise would discard the real result |

**Changes, all of which tighten evidence rather than loosen conclusions:**

1. **Both gates are scored on ctx 1800 and 3600, not ctx 500.** Ctx 500 carried the largest deviations
   all night (7.0% vs 4.5% and 3.9% at the same rung) — least work per token, so the most exposure to
   fixed per-token variation.
2. **Both gates require 3 RUNS, not 3 reps within one run.** Reps within a run share a placement draw
   and a page-cache state; they do not sample the thing that actually varies. **The gate is the median
   of three run medians.** This costs ~45 min per side and is the only way either band means anything.
3. **Bands stay at 5%** — on the median of three runs, not on one. A single run's band would have to
   widen to ~10% to be honest, which would make P-D6 useless as a control. Repeats buy the tightness.
4. **Rep 0 of every run is discarded before taking a median.** It is systematically 4-10% slow in every
   arm measured (the 64-token warmup never faults in the spilled experts). This is a known bias, not
   noise, and it is not defensible to leave it in.
5. **Record NUMA placement** (`/proc/<pid>/numa_maps`) on every arm. It does not explain the variance —
   pinning was tested and made throughput *worse* — but it is now cheap, and an unmeasured variable is
   how Stage 4's exchange-rate table ended up unfalsifiable.

**The threshold this sets, stated plainly: a DIMM upgrade that moves decode by less than ~4% is not
measurable by this campaign's method, however many channels it populates.** P-D5 expects 27%, so the
purchase decision is unaffected — but any secondary claim below that threshold must be reported as
"within noise", not as a small improvement.
