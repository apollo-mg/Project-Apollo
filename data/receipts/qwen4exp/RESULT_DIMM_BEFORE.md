# Result — DIMM pre-upgrade baseline ("before"), the frozen anchor for P-D5/P-D6

**Run 2026-09-15 12:20–14:57 on .194, scored 15:08.** Prereg: `PREREG_DIMM_UPGRADE.md` (Amendments 3 + 4).
Data: `dimm_before_results.jsonl` (109 rows). Scorer: `tools/score_dimm.py` (mechanical implementation of
the preregistered rule — no band is chosen here after the data).

## Setup (recorded, so the after-run can prove it reproduced this)

- **Clock 1189 MHz / 250 W on all four P100s** — this is **out-of-spec** vs the post-efficiency-campaign
  1063/150 production setting, matched only for continuity with the cited spill-ladder figures. Do **not**
  read these as production numbers. `gates()` asserts this clock and aborts otherwise.
- `driver_sha = 8b11667589c5a05b…`, build `c7f114d34` (buun-c7f114d34/build_sm60), IQ4_XS shards verified
  against `flashnext_sha256.txt` at the gate.
- 3 separate launches per rung (independent first-touch placement draws), rungs 2 / 16 / 48, ctx
  {500, 1800, 3600}, reps 0–2 with **rep 0 discarded**. mmap load, `--numa distribute`, **no `--membind`**
  (rung 48's 27.5 GB PLE + spilled experts won't fit one node; pinning tested worse in Stage 5).

## The frozen before-medians  (median across L0/L1/L2 of each launch's median over reps 1,2)

| rung | ctx 500 | ctx 1800 | ctx 3600 | worst spread |
|---:|---:|---:|---:|---:|
| **2** (P-D6 control) | 21.08 (0.9%) | 20.83 (2.0%) | 19.11 (0.6%) | 2.0% |
| **16** | 13.77 (3.1%) | 13.69 (2.3%) | 12.85 (2.2%) | 3.1% |
| **48** (P-D5 fork) | 8.47 (10.7%) | 8.50 (15.0%) | 7.54 (8.6%) | **15.0%** |

(percent = full across-launch spread as a fraction of the median.)

## Findings

**1. Re-baselining was necessary, exactly as Amendment 3 anticipated.** The fresh 3-run rung-2 median is
**21.08 @ ctx 500 vs the historical single-run 22.33 (−5.6%)**; rung 48 is 8.47 vs 8.64 (−2.0%). Same clock,
same binary — this is between-session drift (uptime / cache state), larger than the 0.9% within-run spread.
**The frozen medians above are now the anchor**; the old single-run numbers are retired. This is precisely
why P-D5 was re-expressed as a ratio (Am4): a fixed "≥ 11 tok/s" bar would now be measuring against the
wrong baseline.

**2. The rung-2 control is tight (0.6–2.0%) — it will make a clean P-D6.** Two spilled layers touch almost
no host memory, so the DIMM upgrade must leave it put; a breach tomorrow means contamination.

**3. The placement lottery is real and it lives in rung 48.** Under byte-identical config, the three
full-spill launches spread **8.6–15.0%** — L2 drew a bad placement at ctx 500/1800 (7.61 / 7.24 vs ~8.5),
L1 drew a good one at ctx 3600 (8.18 vs ~7.5). This is the first-touch scatter that `--numa distribute`
cannot control and that rung 48 cannot pin around. It is the single biggest threat to the fork.

**4. P-D5 remains measurable — but the SNR is ctx-dependent, and thin at 1800.** The derived fork rise is
**+26–27% at every ctx** (spill is ~ctx-stable, so the ratio barely moves):

| ctx | before r48 | predicted after (B=1.54) | predicted rise | rung-48 spread | SNR (rise/spread) |
|---:|---:|---:|---:|---:|---:|
| 500 | 8.47 | 10.72 | +26.5% | 10.7% | 2.5 |
| 1800 | 8.50 | 10.73 | +26.2% | 15.0% | **1.7** |
| 3600 | 7.54 | 9.58 | +26.9% | 8.6% | **3.1** |

All three clear the unmeasurability clause (spread < predicted rise), so P-D5 is not declared dead. Both
preregistered ctx (1800 and 3600) are still scored tomorrow — this table does **not** drop one; it reports
the SNR each carries so the after-result is weighted honestly: **ctx 3600 is the high-SNR test (3.1), ctx
1800 the marginal one (1.7)** — at 1800 the placement spread is already 57% of the effect. If the two ctx
disagree tomorrow (3600 clears the bar, 1800 ambiguous, or vice versa), that split is reported as-is, not
resolved by picking the convenient one.

**5. The spill decomposition holds.** `spill(c) = t48 − t2 = [70.6, 69.6, 80.2] ms` across ctx — right on
the prereg's 71.3 ms and ~ctx-stable (the 3600 value is ~14% high, worth watching but within the story).
This validates the rung-2 "no host traffic" assumption the P-D5 formula rests on, and confirms
`rung48 − rung2` *is* the prereg's spill time, measured directly.

## For the after-run (tomorrow, post-swap)

- `python3 flashnext_residency.py --dimm-after` — identical arms (`DA-*`), same driver, same clock. `gates()`
  refuses to run unless the clock reads 1189/250 (a chassis reboot reverts it to 1063/150).
- Score with `tools/score_dimm.py <results.jsonl> DA`, then compare `DA` medians against the `DB` medians
  frozen here. **P-D5 confirmed (bandwidth-bound) iff rung-48 after-median rises ≥ its ctx's predicted
  value**, scored at both ctx 1800 and 3600 (3600 is the high-SNR read, 1800 corroborating). P-D6 confirmed
  iff rung-2 after-median stays within ±5% of 21.08 / 20.83 / 19.11. If P-D2 measures node-local bandwidth > 1.54×, recompute the fork band from the measured
  ratio once, and log it.
- Not-to-do: don't stage the REAP EXL3 download or heavy I/O on .194 during the after-run (page-cache
  eviction would perturb rung 48's already-fragile placement).
