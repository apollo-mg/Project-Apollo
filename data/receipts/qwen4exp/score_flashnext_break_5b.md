## Ladder

| arm | -ncmoe | peak MiB | decode @1800 | imbalance I | anon/file MiB |
|---|---:|---:|---:|---:|---|
| D-08 | 8 | 54720 | 16.61 | 0.5883 | 882 / 10857 |
| D-10 | 10 | 52444 | 15.84 | 0.5399 | 881 / 13116 |
| D-12 | 12 | 50170 | 15.75 | 0.028 | 881 / 15391 |
| D-14 | 14 | 47900 | 14.48 | 0.3527 | 881 / 17674 |
| D-16 | 16 | 45626 | 13.58 | 0.6543 | 881 / 19935 |
| D-18 | 18 | 43350 | 13.00 | 0.5598 | 882 / 22224 |
| D-20 | 20 | 41076 | 12.54 | 0.5467 | 881 / 24486 |
| D-24 | 24 | 36506 | 11.49 | 0.6352 | 882 / 29040 |
| D-28 | 28 | 31896 | 10.37 | 0.6075 | 880 / 33583 |
| D-32 | 32 | 27146 | 10.87 | 0.1179 | 879 / 38571 |

## Marginal cost per spilled layer (adjacent rungs only)

| step | ms / layer | implied GB/s |
|---|---:|---:|
| 8 → 10 | 1.469 | 18.8 |
| 10 → 12 | 0.166 | 166.3 |
| 12 → 14 | 2.795 | 9.9 |
| 14 → 16 | 2.275 | 12.1 |
| 16 → 18 | 1.660 | 16.6 |
| 18 → 20 | 1.407 | 19.6 |
| 20 → 24 | 1.812 | 15.2 |
| 24 → 28 | 2.362 | 11.7 |
| 28 → 32 | -1.109 | nan |

## Predictions

- **P-B7 (replication, read this first)**: FALSIFIED — D-08 @500 16.37/17.60 (-7.0%) @1800 16.61/17.39 (-4.5%) @3600 15.22/15.84 (-3.9%); D-16 @500 13.69/13.57 (+0.9%) @1800 13.58/13.60 (-0.1%) @3600 12.95/12.84 (+0.8%); D-32 @500 10.85/10.75 (+1.0%) @1800 10.87/10.72 (+1.4%) @3600 10.30/10.29 (+0.1%) — worst deviation 7.0%
    - **Stage 4's marginals are not reproducible on an identical binary and box.** P-B1–P-B3 below are reported but NOT interpretable: a break cannot be distinguished from run-to-run variation that exceeds it.
- **P-B1 (two regimes)**: CONFIRMED — shallow mean 1.676 ms/layer vs deep 1.022, **ratio 1.64×** (band ≥ 1.40)
- **P-B2 (break location)**: FALSIFIED — largest single drop 3.471 ms/layer at step midpoint **30** (band [14, 24])
- **P-B3 (step, not ramp)**: CONFIRMED — the largest step carries **56%** of the total decline (band ≥ 50%); **≥4 steps each carry <25% — this is a ramp**
- **P-B4 (placement vs depth)**: **DESCRIPTIVE, no verdict** (Amendment 4) — I by rung: 8:0.588, 10:0.540, 12:0.028, 14:0.353, 16:0.654, 18:0.560, 20:0.547, 24:0.635, 28:0.608, 32:0.118
    - range 0.028–0.654, spread 0.626; run-to-run swing at a FIXED rung was 0.116, so a trend smaller than that is not a result
    - I(8) 0.5883 vs I(32) 0.1179, difference +0.4704 (what the retired band asked for: ≥ 0.10 — reported, not scored)
- **P-B5 (MiB/layer constant)**: CONFIRMED — mean 1145 MiB/layer, worst deviation 3.7% (band ±15%)
- **P-B6 @ 8**: NOT TESTABLE (arm or control missing)
- **P-B6 @ 24**: NOT TESTABLE (arm or control missing)
- **P-B9 (capacity boundary)**: FALSIFIED — I(24) 0.635 (want > 0.35), I(28) 0.608 (want < 0.35)

  host residency by rung (fit: ~1150 MiB/layer + 1800):
    - rung 8: 11,739 MiB, I=0.5883, fits one node
    - rung 10: 13,996 MiB, I=0.5399, fits one node
    - rung 12: 16,272 MiB, I=0.028, fits one node
    - rung 14: 18,555 MiB, I=0.3527, fits one node
    - rung 16: 20,816 MiB, I=0.6543, fits one node
    - rung 18: 23,106 MiB, I=0.5598, fits one node
    - rung 20: 25,367 MiB, I=0.5467, fits one node
    - rung 24: 29,923 MiB, I=0.6352, fits one node
    - rung 28: 34,463 MiB, I=0.6075, **exceeds one node**
    - rung 32: 39,450 MiB, I=0.1179, **exceeds one node**

## P-B8 — clock elasticity by spill depth (1189 MHz / 250 W vs 1063 MHz / 150 W)

- rung **8**: 16.61 @1189 vs 16.60 @1063 — **0.1%** lost to a 10.6% clock cut (elasticity 0.00)
- rung **16**: 13.58 @1189 vs 12.58 @1063 — **7.4%** lost to a 10.6% clock cut (elasticity 0.70)
- rung **32**: 10.87 @1189 vs 9.77 @1063 — **10.1%** lost to a 10.6% clock cut (elasticity 0.95)
- **P-B8**: FALSIFIED — sensitivity 0.1% at rung 8 vs 10.1% at rung 32, **-10.0 points** (band ≥ 3.0)

- **P-B0 (load-mode gate)**: FALSIFIED — load 606.7s → 155.3s; I 0.7564 vs 0.9963 (Δ 0.2399, band ≤ 0.05); decode 12.58 vs 12.12 (-3.6%, band ±3%)
    - **dio engaged: True** — functional evidence (load time), not a log string. log hits for 'direct-io': 0

**The foil — do not quote this.** A single linear fit through all 10 rungs gives 1.566 ms/layer at R² = 0.9496. Stage 4's R² was 0.9907 across a real 1.7× break. **A high R² here is evidence of nothing; read the marginals table.**
