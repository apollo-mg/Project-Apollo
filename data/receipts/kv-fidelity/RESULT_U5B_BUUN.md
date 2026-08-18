# turbo8 vs `q8_0`, turbo4 vs `q4_0` — buun's aliasing plan, measured on buun's own build

**2026-08-18**, `.194`, quad Tesla P100 (sm_60), 150 W cap. buun `02f8581`
(`buun_tree_current`), `Qwen3.8-27B-Q6_K`, **D=256, GQA 6:1**. Teacher-forced against
f16/f16 with `llama-frontier-hazard` (buun's own tool, from `buun-quality-bench`).
16 wikitext prompts, `--n-prefix 128 --n-score 128`, `TURBO_AUTO_ASYMMETRIC=0`.
Raw `~/u5b.log` on `.194`, script `u5b_buun.sh`.

Answers Mark's question — *"Did you run turbo8 too? He claims it's > Q8."* `U5`
could not: **turbo8 does not exist in TheTom's fork.** This tree is the only one on the
fleet carrying turbo8, turbo3_tcq and vbr.

## The panel

| K/V | bits/value | flip_rate | mean_KL | mean_R | mean_L | frac_L≥1 |
|---|---:|---:|---:|---:|---:|---:|
| f16/f16 | 16 | 0.0000 | 0.00000 | 0.0000 | 0.0000 | 0.0000 |
| **`q8_0`/`q8_0`** | **8.5** | 0.0005 | 0.00001 | **0.0868** | −0.0882 | 0.0005 |
| **turbo8/turbo8** | **8.125** | 0.0030 | 0.00001 | **0.1507** | −0.0870 | 0.0030 |
| `q8_0`/turbo4 | 8.5 / 4.125 | 0.0167 | 0.00147 | 19.5817 | −0.4826 | 0.0153 |
| turbo8/turbo4 | 8.125 / 4.125 | 0.0153 | 0.00147 | 19.3743 | −0.5751 | 0.0143 |
| **`q4_0`/`q4_0`** | **4.5** | 0.0207 | 0.00205 | **22.1037** | −1.1863 | 0.0202 |
| **turbo4/turbo4** | **4.125** | 0.0266 | 0.00252 | **32.1966** | −0.9315 | 0.0251 |
| turbo3_tcq/turbo3_tcq | **3.25** | 0.0399 | 0.00567 | 63.2286 | −1.4500 | 0.0379 |
| turbo3/turbo3 | **3.5** | 0.0458 | 0.00889 | 125.2895 | **+2.3165** | 0.0423 |
| turbo2/turbo2 | 2.5 | 0.0866 | 0.03213 | 362.5289 | −5.7431 | 0.0733 |
| vbr/vbr | — | — | — | **not testable** | — | — |

Bits/value are from source, not inference: `block_turbo8_0` is 130 B per `QK_TURBO8`=128
(**8.125**), `block_q8_0` is 34 B per 32 (**8.5**), `block_turbo4_0` is 66 B per 128
(**4.125**), `block_q4_0` is 18 B per 32 (**4.5**). So **every turbo type here is the
*cheaper* side of its comparison** — turbo8 by 4.4 %, turbo4 by 8.3 %.

## What this does and does not say about the aliasing plan

buun's stated intent is to drop the legacy types and alias them: *"turbo4 > q4 and
turbo8 > q8 / why do I even offer them / they should just be aliases."*

**Neither half reproduces here as a fidelity win.**

- **turbo8 measures worse than `q8_0` symmetric** — 1.7× the decision danger, 6× the flip
  rate. **But this is underpowered and should not be quoted as a result.** `mean_KL` reads
  identical (0.00001) and is *at the printed resolution floor* (`%.5f`). Worse, the tool's
  means divide by `n_done` — the **prompt** count — so n=16, not 2048 tokens. `flip_rate`
  and `frac_L≥1` are equal in both rows, i.e. **the same events**: 1 vs 6. p ≈ 0.12.
- **turbo4 measures worse than `q4_0`** — R 32.20 vs 22.10, and here flip (0.0266 vs
  0.0207) and KL (0.00252 vs 0.00205) move together, so it is better supported than the
  8-bit row.

**The turbo4 result reverses `U5`.** On TheTom's fork (gfx1201, Qwen3.5-9B-Q8_0) turbo4
scored R 68.1 against `q4_0`'s 89.5 — turbo4 clearly ahead. Here it is clearly behind.
Different fork, different architecture, different model, so this is **not a contradiction of
a single measurement** — it means *"turbo4 > q4"* is **not architecture-independent**, and
`U5` should never have been read as general support for the aliasing plan. That was my
error, made in the prior session and corrected here.

## The finding that is actually well-supported

**turbo3_tcq is roughly 2× better than turbo3 while also being cheaper** — R **63.23** vs
**125.29**, flip 0.0399 vs 0.0458, KL 0.00567 vs 0.00889, at **3.25 bpv vs 3.5**
(`block_turbo3_tcq` 52 B/128 vs `block_turbo3_0` 14 B/32). Fewer bits *and* half the decision
danger, so unlike every other pair in this panel there is **no bit-budget confound pointing
the other way**. Of everything here this is the cleanest signal, and it is the one buun is
least likely to have priced, since TCQ is the newer codec.

It also carries further than it looks: **`"vbr"` is a CLI alias for `GGML_TYPE_TURBO3_TCQ`**
(`common/arg.cpp:342`; there is no `GGML_TYPE_VBR`). So this row is the static base of
buun's *default* KV type — the number under everything his build ships by default.

## A symmetry pattern, and the test it triggered

Mark's read: *"Turbo codecs, iirc, always perform badly when symmetric due to the rotation
math."* h4rm0n1c called symmetric turboquant "bunkum" in the same Discord thread.

The panel is consistent with it, in a way pure bit-budget is not:

| comparison | turbo | non-turbo | winner |
|---|---:|---:|---|
| **symmetric** turbo8/turbo8 vs `q8_0`/`q8_0` | 0.1507 | 0.0868 | **non-turbo** |
| **mixed** turbo8/turbo4 vs `q8_0`/turbo4 | 19.3743 | 19.5817 | **turbo** |

turbo8 loses as a symmetric pair and **wins as the K partner of a *different* type**, at
4.4 % fewer bits. Mechanistically available: buun's own header calls turbo8 *"no QJL"* with
*"FWHT outlier suppression"* — **no random projection means the Walsh-Hadamard rotation is
deterministic**, so a symmetric pair gives K and V an *identical* transform and lets their
errors correlate. Asymmetric pairs break that.

**Not established here.** The mixed comparison is dominated by turbo4's V error (R ≈ 19.5
against K's ≈ 0.1), so a 1.7× K difference can only move it ~0.4 % — smaller than the
1.07 % observed, in the wrong direction. `U5c` tests it properly at matched bit budget.

## Method notes

- **No silent K upgrade fired.** buun's tree contains a `q8_0` fallback for turbo types on
  CPU-bound layers (`llama-kv-cache.cpp:894-914`) and does **not** read
  `TURBO_AUTO_ASYMMETRIC` at all — so pinning it to 0 guarantees nothing. Proven empirically
  instead: turbo4/turbo4 (32.20) ≠ `q8_0`/turbo4 (19.58). Had K been upgraded, those two
  rows would be the same measurement. `-ngl 99` and head_dim 256 ≤ 512 keep both fallbacks
  dormant.
- **VBR is not testable through this tool.** `error: unsupported KV cache type 'vbr'` — the
  arg parser's string→type map lacks it; the gate line reads
  `dynamic=0 policy=0 is_turbo=0 -> wanted=0`. This is a **tool limitation, not evidence of
  the non-engagement** the prior `kv_bpv: 16.0` result suggested. `U7` stays open and needs
  `VBR_LAYER_SCHEDULE` or an equivalent entry point.
- **`mean_L` is unstable at the tail.** turbo2 reads −5.74 and turbo3 **+2.32**; these are
  means of a ratio whose denominator can approach zero. `frac_L≥1` is the robust form and is
  monotone across the ladder. Do not quote `mean_L`.
- The script discarded `cvar95_R` and the per-position `DEPTH` bands that
  `frontier-hazard` also emits. `U5c` keeps full per-arm output.

## Comparability

**`U5` and `U5b` are not comparable to each other.** Different fork (TheTom vs buun),
architecture (gfx1201 vs sm_60), model (Qwen3.5-9B-Q8_0 vs Qwen3.8-27B-Q6_K) and GQA ratio
(4:1 vs 6:1). Compare only *within* each panel.
