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
| cold load, insufficient RAM | **~16 min** (this run) |
| warm load, same model and flags | **~2 min** (`RESULT_FLASHNEXT_RESIDENCY.md`) |

**Eviction pressure converts a sequential load into a random one, costing ~5×.** The decode ladder sees this
capacity limit only as a marginal-cost bump at rung 48; load time shows it as a 7–8× penalty.

**P-D7, committed now:** after the upgrade, a **cold-cache** load of Flash-Next UD-IQ4_XS at `-ncmoe 2`
completes in **≤ 6 minutes**, with major faults **below 4 million**. At 128 GB the 84.7 GB working set fits,
so the access pattern should revert to sequential.

**Declared limits on P-D7:** cold-cache load time is noisier than the decode measurements — it depends on what
the page cache happened to hold and on SSD state — so it is scored as a **single ordinal check, not a ratio**,
and it is **not** evidence for or against P-D5. Drop caches (`echo 3 > /proc/sys/vm/drop_caches`) immediately
before both the baseline and the post-upgrade run, or the comparison is meaningless. **The pre-upgrade
baseline for P-D7 must be re-measured under that dropped-cache protocol** — the ~16 min above was an
incidental observation, not a controlled one, and is quoted here only as the motivation.
