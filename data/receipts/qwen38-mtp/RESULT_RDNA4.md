# MTP on Qwen 3.8 27B / RDNA4: 2.05x FASTER. Two independent reports of "slower" do not reproduce here.

**Date:** 2026-08-14 · **Node:** desktop RX 9070 XT (gfx1201), 16 GB, 1857 MHz at run
**Build:** `moe-cache-test/src/build-hip` @ `bb3c3fa` (HIP/ROCm 7.2)
**Model:** `Qwen3.8-27B-UD-IQ3_XXS` (11.10 GiB, dense, `qwen35`, 65 blocks), fully resident
**Serving:** `-ngl 999 -c 8192 -fa on -np 1`, temp 0 / top_k 1 / seed 1234, `n_predict 320`

## Why this was run

@JabbaTheDuck and @ekryski independently reported MTP making Qwen 3.8 **slower** — eric on
his own engine. Jabba has reported the same on earlier models, so the operator's read was
that it may be specific to one stack. That is what an independent fleet measurement is for.

## Result: 2.05x faster, with no position artifact

Arms alternated **off / on / on / off**, each with its own server launch, because this
fleet has produced 2-3.9x position artifacts on identical configs.

| arm | median t/s |
|---|---|
| off_1 | 27.18 |
| on_1 | **55.40** |
| on_2 | **55.28** |
| off_2 | 27.06 |

Off arms differ by **0.4%**, on arms by **0.2%**. Unusually clean for this hardware — the
effect is not positional.

## Speedup is strongly content-dependent

| prompt | off | on | speedup |
|---|---|---|---|
| `repeat` (write 1-60, one per line) | 26.75 | 62.59 | **2.34x** |
| `list` (first 30 primes) | 27.19 | 62.07 | 2.28x |
| `reason` (tank fill word problem) | 27.01 | 55.40 | 2.05x |
| `code` (LRUCache class) | 27.19 | 41.00 | 1.51x |
| `prose` (branch predictor, 3 paragraphs) | 27.22 | 40.52 | 1.49x |

Highly predictable output drafts well and approaches the 3-token draft ceiling; open-ended
prose and code accept fewer drafted tokens. **A benchmark using only one prompt type would
report anywhere from 1.49x to 2.34x** — which is one plausible route to disagreement between
stacks.

## A sealed prediction, falsified

Logged before the run: *"MTP will be slower here too, ~0.6"*, reasoning that
`nextn_predict_layers = 1` on a **dense** 27B means an expensive verify step relative to
the draft, unlike `mtp-sm60`'s 1.70x on a sparse 35B-A3B MoE.

**Wrong, and the mechanism was wrong.** The dense model got a *larger* speedup (2.05x) than
the MoE did (1.70x). Whatever governs MTP economics here, dense-vs-sparse is not it in the
direction assumed.

## Engagement proven before timing

```
srv: load_model: [spec] estimated memory usage of MTP context is 292.03 MiB
```

No `unused tensor` warnings on this build. That matters, because **the same model file on
`.194`'s CUDA build at the same commit discards all 15 `blk.64.*` tensors as unused** and
its `--spec-type` list omits `draft-mtp` entirely.

## The most likely explanation for the disagreement: build, not hardware

Support differs between forks on the same day, same model:

| build | `--spec-type` includes | `blk.64` tensors |
|---|---|---|
| desktop HIP `bb3c3fa` | `draft-mtp`, **`draft-dspark`** | wired up |
| `.194` CUDA `bb3c3fa` | neither | **discarded as unused** |
| `.194` `buun_vbr` | `draft-mtp`, `draft-dflash`, no dspark | not tested |

A stack whose build declines the draft heads still runs, just without speculation — and a
stack that engages them but drafts poorly on prose-heavy prompts would land near 1.5x. This
does **not** establish what either reporter's stack was doing; it establishes that "MTP is
slower on Qwen 3.8" is not a property of the model, because the same model is 2.05x faster
here.

## Not bit-exact — the standing caveat holds

**4 of 10 completions differed** between the off and on arms at temp 0 / top_k 1 / fixed
seed. Consistent with `mtp-sm60/SUMMARY.md`, which found 4 of 5 diverging against a clean
5/5 determinism control, and expected by construction: verifying k drafted tokens in one
pass is not the same arithmetic as k single-token passes.

**MTP is a serving win, never something to enable on one arm of a quality A/B.**

## Limits

- One quant (`UD-IQ3_XXS`), one card, one context length, `--spec-draft-n-max 3`.
- 2 reps x 5 prompts per arm. Tight variance, but small n.
- Determinism control not re-run here (off vs off byte-comparison); the divergence figure
  leans on `mtp-sm60`'s established control on different hardware.
- No quality measurement of any kind.
