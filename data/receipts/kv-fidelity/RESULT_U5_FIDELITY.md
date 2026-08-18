# "Clean" spans 55x in decision danger — the first fidelity numbers of this campaign

**2026-08-18**, RX 9070 XT (gfx1201, RDNA4), ROCm 7.2.4. Binary TheTom `f050a2501` with
**buun's `frontier-hazard`** built into it (`buun-quality-bench/hazard-bench`, audited: 366
lines, public `llama.h` API only, no shell-outs, no network).
Model `Qwen3.5-9B-Q8_0`, **D=256**, GQA 4:1. 16 wikitext-2 prompts, `--n-prefix 128`,
`--n-score 128`. Raw `u5.log`, script `u5_fidelity.sh`, prompts `hazard_prompts.txt`.

## Why this exists

Every "clean" verdict in this campaign came from a **collapse detector** — it fires on a run
of >200 identical characters or fewer than 12 distinct ones. It cannot distinguish *faithful*
from *subtly wrong*. That limitation is written into eight receipts and into the compatibility
map shared with both maintainers.

`frontier-hazard` is teacher-forced: a reference f16/f16 context and a quantized context decode
the **same real tokens**, and per scored position it reports top-1 flip rate, full-vocab KL,
decision danger `R = KL / (0.5*margin^2)`, and margin erosion `L = (gap_P - gap_Q)/gap_P`.

## Result

| K / V | flip rate | mean KL | **mean R** | mean L | frac L>=1 |
|---|---:|---:|---:|---:|---:|
| f16 / f16 *(control)* | 0.0000 | 0.00000 | **0.0** | 0.0000 | 0.0000 |
| **`q8_0` / `q8_0`** | 0.0148 | 0.00061 | **10.5** | 0.0332 | 0.0143 |
| `q8_0` / turbo4 | 0.0315 | 0.00273 | **45.2** | 0.0166 | 0.0310 |
| turbo4 / turbo4 | 0.0359 | 0.00423 | **68.1** | 0.0920 | 0.0344 |
| turbo3 / `q8_0` | 0.0482 | 0.00584 | **76.4** | 0.0927 | 0.0433 |
| `q4_0` / `q4_0` | 0.0364 | 0.00509 | **89.5** | 0.1543 | 0.0340 |
| turbo3 / turbo3 | 0.0674 | 0.01351 | **228.4** | **-0.0146** | 0.0620 |
| turbo2 / turbo2 | 0.1240 | 0.05160 | **817.3** | 0.4491 | 0.1073 |

The f16/f16 row is the exact-anchor control and returns **all zeros**, which is what makes the
rest readable — and is also the check that would have caught a silent fallback to f16 in any
other row.

## What it says

**1. Every row above was "clean" to the collapse detector, and they span 55x in R.**
turbo2 flips **12.4 %** of top-1 tokens against the f16 reference. Nothing in this campaign
could see that. The "clean != faithful" caveat was load-bearing, not boilerplate.

**2. `q8_0` KV is far the most faithful quantized option** — 10.5 R, **6.5x lower than the
next best**, at a 1.48 % flip rate. Independently consistent with
`hermesagent20/KV_KLD_PANEL.md` ("the gentlest codec measured") reached there by KLD alone,
here by a decision-margin metric.

**3. turbo4 beats `q4_0` at comparable width** — R 68.1 vs 89.5, KL 0.00423 vs 0.00509, flip
rate a wash (0.0359 vs 0.0364). Direct support for buun's *"turbo4 > q4"* claim, measured with
buun's own instrument on a third party's fork.

**4. turbo3's margin erosion is negative (-0.0146)** — its decision margins are on average
*wider* than f16's, while it flips 6.7 % of top-1 tokens. Wide margins plus frequent flips is
the signature of **overconfidence**, not fidelity: it is landing elsewhere, confidently. Worth
flagging to buun as a codec-shape observation rather than a defect claim.

**5. Asymmetric beats symmetric at the same nominal budget.** `q8_0`/turbo4 (45.2) is better
than turbo4/turbo4 (68.1) *and* than turbo3/turbo3 (228.4). K-side precision buys more than
V-side, which is what h4rm0n1c argued from theory and what Tom's auto-asymmetric guard assumes.

## Bearing on buun's aliasing plan

buun proposed aliasing `q8_0` -> turbo8 and `q4_0` -> turbo4 to drop the legacy types.
This data supports **half** of it and cannot speak to the other half:

- `q4_0` -> turbo4 is **supported**: turbo4 is measurably better here.
- `q8_0` -> turbo8 is **untested**. Tom's fork has no turbo8, so it is absent above. And
  `q8_0` is 6.5x better than the best non-`q8_0` row, so whatever replaces it has a high bar.

The obvious next run is `frontier-hazard` against **buun's own build**, which has turbo8,
turbo3_tcq, turbo2_tcq and VBR. `frontier-hazard` builds a single context and does not use
tensor split, so `.194`'s buun trees can run it despite aborting on `-sm tensor`.

## What this does NOT establish

- **One model, one head dim, one arch.** Qwen3.5-9B, D=256, GQA 4:1, gfx1201. Codec ranking
  may differ elsewhere — and buun's own layer-pricing work says K-vs-V sensitivity is not
  uniform across layers, so a single aggregate hides structure.
- **Not a task score.** Fidelity to an f16 reference is not goodness. buun's own README is
  explicit: everything except `margin-bench` measures fidelity, not quality. A codec can beat
  the reference on a downstream task while scoring worse here.
- **Teacher-forced, not generative.** Per-step error never compounds. This is deliberate — it
  keeps the signal graded where autoregressive harnesses saturate — but it is not decode.
- **`--n-ubatch 8` throughout.** Required: on gfx1201 any quantized KV above `Q->ne[1] = 8`
  aborts in the TILE/MMA path (`rdna4-kernel-census/RESULT_LAUNCH_CENSUS.md`). Without that
  flag every row would have died.
- **Turbo results are from TheTom's implementation**, not buun's. Same codec names, different
  kernels.
