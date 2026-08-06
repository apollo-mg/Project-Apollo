# Predictions — HA-20 MTP leg re-run with `-cb` off

Logged 2026-07-30 **before** the run. Tests whether the deployment recipe from
`MTP_CACHEPROMPT_FALSIFICATION.md` (`-cb` off, prompt caching left on) eliminates the 35 %
scenario instability measured in `MTP_HA20_AND_MARGIN.md`.

## Design

**Single variable vs the original leg:** `-cb` removed from the server flags. Everything else
byte-identical — `run_ha20_mtp_ab.sh` unchanged in structure, same model, same
`-c 65536 -b 1024 -ub 512 -ctk f16 -ctv f16 -fa on -np 1 -ngl 99 --cache-ram 0 --jinja`, same
stevibe runner (`scripts/run-scenarios.mjs`, temp 0), same asymmetric K (base 1, MTP 3), same
**300 s / 240 s token-matched timeouts**.

**Timeouts deliberately NOT re-tuned.** With `-cb` off, MTP decodes at 97.6 t/s instead of 99.7,
so the 240 s budget is ~2 % tighter in tokens (23.4k vs 23.9k). Re-tuning would add a second
variable and break comparability with the original MTP arm. The headline measure — do the three
MTP reps agree *with each other* — is a within-arm comparison and does not depend on the absolute
budget. Noted as a small confound for scenarios that sit near the ceiling.

New output dir `ha20_mtp_ab_nocb/`; the original `ha20_mtp_ab/` is untouched.

## Baseline being tested against

Original leg (`-cb` on): base 14/20. MTP majority 14/20, but **7 of 20 scenarios (35 %) unstable
across the three reps** — HA-04, 07, 08, 10, 12, 14, 19 — plus 2 no-verdict runaways in rep 1.

## Predictions

| id | claim | confidence |
|---|---|---|
| **P-H1** | The three MTP reps agree on **≥18/20** scenarios (vs 13/20 agreement originally). | **0.70** |
| **P-H2** | Perfect agreement — **20/20**, all three reps identical. | **0.45** |
| **P-H3** | If any scenario still varies, **HA-07 or HA-08** is among them. | **0.60** |
| **P-H4** | MTP majority score is within 1 of base. | **0.70** |
| **P-H5** | Zero no-verdict runaways, or runaways that reproduce in **all three** reps rather than one. | **0.55** |

## Why P-H2 is well below what the probe result alone would suggest

The paired probe went 6/6 identical with `-cb` off, so pure numerics should now be deterministic.
But HA-20 is not a probe, and it has a nondeterminism source that has nothing to do with MTP:

**Wall-clock timeouts.** Scenarios are killed at 240 s. A scenario whose honest runtime sits near
that ceiling can time out in one rep and complete in another purely from machine jitter — no
numerical divergence required. HA-07 and HA-08 were exactly the two that hit the ceiling
originally, which is why P-H3 is stated separately: I expect any residual variation to be
**timeout artifacts, not numerics.**

That distinction is the thing this run has to establish. "Instability dropped from 7 to 1, and the
1 is a clock artifact" is a materially different — and much stronger — result than "instability
dropped from 7 to 1."

## Scoring — RUN COMPLETE 2026-07-30

**P-H1 FALSIFIED (16/20, needed 18) · P-H2 FALSIFIED · P-H3 FALSIFIED · P-H4 CONFIRMED ·
P-H5 FALSIFIED.** Four of five wrong.

Instability went **7/20 → 4/20**: improved, not eliminated. The probe's perfect determinism
under `-cb` off **did not transfer to the agent loop**.

P-H3 was wrong in the most informative way: I predicted residual variation would be a *clock
artifact* on the timeout-prone HA-07/HA-08. Those two were perfectly stable; the runaways hit
HA-04 and HA-05, which base finishes in ~40 s.

Two structural problems found that make the residual 20 % **unattributable to MTP**: there is no
base K=3 control, and the MTP arm runs all three reps against a *single* server process (the
paired probe restarts per rep).

Full analysis: **`HA20_MTP_NOCB.md`**.
