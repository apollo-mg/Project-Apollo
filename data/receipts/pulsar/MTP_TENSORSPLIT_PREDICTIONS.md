# Pre-registered predictions: MTP speculative decode + `-sm tensor` on 2× P100

**Logged 2026-08-03 BEFORE any run.** Node `.73`, 2× Tesla P100-PCIE-16GB (sm_60),
build `TheTom/llama-cpp-turboquant` @ `d0e2a8b64` (upstream base 10281), 150 W / 1063 MHz.

## The claim under test

Mark: *"Bet that box would do 70 t/s with MTP on a Qwen 3.6 35B based MoE."*

Baseline for that model class, measured today (`CROSSOVER_LADDER_73.md` rung A):
**Hermes3.6-35B-A3B-APEX, `qwen35moe`, 39.86 t/s stock / 39.36 t/s fork.**
70 t/s therefore requires **1.76×**.

## ⚠️ The exact claim is not directly testable — no 35B MoE with an MTP head is on disk

GGUF header probe (`~/gguf_mtp_probe.py`, header-only — never reads the tensor region):

| model | arch | blocks | `nextn_predict_layers` | nextn tensors |
|---|---|---|---|---|
| Hermes3.6-35B-A3B-APEX | **qwen35moe** (MoE) | 40 | absent | **0 — no MTP head** |
| Qwen3.6-27B-Q6_K-MTP | qwen35 (**dense**) | 65 | 1 | 4 (`blk.64.nextn.*`) |
| DavidAU-Fable-Fusion-711-MTP-Q6_K | qwen35 (**dense**) | 65 | 1 | 4 (`blk.64.nextn.*`) |

So the MoE we benchmarked cannot run MTP, and the models that can are dense 27B. The testable
substitute is **the MTP speed-up factor on Pascal**, measured on the dense 27B, then reasoned
about — not asserted — for the MoE case.

## Predictions

**P-MTP1 (confidence 0.75): MTP yields < 1.5× on the dense 27B on this hardware.**
Mechanism: the fork's MTP carries a fixed per-round overhead (~7 ms/cycle, established in
turboquant #249 — net-negative on a 5090, 225 → 112.7 t/s, and positive only on bandwidth-poor
hardware). Pascal is the extreme bandwidth-poor end, so MTP should look *better* here than
anywhere in that thread. Anchor: pulsar reports 18.7 → 27.8 tok/s = **1.49×** on a dense
Qwen3.6-27B at 85% acceptance, depth 3 — on far newer silicon.

**P-MTP2 (confidence 0.75): a 35B-A3B MoE with an MTP head would NOT reach 70 t/s here.**
Mechanism, and the reason this is *not* just P-MTP1 restated: the MoE is fast **because only ~3B
params are active**, so its decode step is already ~25 ms. A ~7 ms fixed cycle overhead is then a
~28% tax — proportionally far worse than on a dense model with a slow step. Second, MoE batched
verify must read the **union of experts selected across all drafted tokens**, which grows with
draft depth; speculative decoding is structurally weaker on MoE than on dense for exactly this
reason. Expect ~1.2–1.4× → **48–56 t/s**, not 70.

**P-TS1 (confidence 0.6): `-sm tensor` is refused or ≤ `-sm layer` on these archs.**
Tensor split is implemented **per architecture** — established on this fleet when
`nemotron_h_moe` was refused outright (`APEX_IMINI_2xP100_NOFIT.md`) while `deepseek4` reached
runtime asserts after `ce3dce77b`. Whether `qwen35`/`qwen35moe` has an implementation is unknown.
If it loads, the P100 pair has **no NVLink** and sits behind `PHB`, so the extra cross-device
traffic tensor split implies should cost more than it saves. Mark's field experience is that
tensor split balances better than layer split, so this is the prediction most likely to be wrong.

## Scoring rules (fixed now)

