# At a fixed KV budget, spend the bits on V — and the symmetry hypothesis is falsified

**2026-08-18**, `.194`, quad Tesla P100 (sm_60), 150 W / 405 MHz idle-clock state.
buun `02f8581`, `Qwen3.8-27B-Q6_K`, D=256, GQA 6:1. `llama-frontier-hazard`, **128 wikitext
prompts** (8× U5b, exact superset), `--n-prefix 128 --n-score 128`, teacher-forced against
f16/f16. Raw `u5c.log` / `u5d.log`, scripts `u5c_power.sh` / `u5d_swap.sh`, per-arm output in
`~/u5c_raw/` and `~/u5d_raw/` on `.194`.

Pre-registration and its amendment: `U5C_PREREGISTRATION.md` (`375761b`, `bb2b6e1`,
`0c8aa6a`, `45fdf8d`) — **all committed before the arms they score.**

**Read with `SCOPE_CORRECTION_136_TOKENS.md`.** Every number here is a **136-token context**
measurement. It says nothing about depth.

## The question

Mark: *"Turbo codecs, iirc, always perform badly when symmetric due to the rotation math."*
h4rm0n1c called symmetric turboquant "bunkum". Mechanism: turbo8 is *"no QJL"* with
*"FWHT outlier suppression"* — a **deterministic** Walsh-Hadamard rotation, so a symmetric
pair gives K and V the identical transform and their errors can correlate.

Confound: every turbo type is also the *cheaper* side of its comparison, so "turbo lost" is
unidentifiable against plain bit budget. Both tiers below fix the budget and place the two
mixed arms at the bit midpoint of the two symmetric ones.

## 8-bit tier (U5c)

| arm | K | V | nominal bpv | flip | mean_R | cvar95_R |
|---|---|---|---:|---:|---:|---:|
| f16 control | f16 | f16 | 32.00 | 0.0000 | 0.0000 | 0.0000 |
| A | `q8_0` | `q8_0` | 17.00 | 0.0014 | 0.1654 | 3.3529 |
| B | `q8_0` | turbo8 | 16.625 | 0.0014 | 0.1820 | 3.6553 |
| **C** | **turbo8** | **`q8_0`** | 16.625 | 0.0014 | **0.1469** | **2.9358** |
| D | turbo8 | turbo8 | 16.25 | 0.0016 | 0.2062 | 4.1498 |

## 4-bit tier (U5c) — half of it does not exist

| arm | K | V | nominal bpv | flip | mean_R | cvar95_R |
|---|---|---|---:|---:|---:|---:|
| A | `q4_0` | `q4_0` | 9.00 | 0.0234 | 30.9471 | 616.8537 |
| B | `q4_0` | turbo4 | 8.625 | — | **ABORT** | — |
| C | turbo4 | `q4_0` | 8.625 | — | **ABORT** | — |
| D | turbo4 | turbo4 | 8.25 | 0.0265 | 37.6386 | 749.3771 |

`ggml/src/ggml-cuda/fattn.cu:2658` → `GGML_ABORT` under `BEST_FATTN_KERNEL_NONE`: **no FA
kernel exists on sm_60 for `q4_0` paired with a turbo type, in either order.** The
enumeration just above that line gives the supported mixed set — `K=TURBO2_0` with
`V ∈ {TURBO3_0, TURBO4_0, Q8_0, F16}`, `K=TURBO3_0` with `V=TURBO2_0`. **`q4_0` is not in the
turbo-mixing story at all.** Coverage gap, not a bug. **`P4` withdrawn, not scored.**

## Swap tier (U5d) — the clean test

Rebuilt on turbo2/turbo3, which is **better than the design that failed**: B and C are an
**exact swap of the same two codecs at identical total bits**, so the codec-quality term
cancels. The 8-bit tier could not do this (turbo8 vs `q8_0` differ in codec *and* width).

