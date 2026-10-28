# RESULT: three weeks of Strata releases bought +18 % on 4x P100 and +31-36 % on the RX 9070 XT

**Prereg:** `PREREG_STRATA_RERUN_027.md` (`1b9558f4`). Strata v0.2.7 (`5e8a4cca`) against our v0.1.39 receipts, on the
same weights and packs, the same prompts and harnesses, with drafting kept on (penalties off in the run config).

| host, model | prompt | v0.1.39 (Oct 5-6) | v0.2.7 (Oct 28) | change |
|---|---|---|---|---|
| .194 4x P100 (1,063 MHz), Flash-Next UD-IQ4_XS, experts spilling | reasoning-v1 | 37.2 (37.1 / 37.3) | **43.7** (44.3 / 43.7, two starts x 6 samples) | **+17.5 %** |
| .194 | code-v1 | not measured then | 42.3 | |
| RX 9070 XT, Flash-Next Coder IQ1_M | code-v1 | 52.6 (53.0 / 52.2) | **71.8** (clean start, 6 samples 69.9-75.6) | **+36.5 %** |
| RX 9070 XT | reasoning-v1 | 65.5 | **85.7** (82.7-88.1) | **+30.8 %** |

MTP acceptance: .194 reasoning 0.846 (October ~0.84), code 0.799; 9070 0.839 (October 0.846).

| # | prediction | result |
|---|---|---|
| R1 | .194 reasoning >= 40.0 | **holds**: 43.7 |
| R2 | 9070 code >= 57.9 | **holds**: 71.8 |
| R3 | acceptance within 0.05 of October | **holds** on both hosts |

**What changed besides the engine.** Each config is what v0.2.7's setup writes, as registered, so some of the gain is
setup's new choices, not the kernels. .194: setup dropped `--remote-expert-opt` (v0.1.39's installer had it) and added
`--ple-io ram` (the 29 GB n-gram table held in RAM), KV streaming and an automatic 4-GPU layer split. 9070: the same
pack, profile and `--spec 4` as October, plus `STRATA_RESIDENT_PIN=0`. Strata's release notes claimed +7-11 % and +6 % on
P100 and up to +38 % on a 16 GB Radeon; the measured gains are at or above those.

**Deviation and flags.** The first desktop code start ran while the desktop was short of RAM (Chrome, Discord and
Strata; 3 GB available). The kernel OOM-killed Chrome at 15:20:43, logged 3 allocation failures in that arm, and one
lmx pass wrote no file. That start (median 69.5, samples 43.8-77) is reported but not used. R2 rests on the second start,
which had no allocation failures, and it clears the bar by 24 % either way. Desktop Strata runs need the browser closed.

**Files:** `runs/run.log` (desktop), `runs_194.log` (.194), configs `october_*` and `v027_*`.
