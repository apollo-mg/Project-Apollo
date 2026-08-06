# Predictions — is the temp-0 runaway caused by MERGE or by DENSITY?

Logged 2026-08-01 **before** the runs. ScrapeBench on `.73`, 2× P100, pinned serving config.

## The question

`Qwopus3.6-27B-Fusion-Q4_K_M` at temp 0 produced ~50,000-character tool-call arguments,
18.6× wall-clock on the easiest tier, and a hard HTTP 500. At its recommended
temp 0.9 / top_p 0.9 the same tiers ran clean (`SAMPLING_ENVELOPE_QWOPUS.md`).

Mark's hypothesis: **dense models are more susceptible to sampling settings than MoEs.**

Competing explanation: **Qwopus is a merge** (geometry-weighted, 0.12 coding delta early →
0.48 late). Merging linearly combines weights from models whose logit distributions were
never trained to be averaged, which is a direct route to greedy-decode degeneracy.

**Genesis V5 is the fact that rules out "envelope violation alone."** V5 is a Qwen3.6-35B-A3B
derivative; Qwen3.6 recommends temp 1.0 for thinking mode. We ran it at temp 0 — the same
violation — and every tier completed in 40–140 s with no runaway.

## The 2×2, and what each cell decides

| | not merged | merged |
|---|---|---|
| **dense** | `q36` Qwen3.6-27B-Q6_K-MTP | `fable` Fable-Fusion-711 · `qwopus` (BLEW UP) |
| **MoE** | — | `v5` Genesis V5 (fine) |

`qcoder` (Qwopus3.6-27B-Coder-heretic) is a **parent** of the fusion — the sharpest single
test available. Parent fine + fusion broken ⇒ merge, not density.

## Predictions

| id | claim | conf |
|---|---|---|
| **P-M1** | `fable` (dense+merged) shows a runaway at temp 0 — any tier >400 s or an INFRA_ERROR | **0.55** |
| **P-M2** | `q36` (dense, unmerged) does **not** run away | **0.75** |
| **P-M3** | `qcoder` (parent, unmerged) does **not** run away | **0.70** |
| **P-M4** | If P-M2 and P-M3 hold and P-M1 fires, merge is the cause | — (decision rule) |
| **P-M5** | Every arm scores ≥0.9 on t1/t3_redirect when it does not run away | 0.80 |

**P-M1 at 0.55 — deliberately near a coin flip.** Fable-Fusion is merged *and* dense, so it
shares both candidate causes with Qwopus. But it is a different merge recipe by a different
author, and it already passed HermesBench at 55/61 under temp-0-adjacent conditions
(`hermesbench-p100/SUMMARY.md`), which is weak evidence against a catastrophic greedy failure.

**P-M2 higher than P-M1** because plain Qwen3.6-27B is a heavily-tested reference model;
a greedy-decode collapse in it would have been reported by others.

## Confounds recorded before the data

- **Quant is not matched to Qwopus.** These three are **Q6_K**; Qwopus-Fusion was **Q4_K_M**.
  Q4 is more degeneracy-prone in every measurement this project has made, so a *negative*
  result on the Q6_K arms does not fully exonerate merge — it could be the quant.
  `fable` vs `q36` **is** quant-matched, and that is the pair the conclusion should rest on.
- All three carry **MTP tensors**, loaded unconditionally (~307 MiB) but with no `--spec`
  flags, so speculative decoding is off. Same as every prior arm.
- **K=1 per arm.** A runaway observed is strong evidence; a runaway *not* observed is weak
  (it may simply not have been drawn). The asymmetry favours P-M1 firing over P-M2/P-M3
  holding.
- ScrapeBench is 6 tiers; the Qwopus blowup hit 2 of them. A single clean arm is not proof
  of robustness.

## Scoring

Score honestly on completion. **P-M1 is the one to protect against motivated reading** —
"merge causes it" is the tidier story and therefore the one to be suspicious of.
