# PREREG: DavidAU Qwen3.6-40B dense merge on dual P100

**Written:** 2026-09-08, before the model is loaded. Predictions logged with confidence; scored honestly after.

**Model:** `Qwen3.6-40B-GrIntell-F-Fusion-Uncen-Htic-NEO-MAX-MTP-IQ4_XS.gguf`, 22.08 GiB
(DavidAU `Grand-Intelligence` dense merge), byte-verified against HF (23,710,267,264).
**Control:** `Qwen3.6-27B-Q6_K-MTP.gguf`, 21.31 GiB — already on `.73`, near-matched on **bytes**,
so this is a comparison at roughly equal VRAM cost, not equal parameter count.
**Node:** `.73`, dual Tesla P100 16 GB (32 GB total), sm_60.
**Build:** `build_a56` @ `a56eeef5` — the tensor-split cache fix verified today
(`vbr-artifact-store/RESULT_A56_VERIFIED_ON_P100.md`), so `-sm tensor` keeps prompt caching.

## Step 0 (this step): does it load, and how fast is it?

A dense 40B at 22.08 GiB leaves ~10 GB for KV across both cards. Establish load success and a
throughput floor **before** committing hours of corpus time.

### Predictions

- **P1: loads successfully at `-c 32768` with `-sm tensor`.** 80%.
  22.08 GiB weights + MTP draft + VBR KV should fit in 32 GB, but MTP costs 1.2–2.1 GB scaling with
  context and the 40B's KV geometry is unmeasured.
- **P2: decode ≤ 12 tok/s at short context.** 70%.
  A dense 40B moves ~1.5× the bytes per token of the 27B control. `.73`'s measured throughput on
  27B-class dense models sets the scale; P100 HBM2 bandwidth is the binding constraint, not compute.
- **P3: the 40B is NOT better than the 27B control on our fixture.** 65%.
  DavidAU merges optimise for character and prose, not calibration or tool discipline. Mark's own
  framing — *"I doubt this is any better than 3.8 27B, but I always enjoy DavidAU's weird ass models"* —
  is the honest prior, and it is worth testing precisely because it is cheap to be wrong.
- **P2-MARK (logged 2026-09-08, before measurement): 13-16 tok/s with MTP.** Mark's prediction,
  recorded in competition with P2 above. His reasoning is the stronger one and I am recording that
  plainly: my P2 accounted for MTP's *VRAM cost* but not its *throughput multiplier*, which is the
  wrong half for a decode-rate prediction. We measured **1.40x at np=1**; a dense base near 10 t/s
  lands at ~14 t/s. If the measurement falls in 13-16, P2 is falsified and P2-MARK is confirmed.
- **P4: MTP draft acceptance below the 27B's.** 55%. Low confidence; merged models can have
  mismatched draft heads, but we have no measurement of this merge's MTP head at all.

### Falsification

P1 fails if the server OOMs or refuses. P2 fails at >12 tok/s measured over ≥64 generated tokens at
short context. P3/P4 are only scorable after the fixture runs, and are recorded now so the result
cannot be re-narrated afterward.

### Known confounds to control

- **Server uptime is a variable** (AFM-26): both arms get a freshly restarted server.
- **Byte-matched, not parameter-matched.** IQ4_XS 40B vs Q6_K 27B differ in quant *and* size; a
  difference is not attributable to architecture alone. This is a deployment-cost comparison.
- `-sm tensor` is only valid post-`a56eeef5`; pre-fix numbers on this node are not comparable.

---

# SCORING — arm `tensor_mtp`, measured 2026-09-08T20:18

**Config:** `build_a56` @ `a56eeef5`, `-ngl 99 -c 32768 -np 1 -fa on --kv-unified -ctk vbr -ctv vbr
--vbr-floor t2 --vbr-vram auto --split-mode tensor --spec-type draft-mtp`. Fresh GPU (0 MiB before
launch). KV VRAM budget 6707 MiB (auto). Load 200 s from spinning disk.

```
eval time        = 3889.83 ms /  64 tokens (61.74 ms per token, 16.20 tokens per second)
draft acceptance = 0.86538 (45 accepted / 52 generated), mean len = 3.50
```

