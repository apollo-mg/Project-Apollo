# Thinking compensates for quantisation damage — the gap collapses 25.0 pp → 3.3 pp from Q2 to IQ4

`.194`, 4× Tesla P100 (sm_60), **1063 MHz / 150 W** (idle 405 MHz at read time; the fleet
standing config since 2026-07-17). `llama_stock/build_puzzle` @ `73a55486c` (carries the
sm_60 fp32 carve-out). **NVIDIA-Nemotron-Labs-3-Puzzle-75B-A9B**, HumanEval+ 164 problems,
**K=3** (492 samples/cell), temp 0.7 / top_p 0.95 / top_k 20,
`-c 32768 -np 1 -ngl 99 -sm layer -ts 1,1,1,1 -fit off **-fa on**`.
Wall clock **2026-07-30 23:19:54 → 2026-08-01 11:45:12 (~36.4 h)**.
Predictions sealed pre-run in `PREDICTIONS_ladder_fa_on.md`.

## Result

| cell | pass@1 | pass@3 | non-stop | thinking leak |
|---|---|---|---|---|
| **q2_off** | **67.5 %** | 89.0 % | 3 | **21.1 %** |
| **q2_on** | **92.5 %** | 96.3 % | 7 | 3.9 % |
| **iq4_off** | **91.1 %** | 92.7 % | 0 | 0.0 % |
| **iq4_on** | **94.3 %** | 97.6 % | 2 | 0.4 % |

**Thinking gap: 25.0 pp at Q2_K → 3.3 pp at IQ4-XL.**

## The campaign's central hypothesis, confirmed

The claim under test since the offlabel#10 dispute: *thinking compensates for quantisation
damage, so its value shrinks as precision rises.*

It holds, and the effect is large. At Q2_K, turning thinking off costs **25 points**. At
IQ4-XL it costs **3.3**. Raising precision from ~2.5 bpw to ~4 bpw recovers 23.6 pp of the
non-thinking score (67.5 → 91.1) while moving the thinking score only 1.8 pp (92.5 → 94.3).

**Reading: reasoning tokens and weight precision are substitutes for this model.** A Q2 model
that thinks scores about the same as an IQ4 model that does not (92.5 vs 91.1). Practically —
if you can afford the VRAM, IQ4 buys you the option of skipping reasoning tokens; if you
cannot, thinking recovers most of what low-bit costs.

## The FA task-level result: a real fidelity difference that does not reach the task

`FA_EQUIVALENCE_SM60.md` measured `-fa on` vs `-fa off` on this exact model and hardware:
median KLD **0.000317**, same-top **98.686 %** — about **1 token in 76 changes its argmax**,
a larger perturbation than quantising BF16→Q8_0.

This ladder re-ran the q2 cells under `-fa on` against the earlier `-fa off` results:

| cell | `-fa off` (prior) | `-fa on` (this run) | delta |
|---|---|---|---|
| q2_on | 91.7 % | **92.5 %** | **+0.8 pp** |
| q2_off | 66.5 % | **67.5 %** | **+1.0 pp** |

**Both moves are under 1 pp, inside the ~2 pp noise floor pre-registered for K=3 on 164
independent problems.** So:

> Flash attention changes roughly 1 in 76 argmax decisions, and that does **not** produce a
> measurable task-level difference on HumanEval+ at K=3.

Both halves are now measured on the same model, same hardware, same protocol. The KLD finding
stands as a *fidelity* result and should not be restated as "FA costs you accuracy" — on this
benchmark it does not. Equally, PPL's blindness to the difference (0.999910) remains a real
instrument failure; it just isn't predictive of task harm here either.

## P-L4 falsified: low-bit models cannot reliably obey the thinking gate

Predicted 0.90 that every OFF cell would show 0 % thinking. **q2_off leaked reasoning on
21.1 % of samples**; iq4_off leaked **0.0 %**.

Same stopping-rule family as the Laguna finding and today's Qwopus tool-argument runaway:
**low-bit models fail at control, not at content.** The instruction to suppress reasoning is
a stopping constraint, and Q2_K obeys it 4 in 5 times.

This also partly confounds q2_off's 67.5 %: a fifth of those samples spent budget on
reasoning that was supposed to be off. The gap is real, but "thinking fully disabled at Q2"
is not a condition this stack can actually produce.

## Prediction scoring

| id | claim | conf | outcome |
|---|---|---|---|
| P-L1 | iq4_on > q2_on | 0.70 | **CONFIRMED** — 94.3 vs 92.5 |
| P-L2 | ON/OFF gap smaller at IQ4 than Q2 | 0.65 | **CONFIRMED** — 25.0 → 3.3 pp |
| P-L3 | iq4_off beats q2_off by ≥10 pp | 0.60 | **CONFIRMED** — +23.6 pp |
| P-L4 | every OFF cell passes the thinking gate | 0.90 | **FALSIFIED** — q2_off 21.1 % |
| P-F1 | q2_on differs from 91.7 % by ≥2 pp | 0.35 | **FALSIFIED** — +0.8 pp |
| P-F2 | q2_off differs from 66.5 % by ≥2 pp | 0.45 | **FALSIFIED** — +1.0 pp |
| P-F3 | both q2 arms move the same direction | 0.50 | CONFIRMED — both up (but both inside noise) |

4 of 7. **P-L2 — the one flagged pre-run as most at risk of motivated reading — is confirmed
on a 21.7 pp margin**, far outside any plausible noise. The two FA predictions were
deliberately hedged low (0.35, 0.45) and still failed, in the direction of *less* effect.

## Limits

- **One model.** Puzzle-75B is a NAS-derived architecture with heterogeneous layers and
  variable V embedding widths. The substitution result may not transfer.
- **One benchmark.** HumanEval+ rewards short verifiable programs; reasoning may pay off
  differently on tasks with no unit test.
- **K=3, 164 problems.** Effective SE ≈ 2 pp, not the ~0.4 pp a naive binomial suggests —
  which is exactly why the sub-1 pp FA deltas are reported as null, not as small effects.
- **The FA comparison is cross-session.** The `-fa off` q2 numbers come from the aborted
  ladder (2026-07-29); only FA and session differ. Same binary, same flags otherwise.
- **q2_off is confounded by the 21.1 % thinking leak** (above).
- pass@3 compresses the story: q2_off reaches 89.0 % given three attempts, so low-bit failure
  is substantially about *consistency*, not capability.

## Provenance

- `.194:~/hep/ladder_fa/` — `ladder_results_{q2,iq4}_{on,off}.json` (164 items each, per-task
  `passes`/`buckets`/`finishes`/`srcs`), `cell_*.log`, `ladder.log`, `ladder_traces_*/`
- Driver: `~/hep/puzzle_ladder_fa.sh`
- Prior: `PREDICTIONS_ladder_fa_on.md`, `FA_EQUIVALENCE_SM60.md`,
  `Instrument_Disagreement_PPL_vs_KLD.md`