- Warm/cold discipline per `DS4_DECODE_WARMUP.md`: discard pre-warm draws, K ≥ 3, report spread.
- A run that fails to load is a **result**, not a missing datum.
- Report acceptance rate alongside tok/s. High acceptance with flat throughput is the
  per-call-overhead signature (the #249 finding).
- Any figure quoted must come from tool output in the transcript, with the GPU clock state
  recorded (150 W / 1063 MHz, persistence enabled).


---

# SCORING (appended as results land — original predictions above are unedited)

## P-TS1 — **FALSIFIED** (confidence was 0.6, wrong direction)

Predicted: `-sm tensor` refused, or ≤ `-sm layer`, because the P100 pair has no NVLink and sits
behind `PHB`, so the extra cross-device traffic should cost more than balance saves.

Measured (turboquant `d0e2a8b64`, `-ngl 99`, n=64, temp 0, K=3, alternating):

| model | `-sm layer` | `-sm tensor` | gain | VRAM placement |
|---|---|---|---|---|
| Hermes3.6-35B-A3B (qwen35moe, MoE) | 37.69 / 39.63 / 39.60 | **41.55 / 43.56 / 43.58** | **+10%** | 12989/12191 → **12677/12677** |
| Qwen3.6-27B-MTP (qwen35, dense) | 7.92 / 7.94 / 7.93 | **13.34 / 13.36 / 13.37** | **+68%** | 10847/11199 → **10983/10983** |

**Both halves of the prediction were wrong.** Tensor split is supported on these archs *and* it
wins. The VRAM columns show the mechanism I missed: layer split places **unevenly** (12989 vs
12191; 10847 vs 11199) while tensor split is **exactly even**. On the dense 27B that imbalance
was costing 68%. Cross-device traffic evidently costs far less than the idle capacity created by
a bad layer partition — the opposite of my reasoning.

Reproducibility is tight (13.34/13.36/13.37; 43.56/43.58), so this is not run-to-run spread.

Mark's field observation ("tensor split seems to be more even than layer in my experience") is
confirmed and was a better guide than my mechanism argument.

### Sub-finding: `-sm tensor` needs explicit `-ngl`

```
W common_fit_params: failed to fit params to free device memory:
    llama_params_fit is not implemented for SPLIT_MODE_TENSOR, abort
```

This is the **auto-fitter**, not an architecture refusal — unlike `nemotron_h_moe`, which
additionally raised a hard `LLAMA_SPLIT_MODE_TENSOR not implemented for architecture` error
(`APEX_IMINI_2xP100_NOFIT.md`). With `-ngl 99` passed explicitly, `qwen35moe` and `qwen35` both
load and run. **Anything comparing split modes must pin `-ngl` or it will mistake a fitter abort
for missing support.**

## P-MTP1 / P-MTP2 — baseline invalidated, re-test in flight

A Qwen3.6-**35B-A3B** MoE **with** an MTP head now exists on `.73`:
`Qwen3.6-35B-A3B-UD-IQ4_NL-MTP.gguf` — `qwen35moe`, 41 blocks, `nextn_predict_layers=1`,
4 nextn tensors at `blk.40`, **17.26 GiB**. The exact claim is therefore directly testable, and
P-MTP2's premise ("no 35B MoE with an MTP head is on disk") no longer holds.

⚠️ **The 1.76× figure in P-MTP2 was computed against the wrong baseline.** It used Hermes-APEX
(23.93 GiB) at 39.86 t/s. The MTP model is a different, **28% smaller** quant (UD-IQ4_NL), so its
own no-MTP baseline will be higher — and `-sm tensor` adds ~10% on top. The multiplier MTP must
supply for 70 t/s is correspondingly smaller than predicted, which moves the odds toward the
claim. **The mechanism arguments in P-MTP2 (fixed ~7 ms/cycle overhead against a short MoE step;
expert-union growth during batched verify) still stand and are what the n-max sweep tests.**

The live test measures this model against **itself** (`--spec-type none` vs `draft-mtp`), which is
the only clean way to isolate MTP.


## P-MTP2 — **FALSIFIED** (confidence was 0.75)

Predicted: a 35B-A3B MoE would reach only ~1.2–1.4× → **48–56 t/s**, never 70.
Measured on `Qwen3.6-35B-A3B-UD-IQ4_NL-MTP.gguf`: **47.4 → 70.50 t/s = 1.487×** at n-max 3.
**Mark's 70 t/s call was correct.** Full receipt: `MTP_PASCAL_NMAX_MMVQ.md`.

Where the reasoning went wrong, specifically:

- **The ~7 ms/cycle overhead argument was not the binding constraint.** It is real — n-max 1 shows
  27.3 ms/cycle against a ~21 ms unassisted step — but acceptance was high enough (84% at n-max 1,
  72.5% at n-max 3) to pay for it several times over. I treated a real overhead as decisive without
  weighing it against the acceptance rate it had to beat.
- **The "expert-union growth during batched verify" argument was directionally wrong.** `mean len`
  rose monotonically with draft depth (1.84 → 2.52 → 3.17 → 3.43); nothing degraded gradually with
  batch size. The real limit is a **discontinuity** — the `mmvq_mmid_max` batch table on sm_60 —
  which no amount of reasoning about expert unions would have found.
- **P-MTP1 (< 1.5× on dense) is unscored** — the dense 27B was benchmarked without MTP only
  (7.93 layer / 13.36 tensor). The MoE result, 1.487×, sits just under the 1.5× line, and pulsar
  independently reports 1.49× on a dense Qwen3.6-27B, so the *magnitude* guess was reasonable even
  though P-MTP2's conclusion drawn from it was not.

**Score for the session: P-TS1 falsified, P-MTP2 falsified, P-MTP1 unscored.** Both scored
predictions were wrong, and in both cases Mark's field intuition (tensor split is better; the box
will hit 70 t/s) beat mechanism-based reasoning from first principles.