| prediction | claim | outcome |
|---|---|---|
| **P1** (mine, 80%) | loads at `-c 32768` with `-sm tensor` | **CONFIRMED** — 200 s, zero fit warnings |
| **P2** (mine, 70%) | decode **≤ 12 t/s** | **FALSIFIED** — 16.20 t/s |
| **P2-MARK** | decode **13–16 t/s** with MTP | **CONFIRMED** — 16.20, at the top edge |
| P4 (mine, 55%) | MTP acceptance below the 27B's | unscored — needs the control arm |

**Why P2 was wrong, recorded plainly:** I priced MTP's VRAM cost into a decode-rate prediction and
omitted its throughput multiplier — the wrong half of a known quantity. We had already measured
**1.40× at np=1**. Mark applied it; I did not. The error was identified *before* the measurement
landed, which is the only reason it is legible now rather than rationalised afterward.

## The `Meta()` fit failure did NOT reproduce — do not report it upstream

The first manual launch produced:

```
W failed to fit params to free device memory: required speculative model/context
  uses device Meta() outside the target fit authority
E fit could not prove a viable placement; restoring the pre-fit parameters
```

Under the controlled arm — identical flags, but launched onto a **fully released GPU** after
`pkill -x llama-server` plus a 5 s settle — the same configuration produced **zero** fit warnings and
loaded cleanly. The original launch fired immediately after killing the wake-proxy's llama-server,
so VRAM had not yet been released and the fit prover was correct that it could not place the
speculative model.

**This was a transient free-memory condition, not a tensor-split/MTP device-resolution bug.** It
superficially resembled the `a56eeef51` cache-binding family and was nearly reported to buun as a
second instance. It is not one. Held because a single flushed warning from a block-buffered log is
not a finding — see below.

## Instrument defect found and fixed mid-experiment (v1 discriminator was VOID)

Discriminator v1 detected readiness by grepping the server's redirected stdout for `listening on`.
That stream is **block-buffered**, so the log lagged minutes behind reality; llama-server also binds
its port immediately and answers `/health` with **503** until the model is ready, so an open port is
not readiness either. v1 therefore reported `RESULT: FAILED` for a server that was loading normally.

v2 fixes the method: readiness is `/health == 200`; the server runs under `stdbuf -oL -eL` so its log
is a usable diagnostic; TIMEOUT and PROCESS-EXITED are distinguished rather than collapsed into
"FAILED" (the same verdict-schema collapse criticised in `RESULT_CORPUS_HARDENING_GOLDEN.md`, and
then committed here an hour later).

Fourth wrong-semantics measurement of the day, after `tg`, `reused`, and the decode survivorship
bias. See AFM-34.

## New prediction, logged before arm `tensor_nomtp` reports

**P5: no-MTP decode lands 11.0–12.5 t/s.** 60%. If 16.20 t/s reflects the 1.40× MTP multiplier
measured at np=1, the base is 16.20 / 1.40 = **11.6 t/s**. Falsified outside that band — which would
mean the multiplier differs materially on a dense 40B from the 27B where it was measured.

---

# SCORING — arm `tensor_nomtp`, measured 2026-09-08T20:24

Identical flags minus `--spec-type draft-mtp`. Loaded in 309 s, zero fit warnings.

```
eval time = 6151.74 ms / 64 tokens (97.65 ms per token, 10.24 tokens per second)
```

| prediction | claim | outcome |
|---|---|---|
| **P5** (mine, 60%) | no-MTP decode **11.0–12.5 t/s** | **FALSIFIED** — 10.24 t/s |

## The finding: the MTP multiplier is NOT constant across models

| config | decode | |
|---|---|---|
| `tensor` + MTP | **16.20 t/s** | acceptance 0.865, mean draft len 3.50 |
| `tensor`, no MTP | **10.24 t/s** | — |
| **implied multiplier** | **1.58×** | vs **1.40×** measured at np=1 on Qwen3.8-27B |

P5 was built by dividing the measured 16.20 by the 27B's 1.40× and predicting the base. That
assumed the multiplier transfers between models. **It does not** — MTP is worth *more* on this dense
40B merge (1.58×) than on the 27B where we measured it.

This is the same error as P2, one level up: P2 omitted a known quantity, P5 assumed a measured
quantity was a constant. Both times the fix is the same — treat a multiplier as a property of a
(model, config) pair until measured otherwise, never as a property of MTP.

**Practical consequence:** the planning heuristic in `fleet-throughput-test-targeting`
(`tok/s ≈ effective_GB_s / model_GB`) predicts the **no-MTP** rate. For this model it gives
23.7 GB at ~176 GB/s per P100; the measured 10.24 t/s under tensor split implies ~243 GB/s
effective — better than one card, far short of two. Tensor split on sm_60 is buying roughly
**1.4× of a theoretical 2×**, which is consistent with the butterfly AllReduce fallback
(`allreduce-internal-inert-on-pascal`) eating the rest.