| arm | K | V | bpv | flip | mean_KL | mean_R | cvar95_R |
|---|---|---|---:|---:|---:|---:|---:|
| A | turbo3 | turbo3 | 7.0 | 0.0495 | 0.00993 | 159.61 | 3202.31 |
| B | turbo3 | turbo2 | 6.0 | 0.0817 | 0.02698 | 401.83 | 8007.13 |
| **C** | **turbo2** | **turbo3** | 6.0 | 0.0688 | 0.01924 | **274.60** | **5490.94** |
| D | turbo2 | turbo2 | 5.0 | 0.0958 | 0.03603 | 512.56 | 10215.42 |

## Findings

### 1. Bits belong on V, not K — and this reverses the community's stated direction

**C beats B by 31.7 % on the mean and 31.4 % on the tail**, at identical total bits, same two
codecs, merely exchanged. Flip rate and KL agree (0.0688 vs 0.0817; 0.01924 vs 0.02698), so
all four metrics point the same way.

The 8-bit tier says the same thing independently: **arm C beat every arm including the
all-`q8_0` baseline** (0.1469 vs 0.1654) — a different codec pair, same direction.

**`P5b` FALSIFIED at conf 0.60.** I registered h4rm0n1c's K > V direction — *"you can lose a
value and a key might point to something near enough, but if you lose the key, no value at
all gets found"* — explicitly **against** the transfer of our own 8-bit result, on the
grounds that ours was codec-confounded and his had a stated mechanism. The measurement was
right and I discounted it. `P5a` (transfer) is what held.

**The reconciliation, which is not a refutation.** h4rm0n1c's intuition comes from real
long-context use; this is **136 tokens**. Key-retrieval damage is exactly the failure that
should compound with history length, so the sign may well invert at depth. buun's refinement
cuts the same way: *"K > V is a generalization but not true on a layer-by-layer basis — a
middle-late layer on K is more expendable than an early layer on V."* **The depth ladder
decides which regime each of us is describing.**

### 2. The symmetry hypothesis is falsified — placement matters, symmetry does not

Applying the pre-registered rule to `X = (R_B + R_C)/2` against `M_geo = √(R_A·R_D)`:

| tier | metric | `M_geo` | `X` | verdict |
|---|---|---:|---:|---|
| swap | mean_R | 286.02 | 338.21 | **ANTI-SYM** |
| swap | cvar95_R | 5719.52 | 6749.03 | **ANTI-SYM** |

Mixed arms average **worse** than the interpolation, the opposite of a symmetry penalty.
Decomposed, B sits 40 % *above* the line and C 4 % *below* it — so the tier's spread is
**entirely a placement effect**, with no symmetry component at all.

The 8-bit tier nominally returned "strong" on both metrics (X = 0.1644 < R_A = 0.1654), but
**that verdict is unsound** — see finding 4 — and it decomposed the same way: B on the line
(1.4 %/2.0 %), C far below (20.5 %/21.3 %). **Only ever one mixed arm dips.** If
desymmetrization were the mechanism, both would.

**Conclusion: at fixed budget, what matters is *where* the bits go, not whether K and V
share a codec.** The deterministic-FWHT correlation story is not needed to explain anything
measured here.

### 3. The tail carries no ranking information the mean does not

`cvar95_R / mean_R` across all ten scored arms in both tiers:

| span | ratio range | stdev |
|---|---|---|
| mean_R 0.1469 → 512.56 (**3,489×**) | **19.91 – 20.27** | 0.132 |

Mark's Gamers-Nexus critique — *"focus on the stuff that bothers you, not the averages, like
1 % lows and frame-times"* — was methodologically right and prompted promoting `cvar95_R` to
co-primary mid-run (`bb2b6e1`, before arms B/C/D existed). **The data answers it with a
null**: every codec's error distribution has the same *shape*, so the expensive tail
statistic reproduces the cheap mean's ranking exactly. Useful, because it licenses using
`mean_R` alone — **at this depth**. Whether shape-invariance survives at real context length
is untested and is the more interesting form of the question.

