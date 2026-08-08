# Result — at a fixed byte budget, pruning is the worst way to spend it (but it is not dominated)

**Date:** 2026-08-07. `GLM-4.7-Flash` at five points holding **~13.2 GB constant** (12.90–13.21 GB,
2.4 % spread) while trading prune ratio against quantization depth. `.73` 2×P100 @ 1063 MHz / 150 W,
build `tom_default`, thinking OFF, temp 0, K=1, 714 probes/arm, `--max-tokens 160`, GLM chat template
forced on every arm. Pre-registered `PREREG_FIXED_BYTE.md` (`57a82de`).

**Gates:** G-1 `n_expert` 64/58/52/39/32 ✓ · G-1a `sigmoid` ✓ · G-1b chat template ✓ ·
G-5 `no_answer` spread **1.0 %** ✓ · imatrix absent on all five ✓.

`FBREAP50` is **reused verbatim** from `RESULT_REAP_DOSE_RESPONSE.md` — the identical file under
identical settings — and was known before this leg's pre-registration was written.

## Headline — the allocation

| arm | experts | pruned | quant | GB | **raw acc** | refusal | committed (n) |
|---|---|---|---|---|---|---|---|
| **FB-BASE** | 64 | 0 % | Q3_K_S | 13.03 | **39.6 %** | 53.1 % | 85.2 % (332) |
| FB-REAP09 | 58 | 9.4 % | Q3_K_M | 13.14 | 33.6 % | 53.1 % | 72.7 % (330) |
| FB-REAP19 | 52 | 18.8 % | Q3_K_L | 12.90 | 19.9 % | 68.2 % | 64.0 % (222) |
| FB-REAP39 | 39 | 39.1 % | Q5_K_S | 13.19 | 9.5 % | 74.2 % | 43.6 % (156) |
| FB-REAP50 | 32 | 50.0 % | Q6_K | 13.21 | **1.8 %** | 96.9 % | 59.1 % (22) *reused* |

```
~13.2 GB, raw accuracy:   39.6  ->  33.6  ->  19.9  ->  9.5  ->  1.8 %
```

**Perfectly monotone. At a fixed budget, every expert you remove costs you more than the bits you
buy back.** The unpruned 3-bit model beats the half-pruned 6-bit model by **37.8 pp** at the same
size — a 22× ratio.

## Prediction scoring (§8)

| id | prediction | conf | outcome |
|---|---|---|---|
| **P-F0** | GATE — FB-BASE raw ≥ 30 % | 0.80 | **HELD**, 39.6 % |
| **P-F1** | HINGE — FB-BASE beats FB-REAP50 by ≥ 30 pp | 0.85 | **HELD**, +37.8 pp |
| **P-F2** | raw accuracy monotone decreasing in prune ratio | 0.65 | **HELD**, no exceptions |
| **P-F3** | refusal monotone increasing | 0.70 | **HELD**, 53.1 → 53.1 → 68.2 → 74.2 → 96.9 % |
| **P-F4** | DOMINANCE — FB-BASE (13.03 GB) beats REAP-09 **Q6_K** (22.48 GB, 52.5 %) | 0.60 | **FALSIFIED**, 39.6 % vs 52.5 % |

**P-F4's falsification is the honest limit on the whole finding and is kept prominent.** A 3-bit
unpruned model at 13.03 GB does **not** beat a 6-bit lightly-pruned model at 22.48 GB. Bytes still
buy accuracy; you cannot recover 22 GB of performance from 13 GB by declining to prune. **REAP is a
bad allocation, not a dominated one.**

## The rate — pruning costs ~3× more accuracy per GB saved

Both compression axes measured from the same origin (BASE Q6_K, 24.61 GB, raw 68.9 %):

| route | to | GB saved | raw acc lost | **pp lost per GB saved** |
|---|---|---|---|---|
| **quantize** Q6_K → Q3_K_S | 13.03 GB | 11.58 | 29.3 | **2.53** |
| prune 9.4 % (Q6_K) | 22.48 GB | 2.13 | 16.4 | **7.70** |
| prune 18.8 % (Q6_K) | 20.34 GB | 4.27 | 36.3 | **8.50** |
| prune 39.1 % (Q6_K) | 15.70 GB | 8.91 | 57.8 | **6.49** |
| prune 50.0 % (Q6_K) | 13.21 GB | 11.40 | 67.1 | **5.89** |

**Quantization costs 2.53 pp of factual accuracy per GB saved; pruning costs 5.9–8.5.** Pruning is
**2.3×–3.4× less byte-efficient** at every ratio measured. That is the quantitative answer to
"is REAP worth the bytes?" for closed-book knowledge on this model: no.

## Compression-induced withdrawal is not specific to pruning

The most transferable observation here, and it was not predicted:

| model | size | refusal |
|---|---|---|
| BASE **Q6_K** | 24.61 GB | 11.2 % |
| BASE **Q3_K_S** — *no pruning at all* | 13.03 GB | **53.1 %** |

**Quantizing to 3 bits raises refusal from 11.2 % to 53.1 % with every expert still present.** The
withdrawal failure mode this campaign documented for pruned GLM is not a pruning signature — it is
what *compression generally* does to this model. It sits between REAP-19 (39.4 %) and REAP-39
(71.3 %) on the pruning ladder despite zero experts removed.

That weakens a claim the campaign never quite made but was drifting toward: that withdrawal
characterises *expert pruning*. It characterises a damaged GLM-4.7-Flash, however damaged.

## What this leg does and does not license

**Does:** at any budget where you must choose, spend bytes on experts and quantize the result. On
this model, for closed-book facts, there is no prune ratio that beats simply not pruning.

**Does not:** claim pruning is worthless. P-F4 failed — a lightly-pruned Q6_K at 22.5 GB beats
anything available at 13 GB. If your ceiling is 22 GB rather than 13, REAP-09 Q6_K (52.5 %) is the
best measured option at that size and no quantization point was tested there.

**Does not:** say anything about code or agentic ability, which is what REAP was calibrated to
preserve and where it demonstrably succeeds (+1.22 pp HumanEval+,
`RESULT_differential_knowledge_vs_code.md`). A shop that only needs code may still rationally prune.

## Limits

- **K=1, temp 0**, not reproducible on this fleet. Existence proof, not rate.
- **One quantization ladder point for the unpruned model** (Q3_K_S). The pp-per-GB figure for
  quantization rests on two points (Q6_K, Q3_K_S); a fuller base ladder would tighten it and is the
  obvious next leg.
- **Prune ratio and bit depth move together by construction.** This is a budget-allocation result,
  not a single-variable ablation, and the two orderings are the same axis read backwards.
- **13.2 GB only.** A different budget could reorder the arms; nothing here extrapolates.
- **One base model, one pruner, one packager pair.** REAP-the-method is not separated from Akicou's
  application of it.
- `FB-REAP50` **committed n = 22** — its committed figure is indicative only, per the rule adopted
  in `RESULT_REAP_DOSE_RESPONSE.md`. Its raw accuracy is unaffected.