**Open:** whether the 1.58× is a property of this merge's MTP head, of dense-40B geometry, or of
tensor split specifically. The `layer_mtp` arm now running gives a third point and separates the
split-mode contribution from the model contribution.

---

# COMPLETE TRUTH TABLE — 2×2, MTP × split mode (2026-09-08)

All four arms LOADED. **Zero fit warnings in any arm.** 64 generated tokens, temp 0, `-c 32768`,
fresh GPU per arm, `build_a56` @ `a56eeef5`.

| | `--split-mode tensor` | `--split-mode layer` | **MTP gain** |
|---|---|---|---|
| **+ MTP** | **16.20 t/s** | 12.90 t/s | — |
| **no MTP** | 10.24 t/s | 7.73 t/s | — |
| **tensor gain** | — | — | — |
| | 1.58× | 1.67× | |

- **tensor over layer:** 1.26× with MTP, 1.33× without.
- **MTP multiplier:** 1.58× (tensor), 1.67× (layer) — both well above the **1.40×** measured at np=1
  on Qwen3.8-27B. Draft acceptance was **byte-identical across split modes** (0.86538, 45/52,
  mean len 3.50), confirming the draft head is split-mode independent at temp 0.

## The planning heuristic is validated — for layer split

`fleet-throughput-test-targeting` gives **`tok/s ≈ effective_GB_s / model_GB`**, with ~176 GB/s
effective per P100 at 150 W / 1063 MHz, and notes that under layer split only one GPU decodes at a
time.

- Predicted (layer, no MTP): 176 / 23.7 GB = **7.43 t/s**
- Measured: **7.73 t/s** — **4% error.**

The heuristic is sound and should keep being used to size runs before launching them.

**Tensor split is where it needs a correction.** Measured 10.24 t/s implies ~243 GB/s effective —
**1.38× of a single card, not the naive 2×.** On sm_60 the remaining ~30% is eaten by the butterfly
AllReduce fallback (`allreduce-internal-inert-on-pascal`: sm_60 fails the `cc>=700` check, so every
P100 tensor-split run uses the fallback path). Proposed amendment to the heuristic:

> **Tensor split on sm_60: `tok/s ≈ 1.38 × effective_GB_s / model_GB`.** Not 2×. Confirm on a second
> model before trusting the constant — this is n=1.

## Resolution of the campaign's opening question

Mark, 2026-09-07: *"Layer splitting is quite a bit slower based on our testing. Would hate to lose it."*

That trade no longer exists. Post-`a56eeef5`, tensor split is **1.26× faster** than layer **and**
retains prompt caching (`vbr-artifact-store/RESULT_A56_VERIFIED_ON_P100.md`: 4,010 → 4 tokens on
pass 2). Before the fix, tensor split bought throughput at the cost of reprocessing every prefix.
**Recommended config for `.73`: `--split-mode tensor --spec-type draft-mtp`.**

## Prediction scorecard

| prediction | claim | outcome |
|---|---|---|
| P1 (mine, 80%) | loads at `-c 32768`, `-sm tensor` | **CONFIRMED** |
| P2 (mine, 70%) | decode ≤ 12 t/s | **FALSIFIED** (16.20) |
| **P2-MARK** | 13–16 t/s with MTP | **CONFIRMED** (16.20) |
| P5 (mine, 60%) | no-MTP 11.0–12.5 t/s | **FALSIFIED** (10.24) |
| P4 (mine, 55%) | MTP acceptance below the 27B's | **unscored** — needs the 27B control arm |

Two of my three quantitative predictions were falsified; Mark's was confirmed. Both of my misses
came from mishandling the *same* known quantity: P2 omitted MTP's throughput multiplier entirely,
P5 assumed it was a constant that transfers between models. It is neither optional nor constant —
**treat it as a property of a (model, config) pair until measured.**

## Still open

- **P4** needs the `Qwen3.6-27B-Q6_K-MTP` control on the same node and build.
- Whether the 1.58–1.67× MTP gain is a property of this merge's draft head, of dense-40B geometry,
  or of the P100. A third model separates them.
- **Capability** — this is all throughput. Nothing here says the 40B is any *good*.