### 4. The matched-budget premise is measured-false — U5c's verdict is unsound

Per-arm `KV buffer size`, the quantized context (**second** occurrence in each log; the
first is the f16 reference):

| arm | measured MiB | predicted from block layout |
|---|---:|---:|
| f16/f16 | 4.00 | 4.000 ✓ |
| `q8_0`/`q8_0` | **2.12** | 2.125 ✓ |
| `q4_0`/`q4_0` | **1.12** | 1.125 ✓ |
| turbo8/turbo8 | **2.16** | 2.031 ✗ |
| turbo4/turbo4 | **1.16** | 1.031 ✗ |
| `q8_0`/turbo8 | **2.20** | 2.078 ✗ |
| turbo8/`q8_0` | **2.20** | 2.078 ✗ |

**Stock types match source arithmetic exactly; every turbo type allocates ~+0.5 bpv more
than its block layout implies** (turbo8 behaves as ≈8.64 bpv, turbo4 as ≈4.64).

This **inverts the 8-bit ordering the design rests on**. By measured allocation it is
`q8_0`/`q8_0` 2.12 (cheapest) < turbo8/turbo8 2.16 < mixed 2.20 (**most expensive**). The
mixed arms are not the midpoint, so `M_geo` interpolated between endpoints that are not the
endpoints, and **arm C's 8-bit win partly reads as "spent more, got more."**

Two things this does **not** touch:
- **U5d's swap comparison is unaffected.** B and C are the same two codecs exchanged, so
  whatever the true per-type overhead is, it is *identical* in both arms. The 31.7 % gap
  stands on its own.
- **The ~20× ratio is unaffected** — it is a within-arm quantity.

**Caveat that cuts both ways:** at 136 tokens the cache is 1–4 MiB, where fixed padding and
alignment can dominate. A constant per-tensor overhead would vanish at 32k, in which case the
block arithmetic is right for real deployments and only this measurement is misleading.
**Unresolved.** Distinguishing them needs a load-only size sweep at large `n_ctx` — cheap
(~1 min/config, no scoring), not yet run.

## Prediction scorecard

| # | prediction | conf | outcome |
|---|---|---|---|
| P1 | 8-bit tier shows a symmetry dip | 0.50 | **passes rule, but UNSOUND** (finding 4) |
| P2 | 4-bit tier shows a symmetry dip | 0.60 | **UNTESTABLE** — both mixed arms abort |
| P3 | f16 control exact null | 0.97 | **correct** |
| P4 | 4-bit repeats the turbo-on-K asymmetry | 0.70 | **WITHDRAWN** — kernel coverage gap |
| P5b | K > V (bits belong on K) | 0.60 | **FALSIFIED** — V wins by 32 % |

**1 correct, 1 falsified, 1 unsound, 2 unrunnable.** The one that scored cleanly was the
0.97 "nothing happens" control, which continues the pattern `AFM-17` records: confident calls
about *mechanism* keep losing to measurement.

## Method notes

- **No `q8_0` fallback fired** in any arm (`llama-kv-cache.cpp:894-914` warning absent from
  all logs). Independently corroborated: turbo4/turbo4 (37.64) ≠ `q8_0`/turbo4, so K was not
  silently upgraded. buun's tree does **not** read `TURBO_AUTO_ASYMMETRIC`, so pinning it
  guarantees nothing on its own.
- **`mean_L` remains excluded from every verdict** — mean of a ratio with a near-zero
  denominator. `frac_L≥1` is the robust form and is monotone throughout.
- **n=16 was not a stable estimator.** `q8_0`/`q8_0` mean_R moved 0.0868 → 0.1654 (~2×) and
  `q4_0`/`q4_0` 22.10 → 30.95 (~40 %) going from U5b's 16 prompts to 128. **U5b's rankings
  should not be quoted**; this file supersedes them where they overlap.
