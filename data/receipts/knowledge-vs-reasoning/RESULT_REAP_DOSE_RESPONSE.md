# Result — REAP dose-response: the damage is monotone WITHDRAWAL, and it starts immediately

**Date:** 2026-08-07. `GLM-4.7-Flash` at 64 / 58 / 52 / 39 / 32 experts (0 / 9.4 / 18.8 / 39.1 /
50.0 % pruned). Base = mradermacher static Q6_K; pruned arms = Akicou, all Q6_K. `.73` 2×P100 @
1063 MHz / 150 W, build `tom_default`, `-c 4096 -ngl 99 -sm layer -np 1 --jinja`, thinking OFF,
temp 0, K=1, 714 probes/arm (T1 200, T2 200, T3 165, T4 149) after `--exclude-source researcher`.
Pre-registered `PREREG_REAP_DOSE_RESPONSE.md` (`6184f08`) + **AMENDMENT 1** (`a2831d0`).

**This is run 2. Run 1 is void** (93 pp G-5 trip — the Akicou GGUFs carry no chat template and
`--jinja` silently substituted ChatML). Raw arms retained at `reap_ladder_void1/` as evidence only.

**Gates, per arm, from the runtime's own output:** G-1 `n_expert` = 64/58/52/39/32 ✓ ·
G-1a `expert_gating_func = sigmoid` on all five ✓ · **G-1b** chat template loaded on all five ✓ ·
**G-5** `no_answer` spread **1.3 %** (0.0/0.0/0.0/1.3/0.0) ✓.

## Headline — the curve

| arm | experts | pruned | **raw acc** | refusal | committed | committed *n* |
|---|---|---|---|---|---|---|
| BASE | 64 | 0 % | **68.9 %** | 11.2 % | 77.7 % | 633 |
| REAP-09 | 58 | 9.4 % | **52.5 %** | 22.1 % | 67.9 % | 552 |
| REAP-19 | 52 | 18.8 % | **32.6 %** | 39.4 % | 54.7 % | 426 |
| REAP-39 | 39 | 39.1 % | **11.1 %** | 71.3 % | 44.6 % | 177 |
| REAP-50 | 32 | 50.0 % | **1.8 %** | **96.9 %** | 59.1 % | **22** |

```
raw accuracy   68.9  ->  52.5  ->  32.6  ->  11.1  ->   1.8     monotone, no exceptions
refusal        11.2  ->  22.1  ->  39.4  ->  71.3  ->  96.9     monotone, no exceptions
```

**GLM answers 68.9 % of 714 factual probes unpruned and 1.8 % at half its experts removed, and it
gets there by refusing, not by being wrong.** At 50 % it has effectively stopped answering.

## Prediction scoring (§8)

| id | prediction | conf | outcome |
|---|---|---|---|
| **P-L0** | GATE — base committed T1 ≥ 85 % | 0.80 | **HELD**, 94.9 % |
| **P-L1** | T1 committed non-increasing (3 pp slack) | 0.80 | **FALSIFIED** at 39→50 (57.3 → 80.0 %) |
| **P-L2** | HINGE — REAP-09 loses < 10 pp on T1 committed | 0.65 | **HELD**, +7.3 pp |
| **P-L3** | REAP-50 loses > 40 pp on T1 committed | 0.70 | **FALSIFIED**, +14.9 pp |
| **P-L4** | convex — 39→50 loss ≥ 3× 0→09 loss | 0.60 | **FALSIFIED** |
| **P-L5** | refusal rises monotonically | 0.55 | **HELD** — 11.2 → 22.1 → 39.4 → 71.3 → 96.9 % |
| **P-L6** | tail-selectivity is a dose effect | 0.50 | **FALSIFIED** |

**Scored exactly as written, on the pre-registered metric.** Three of these falsifications are
substantially artifacts of that metric (below). Re-scoring them on a metric chosen after seeing the
data is precisely what a pre-registration exists to prevent, so they stay falsified and the
explanation goes here rather than into the scoring.

## The real finding about the metric: committed accuracy breaks under withdrawal

`committed = correct/(correct+wrong)` has been this campaign's headline metric since
`PHASE1_RESULT_COMMITTED_ERROR.md`, chosen because it is immune to divergent *termination*. It is
**not** immune to divergent *refusal*, because refusals are excluded from the denominator:

```
REAP-50   692 refusals, 13 correct, 9 wrong   ->  committed n = 22 of 714
```

At 96.9 % refusal the survivors are a heavily self-selected sample — the model commits only when
overwhelmingly confident — so committed accuracy **rises** (44.6 → 59.1 %) while the model is
collapsing. That is the whole of P-L1's falsification and most of P-L3's and P-L4's.

**No prior leg could have found this.** GLM-REAP-25 refused 61.3 % and Qwen-REAP-20 refused 11.9 %;
neither approaches the regime where the denominator evaporates. It took pushing the dose to 50 % to
expose a limitation in the campaign's central instrument.

**Rule adopted:** report committed accuracy **with its denominator**, and treat any cell with
`committed n < 100` (14 % of the probe set) as indicative only. Where refusal exceeds ~50 %, raw
accuracy is the honest headline. `CAMPAIGN_SYNTHESIS.md` is updated accordingly.

## Is 9 % pruning free? No — and the metric said yes

**P-L2 HELD on its pre-registered terms** (committed T1 −7.3 pp, inside the 10 pp bar). The
practitioner's answer is still no:

```
REAP-09 vs BASE     raw accuracy  68.9 -> 52.5 %   (-16.4 pp)
                    refusal       11.2 -> 22.1 %   (doubled)
```

