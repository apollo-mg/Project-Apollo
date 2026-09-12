# Result — the stock base beat both finetunes on HumanEval+, and the replicate control is the only reason that is readable

**Run 2026-09-11 13:02 → 2026-09-12 00:37 on `.194`** (4× P100, sm_60, 150 W cap, clocks pinned
1063 MHz). Pre-registered in `PREREG_THREE_WAY.md` + Amendments 1–2, all committed before the data.
Raw: `results/`, `traces/`, `logs/`. Scored mechanically by `tools/score_three_way.py`; full output
in `score_output.txt`.

**164 HumanEval+ problems × K=3 × 4 arms = 1,968 completions, all four arms exit 0.**

## Headline

| arm | pass@1 pooled | sweeps | mean ± sd | median tok/completion | median decode | wall clock |
|---|---|---|---|---|---|---|
| **QWEN_R1** stock Qwen3.6-35B-A3B | **94.11%** | 93.29 / 94.51 / 94.51 | 94.11 ± 0.57 | **2,408** | 42.81 t/s | **8.32 h** |
| ORNITH_R2 Ornith-1.5 | 90.65% | 88.41 / 91.46 / 92.07 | 90.65 ± 1.60 | 632 | 42.81 t/s | 3.60 h |
| NEX_R1 Nex-N2.5-mini | 89.84% | 87.80 / 90.85 / 90.85 | 89.84 ± 1.44 | 280 | 47.93 t/s | 2.92 h |
| NEX_R2 *(same weights, other socket)* | 86.99% | 86.59 / 85.98 / 88.41 | 86.99 ± 1.04 | 270 | 48.09 t/s | 3.24 h |

**The stock base won.** Both finetunes aimed at "same speed, significantly smarter" landed below the
model they were tuned from. But the base bought those points with **8.6× the output tokens** and
**2.9× the wall clock**, and only one of the two comparisons survives its own significance test.

## The registered test, not the pooled difference

