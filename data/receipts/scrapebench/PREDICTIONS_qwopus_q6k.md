# Predictions — Qwopus-Fusion at Q6_K: quant or merge?

Logged 2026-08-01 **before** the run. ScrapeBench, `.73`, pinned serving config, temp 0.

## Why this is now the decisive test

`PREDICTIONS_merge_vs_dense.md` proposed a 2×2 to separate merge from density. The Fable
arm collapsed it:

| model | dense? | merged? | quant | temp-0 result |
|---|---|---|---|---|
| Genesis V5 | MoE | no | Q4 | clean, mean 0.998 |
| **Fable-Fusion-711** | **dense** | **merged** | **Q6_K** | **clean, mean 0.996** |
| **Qwopus-Fusion** | **dense** | **merged** | **Q4_K_M** | **BLEW UP** — 18.6×, INFRA_ERROR |

**P-M1 was falsified.** Fable is dense *and* merged — the same quadrant as Qwopus — and ran
all six tiers with no runaway, scoring 1.000 on t2, t3, t4 and t5.

So density is out, merge is out, and envelope-violation-alone is out (V5 and Fable both ran
outside their recommended sampling and were fine). Two candidates remain, and they differ by
exactly one variable that this run controls:

1. **Quantization** — Qwopus is Q4_K_M; every clean arm was Q6_K or a Q4 MoE.
2. **That specific merge** — different recipe, author and parents from Fable.

Running **the same merge at Q6_K** isolates it. Nothing else changes: same weights, same
merge, same server config, same fixtures, same temp 0.

## Predictions

| id | claim | conf |
|---|---|---|
| **P-Q1** | Qwopus **Q6_K** shows **no runaway** at temp 0 (no tier >400 s, no INFRA_ERROR) | **0.70** |
| **P-Q2** | t1_article completes in **<200 s** (vs 1290.2 s at Q4_K_M) | **0.70** |
| **P-Q3** | t2_boilerplate returns a scored answer rather than INFRA_ERROR | **0.72** |
| **P-Q4** | Mean score ≥0.95 across tiers that complete | 0.65 |
| **P-Q5** | If P-Q1 holds, the cause is **quantization**, not the merge | — (decision rule) |

**P-Q1 at 0.70, not higher.** Every degeneracy result this project has produced points at
low-bit — the Laguna stopping-rule failure, the Puzzle ladder, the "low-bit models fail at
stopping, not answering" through-line. Q4→Q6 is a real precision step. But the 50,000-character
tool argument was extreme even for Q4, and a merge can damage output calibration in ways that
higher precision only partially masks.

**If P-Q1 fails** — Q6_K blows up too — that is the more interesting result: the merge itself
is defective in a way precision cannot rescue, and it would be worth telling Kyle.

## Confounds

- **K=1.** A runaway observed is strong evidence; a runaway *not* observed is weaker, since
  it may simply not have been drawn. This asymmetry cuts against P-Q1.
- Q6_K is ~22.4 GB vs Q4_K_M's 16.8 GB, so decode will be somewhat slower per token. Wall-clock
  comparisons must not read that as a regression — the discriminator is the *ratio between
  tiers* (18.6× on t1 vs 1.6× on t3), not absolute seconds.
- Fable is Q6_K and clean, but it is a *different merge*. It cannot stand in for this one.

## Scoring

Score honestly on completion. **P-Q1 is the one to protect against motivated reading** —
"it was just the quant" is the tidy story that closes the investigation, and therefore the
one to be most suspicious of.