Removing 6 of 64 experts costs a quarter of the model's factual output. **There is no free band.**
The damage begins at the mildest rung available and is already large there — which combined with the
falsified calibration mechanism (`RESULT_QWEN_CALIBRATION_CONTRAST.md`) makes the practical claim
*expert pruning costs knowledge from the first experts removed, and no calibration recipe prevents
it.*

## Shape: linear-to-saturating, not convex (P-L4)

Raw-accuracy loss per rung, normalised by how much pruning each rung adds:

| step | Δ pruned | Δ raw acc | acc lost per pp pruned |
|---|---|---|---|
| 0 → 9.4 % | 9.4 | −16.4 | **1.74** |
| 9.4 → 18.8 % | 9.4 | −19.9 | **2.12** |
| 18.8 → 39.1 % | 20.3 | −21.5 | 1.06 |
| 39.1 → 50.0 % | 10.9 | −9.3 | 0.85 |

Damage per unit pruning is flat-to-declining, not accelerating. The late rungs look cheap only
because the model has almost no accuracy left to lose — a floor effect, not resilience. **The
expensive rungs are the early ones**, which inverts the saliency intuition REAP is built on: if
low-saliency experts really were near-free to remove, the first rung should have been the cheapest.
It was among the most expensive.

## Tier structure (P-L6 falsified, but the pattern is informative)

Committed accuracy by tier — read with the denominators above; REAP-39 and REAP-50 are thin.

| arm | T1 | T2 | T3 | T4 |
|---|---|---|---|---|
| BASE | 94.9 % | 91.7 % | 69.6 % | 32.4 % |
| REAP-09 | 87.6 % | 80.1 % | 48.6 % | 27.5 % |
| REAP-19 | 73.9 % | 63.6 % | 21.7 % | 5.7 % |
| REAP-39 | 57.3 % | 36.7 % | 26.1 % | 0.0 % |
| REAP-50 | 80.0 % | 40.0 % | 42.9 % | n/a |

Damage is **graded by obscurity** at the readable rungs — at REAP-19 the losses are T1 −21.0,
T2 −28.1, **T3 −47.9**, T4 −26.7 pp, with T3 hit hardest. P-L6 asked for T3+T4 loss ≥ 2× T1 loss at
REAP-09 and got 1.8× (13.0 vs 7.3 pp), so it fails as worded, largely because T4's *base* is already
32.4 % and has little room to fall.

This does **not** resolve the open GLM-uniform vs Qwen-graded contradiction. It shows GLM graded
under a *different pruner* (Akicou, not Cerebras), so pruner and ratio remain confounded with the
earlier GLM observation. The contradiction stays open.

## Failure mode: withdrawal at every dose

GLM withdrew at Cerebras-25 % (`RESULT_QWEN_CALIBRATION_CONTRAST.md`) and it withdraws at every rung
of this ladder, monotonically. Wrong answers rise then fall in absolute terms (141 → 177 → 193 →
98 → 9) purely because there are fewer committed answers at all. **Pruning this model does not make
it a confident liar; it makes it mute.** That is the safer of the two modes — Qwen-REAP fabricates —
and it is now shown to be dose-monotone rather than a threshold effect.

## Limits

- **Ladder construction — answered by the author 2026-08-08.** Asked whether the rungs are
  nested; Liu (@Akicou) replied that *"each pruned variant is based off the original base
  GLM-4.7 unpruned model repo."* That **rules out cascading** (rung N+1 pruned from rung N's
  weights rather than from the base), which was the failure mode that would have made the curve
  uninterpretable — accumulated damage rather than dose.
  **One assumption remains, and it is not what he was asked:** nesting of the *expert sets*
  additionally requires the saliency ranking to be identical across runs. REAP scores experts by
  router-gate × activation-norm over a calibration set, so if the same calibration data and seed
  were used at every ratio the ranking is fixed and the sets are nested by construction — the
  bottom 6 inside the bottom 12 inside the bottom 25. If calibration differed per ratio, each rung
  is a different *selection* as well as a different *quantity*, and the monotone decline would
  partly track which experts each run happened to choose. Starting from the same base makes the
  identical-ranking case very likely but does not establish it.
  Consequence for this receipt: the dose-response reading — one ranking, cut deeper — is
  supported, and the cascading-damage alternative is excluded.
- **K=1, temp 0**, not reproducible on this fleet (`DETERMINISM_TEMP0_GLM_P100.md`). Existence
  proof, not rate; no confidence interval on any single rung.
- **REAP-39 and REAP-50 tier cells are thin** (committed n = 177 and 22). T4 at REAP-50 is `n/a`.
  Nothing tier-level should be quoted from those two arms.
- **One pruner across the four pruned arms.** Ratio is isolated; REAP-the-method is not separated
  from Akicou's application of it, and the ratios are their labels — though header probes confirm
  retained-expert counts of 58/52/39/32 against a 64-expert base, consistent with those labels.
- **Base is a different packager** (mradermacher) from the pruned arms. Recipe, histogram, imatrix
  status and every architectural KV verified identical; residual unobservable differences remain.
- **Imatrix-free throughout**, so this curve describes static quants
  (`Instrument_Disagreement_PPL_vs_KLD.md` shows imatrix materially changes fidelity).
- **`--max-tokens 160` here vs 64 in earlier legs** (AMENDMENT 1). Absolute numbers are not directly
  comparable to `RESULT_QWEN_CALIBRATION_CONTRAST.md` or `PHASE1_RESULT_COMMITTED_ERROR.md`; the
  ladder is internally consistent, which is what dose-response needs.
- **Closed-book only.** Whether retrieval rescues these arms — it did at 100 % for both prior model
  pairs — is unmeasured here.