The prereg named the **paired per-problem sign test** as the test ("compare per-problem pass counts
(0–3) … exact two-sided sign test"), and pre-committed that "differences under about 3 points are not
expected to be distinguishable." That second sentence is load-bearing, because the pooled gaps all
land in one narrow band:

| pair | pooled gap | pass counts | discordant | sign test p |
|---|---|---|---|---|
| NEX_R1 vs QWEN_R1 | **−4.27** | 6 vs 23 | 29 | **0.0023** |
| NEX_R2 vs ORNITH_R2 | −3.66 | 12 vs 30 | 42 | **0.0079** |
| ORNITH_R2 vs QWEN_R1 | −3.46 | 6 vs 14 | 20 | 0.1153 |
| **NEX_R1 vs NEX_R2** *(same weights)* | +2.85 | 21 vs 11 | 32 | 0.1102 |

**Read the last row first.** NEX ran in both rounds, on different sockets, so that row is this
instrument measuring itself against a known null. On pooled points it produces a 2.85-point
"difference" — within 1.5 points of every cross-model gap in the table, which is exactly the
indistinguishable band the prereg warned about. On the registered paired test it correctly returns
**not significant**.

So the paired test discriminates where the pooled rates cannot: it clears the null pair and flags two
of the three cross-model pairs. **Had we scored this panel by subtracting two pass@1 numbers — which
is what we did to the CAL baseline last night and had to withdraw — all four gaps would have looked
alike, and the one real finding would have been indistinguishable from socket noise.**

## What each comparison actually supports

**NEX vs its own base: resolved.** 23 problems where QWEN is better, 6 where NEX is, p = 0.0023,
fully concurrent (99.9% overlap). The direction is the opposite of the claim that prompted the panel.
**Caveat: this is the sampling-confounded pair** — NEX ran its card's 0.7 / top_k 40, QWEN its card's
0.6 / top_k 20, and the prereg conceded "top_k 40 vs 20 is untested."

**ORNITH vs QWEN: direction only.** This is the **sampling-matched** pair — identical 0.6 / top_k 20
/ min_p 0, 100% concurrent — so it is the comparison least able to be explained away. It goes the
same way, and it does **not** reach significance (p = 0.1153, 20 discordant; the prereg's own bar was
"at least 6 discordant problems" all one way). The indirect path registered in Amendment 1 agrees:
−0.61 points through NEX.

**So the strongest form of "stock beats finetune" is the unresolved one, and the resolved one is
confounded.** Both point the same way; neither is clean. That is the honest state of it.

**Finetune vs finetune: not settled, and the drift control is why we know that.** P-T3 was registered
on NEX_R2. Scored as registered, ORNITH beats NEX significantly (p = 0.0079). Scored against NEX's
*other* replicate, the same comparison collapses:

| | pooled gap | discordant | p |
|---|---|---|---|
| NEX_R2 vs ORNITH_R2 *(registered)* | −3.66 | 12 vs 30 of 42 | **0.0079** |
| NEX_R1 vs ORNITH_R2 *(sensitivity)* | −0.81 | 15 vs 23 of 38 | 0.2559 |

One verdict, two answers, decided by which run of the same weights you happen to pick. **The
NEX–ORNITH result is an artefact of replicate choice and should not be cited in either direction.**

## Predictions

| id | prediction | result |
|---|---|---|
| P-T1 | NEX pass@1 > QWEN (R1) | **FALSIFIED** — 89.84 vs 94.11, p = 0.0023 |
| P-T2 | ORNITH pass@1 > QWEN | **FALSIFIED** — 90.65 vs 94.11 direct (p = 0.1153); −0.61 through NEX. Both paths agree in direction; neither is significant |
| P-T3 | NEX and ORNITH within 3 points (R2) | **FALSIFIED as registered** — 3.66 points — but see the sensitivity above; this verdict does not survive the other replicate |
| P-T4 | NEX uses fewer tokens than QWEN | **CONFIRMED** — 280 vs 2,408 median; paired p = 4.9e-32, QWEN longer on 152 of 164 |
| P-T5 | ORNITH more TRUNCATED than NEX (R2) | **FALSIFIED** — 1 vs 1, a tie. No arm looped |
| P-T6 | NEX decode within 5% of QWEN and ORNITH | **FALSIFIED** — NEX is **+12.0%** vs QWEN and **+12.3%** vs ORNITH. Falsified in the favourable direction |
| P-T7 | NEX R1 and R2 within 3 points | **CONFIRMED, weakly** — 2.85 points. It passes a bar the prereg itself called unresolvable, and the paired test on the pair is p = 0.1102. Read as "no detectable drift", not as "drift under 3 points" |

**2 confirmed, 5 falsified.** Our own prediction that a finetune would beat its base was wrong twice.

## Two findings nobody registered

**1. The base is dramatically more reproducible.** Same problem, three samples — how often does the
arm agree with itself?

| arm | always passes | flaky | never passes |
|---|---|---|---|
| QWEN_R1 | 151 | **5** | 8 |
| ORNITH_R2 | 142 | 14 | 8 |
| NEX_R1 | 132 | 27 | 5 |
| NEX_R2 | 122 | **36** | 6 |

QWEN is flaky on 5 of 164 problems; NEX on 27–36. The finetunes do not merely score lower, they
score *unstably* — and NEX's own two rounds disagree about how unstable it is (27 vs 36). For an
agentic harness, where a flaky step is retried and a consistent failure is caught, this asymmetry
plausibly matters more than 4 points of pass@1. It is untested here; it is the next experiment.

**2. NEX decodes 12% faster on identical architecture, and we cannot explain it.** Same shape (every
`config.json` field matched, prereg §Models), same packager and quant (bartowski Q4_K_M), same
binary, same box, same flags. Checked against the obvious confound — decode slows as the KV grows, and
NEX's answers are 8.6× shorter:

| arm | decode t/s by completion-length quartile | 200–400 tok only |
|---|---|---|
| NEX_R1 | 47.9@136 · 47.9@225 · 47.9@364 · 47.9@952 | 47.94 (n=183) |
| QWEN_R1 | 42.9@1247 · 42.9@2001 · 42.8@2714 · 42.6@3914 | 43.06 (n=4) |
| ORNITH_R2 | 42.8@266 · 42.8@523 · 42.8@757 · 42.7@1330 | 42.83 (n=85) |
| NEX_R2 | 48.1@135 · 48.1@221 · 48.1@363 · 48.0@866 | 48.11 (n=168) |

The within-arm slope is real but negligible (QWEN loses 0.7% across a 3× length range), and the
length-matched rates reproduce the whole gap. **So it is a property of the weights, not of answer
length** — and ORNITH is the *smallest* file (21.86 GB vs NEX's 22.32 GB) and the slow one, so it is
not bytes either. Open question; the GGUF metadata comparison needs `.194`, which is powered off.

## Integrity

**The f16 KV guard was checked positively, not by absence.** Amendment 2 restarted this panel because
buun's fork arms dynamic VBR KV when `-ctk`/`-ctv` are omitted. The guard is the absence of a
`VBR dynamic` log line, which proves nothing on its own — so the discarded v1 logs are the positive
control:

| | `VBR dynamic` lines |
|---|---|
| v1 INVALID — `server_NEX_R1`, `server_QWEN_R1` | 3, 3 |
| v2 SCORED — all four arms | 0, 0, 0, 0 |

Same binary, same box: it logs the line when VBR is armed. Nothing from the v1 run is scored.

## Deviations and limits

- **`EXEC_TIMEOUT` is a fifth bucket; the prereg registered four.** 1 / 3 / 2 / 2 across
  NEX_R1 / QWEN_R1 / ORNITH_R2 / NEX_R2. It is scored as a non-pass, i.e. against the arm. It lands
  hardest on QWEN, so it can only *understate* the winner's lead.
- **NEX_R2 and ORNITH_R2 had zero overlap**, not the partial overlap Amendment 1 anticipated (ORNITH
  ended 19:35, NEX_R2 started 21:23). The registered finetune-vs-finetune comparison was therefore
  fully sequential. NEX_R2 also ran with the box otherwise idle while every other arm ran alongside a
  second job — and it was the *weakest* arm, so the asymmetry does not flatter it.
- **Concurrency cost ~0.3% of decode**, reproducing `splitscale/RESULT_2V4.md`: NEX_R1 at 47.93 t/s
  alongside QWEN vs NEX_R2 at 48.09 t/s alone.
- **Sampling is declared, not controlled**, as registered. The one sampling-matched comparison
  (ORNITH vs QWEN) is the one that does not reach significance.
- **Nothing about agentic ability.** HumanEval+ is single-function Python at 164 problems, near a
  ceiling. Nothing about other quants, packagers, boxes, or "smarter" in general.
- **Nothing about the MTP heads.** All three carry one; none was used.

## The number that actually transfers

**NEX reaches 95.5% of the base's score on 11.6% of its output tokens** (89.84 / 94.11 pass@1;
280 / 2,408 median tokens) and finishes in a third of the wall clock. Whether 4.27 points is worth
8.6× the tokens is a deployment question, not a benchmark question — but this is the clearest
token-cost curve the campaign has produced, and it points the same way as the bit-depth work: the
cheap configuration gets most of the way there, and the expensive one is genuinely better.
