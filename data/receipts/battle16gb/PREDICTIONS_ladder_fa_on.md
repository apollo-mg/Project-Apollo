# Predictions — Puzzle quant ladder v2 (`-fa on`, Q2_K + IQ4-XL)

Logged 2026-07-30 **before** the run. Supersedes the aborted `-fa off` ladder
(`~/hep/ladder/`, 2 of 6 cells, q4/iq4 OOM'd).

## Design change and why

`FA_EQUIVALENCE_SM60.md` measured `-fa on` vs `-fa off` at median KLD **0.000317**, same-top
**98.686 %** — a larger perturbation than quantising BF16→Q8_0. FA settings therefore cannot be
mixed across rungs. `-fa off` is not viable (IQ4/Q4 OOM from Puzzle's V-cache padding), so
**every cell re-runs with `-fa on`**.

Q4_K_M dropped: it and IQ4-XL are both ~4-bit, IQ4-XL is the one Mark would actually deploy, and
Q4_K_M's 48 GiB needs a hand-tuned `-ts` that adds a variable without adding signal.

**4 cells:** {Q2_K, IQ4-XL} × {thinking ON, OFF}. K=3, 164 HumanEval+ problems, 492 samples/cell,
temp 0.7 / top_p 0.95 / top_k 20, `-c 32768 -np 1 -ngl 99 -sm layer -ts 1,1,1,1 -fit off -fa on`.
Output to `~/hep/ladder_fa/`; the FA-off results are preserved untouched.

## The 21 sunk hours are not entirely sunk

The completed FA-off cells (`q2_on` **91.7 %**, `q2_off` **66.5 %**, thinking gate clean at
100 %/0 %) become the **FA-off arm of a paired task-level comparison**. Re-running q2 under
`-fa on` gives a same-model, same-protocol A/B on the *only* variable that changed.

That is a materially stronger claim than the KLD result alone. KLD says the distributions differ;
this says whether it **changes what the model actually scores** — which is the question anyone
reading the FA finding will ask first.

## Predictions — FA task-level effect (the bonus experiment)

| id | claim | confidence |
|---|---|---|
| **P-F1** | q2_on under `-fa on` differs from 91.7 % by **≥ 2 pp** | **0.35** |
| **P-F2** | q2_off differs from 66.5 % by **≥ 2 pp** | **0.45** |
| **P-F3** | Both q2 arms move in the **same direction** | 0.50 |

Sampling noise sets the floor: 492 samples but only 164 independent problems (K=3), so effective
SE is ~2 pp, not the ~0.4 pp a naive binomial gives. **A shift under 2 pp is not distinguishable
from noise**, which is exactly why P-F1 sits at 0.35 rather than high — 1.3 % of tokens changing
argmax need not move a pass/fail boundary.

P-F2 > P-F1 because 66.5 % sits nearer 50 %, where binomial variance peaks, and because the OFF
arm has no reasoning trace to self-correct a diverged token.

## Predictions — ladder science

| id | claim | confidence |
|---|---|---|
| **P-L1** | iq4_on > q2_on | **0.70** |
| **P-L2** | The ON/OFF gap is **smaller at IQ4 than at Q2** (Q2 gap = 25.2 pp) | **0.65** |
| **P-L3** | iq4_off beats q2_off (66.5 %) by **≥ 10 pp** | **0.60** |
| **P-L4** | Every OFF cell passes the thinking gate (0 % fired) | **0.90** |

**P-L2 is the campaign's central hypothesis** — that thinking compensates for quantisation
damage, so its value shrinks as precision rises. Q2's 25.2 pp gap is enormous next to Laguna Q2's
2.7 pp, so there is a lot of room for it to close. If P-L2 and P-L3 both hold, the story is
"low-bit models need thinking to recover what precision would have given them for free," which is
directly what the offlabel#10 dispute was about.

If P-L2 **fails** — the gap staying wide or widening at IQ4 — that is the more interesting result
and argues thinking's value is not a quantisation-compensation effect at all.

## Runtime

FA-off timings were q2_on **17.7 h**, q2_off **3.5 h**. IQ4-XL is 1.4× the weights (41.6 vs
29.3 GiB) at 11.22 t/s decode measured. `-fa on` may shift this either way — untested at this
scale.

**Estimate 50–70 h**, i.e. finishing 2026-08-02 give or take a day. Stated as a range because I
have underestimated this ladder twice (9–12 h/cell predicted, 17.7 h actual). Treat the upper
bound as the planning number.

## Scoring

Score all seven honestly on completion. P-L2 is the one to protect against motivated reading —
it is the hypothesis the campaign wants to be true.
