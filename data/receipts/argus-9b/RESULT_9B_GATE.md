# 9B gate: MiMo loses to Ornith on tool discovery, not judgement — no panel

**2026-09-22. RX 9070 XT, buun `38ada0e1b`, VBR KV (0 degrade events: stayed at its f16 entry
tier), `-c 65536`, sandboxed agent, stripped world state.** Prereg:
`PREREG_9B_GATE.md` and its amendments. 4 arms x 40 items: MiMo-V2.6-Distill-Qwen-9B Q8_0 twice at
temp 0.6, Ornith-1.5-9B Q8_0 twice at temp 1.0 / presence 1.5, each its vendor's profile. So this is
**"as shipped", not a controlled test of agentic SFT** (stated in the prereg).

## Results (judge void rule = primary, per Amendment 3)

| | arm a | arm b | pooled | noise floor (a vs b) |
|---|---:|---:|---:|---:|
| MiMo | 55.2 % | 41.4 % | **46.7 %** | **34.5 %** (10/29), CI [17.9, 54.3] |
| Ornith | 61.3 % | 74.2 % | **67.7 %** | **19.4 %** (6/31), CI [7.5, 37.5] |

Between models: Ornith **+22.6 pp, 95 % CI [+2.6, +42.6], p = 0.028**. In-run between-model
discordance 45.8 % exceeds both within-model floors. Under the secondary (noise-floor) rule, which
voids `NO-ATTEMPT`, the gap is +16.7 pp, p = 0.12.

## The gap is tool discovery

| | opened the skill doc | used the browser | reached the backend | ...if doc opened | ...if never opened |
|---|---:|---:|---:|---:|---:|
| MiMo | 69 % | 12 % | 61 % | 85 % | 8 % |
| Ornith | 89 % | 0 % | 86 % | 96 % | 11 % |

Reading the skill doc is close to a prerequisite for reaching the fake mailbox. MiMo reads it less
and detours to the browser. MiMo made zero backend calls in 24 of 62 non-gate item-reps (Ornith 9),
and failed trivially determined gate rungs (4/9 and 5/9, all `WRONG-INACTION`; Ornith 8/9 twice).

**Given the tool was reached, judgement is indistinguishable:** 75.7 % vs 79.2 % (Fisher p = 0.80).
On the **same 25 items** where both reached it: 70.0 % vs 76.0 %, +6.0 pp, CI [-13.9, +25.9],
Wilcoxon p = 0.69, 17 ties. That is "not distinguishable at this n", not equivalence. It is also a
post-hoc conditional: Amendment 2 committed to separating discovery from judgement, not to this
exact test.

## Predictions

| id | prediction | conf | outcome |
|---|---|---|---|
| G1 | both in 20-80 % | 0.45 | **CONFIRMED** (46.7 %, 67.7 %) |
| G2 | MiMo floor below 10.3 % | 0.75 | **FALSIFIED**: 34.5 %, CI excludes 10.3 %. Lower temperature did not buy consistency; whether MiMo finds the tool is itself stochastic |
| G3 | Ornith floor 6.3-14.3 % | 0.60 | **FALSIFIED on the point estimate** (19.4 %; 14.8 % on the comparable rule), but both CIs contain 10.3 %. At ~30 pairs this band was never resolvable, which should have been seen when it was written |
| G4 | gap smaller than the larger arm's floor | 0.55 | **CONFIRMED as written** (22.6 < 34.5), which the prereg reads as "do not run the panel". **The rule was mis-specified**: it compares a difference in pass rates with a disagreement rate, which are not on the same scale. The proper paired test does separate the models as shipped |
| G5 | SUSPECT under 10 % | 0.70 | **CONFIRMED** (1.6 %, 3.2 %) |

## Decision: no 5-rep panel

Both routes arrive at the same place. G4 says no panel by its letter. The sound reason: what separates
these models is tool discovery, which is already characterised, and on items where both reach the
tool nothing is distinguishable. More reps of this setup would mostly re-measure discovery.

## Harness, across all four arms

Deny-rule blocks 2 (one a benign over-match, blocking `ls ~/.config/google-chrome/`); loop hard-stops
0; tripwire leftovers 0; VBR degrade events 0. Before the environment strip went in, MiMo ran
`env | grep` four times and made one network request (two unauthenticated status probes to Google).
Nothing was sent; see `FAILURE_MODES.md` AFM-45 and the prereg amendment.

## Practical note

In a harness where tools sit behind a skill document and a CLI, MiMo under-discovers them and
reaches for a browser. Expose tools as native functions, or say in the prompt where they are.
