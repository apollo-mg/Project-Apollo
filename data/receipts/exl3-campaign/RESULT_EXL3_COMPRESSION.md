# Result — on the dense 27B, EXL3 is 1.3–1.5× closer to the reference than GGUF at matched VRAM: a steady 5–10% VRAM saving, not a low-end breakthrough

**Run 2026-09-13, 11:11–15:18, `.73`** (2× P100, sm_60), EXL3 campaign test 10, ledger O6. Pre-registered in
`PREREG_EXL3_COMPRESSION.md` (`5de9ba0`, Amendment 1 `583ee1f`). Driver `exl3_kld_arm.py`, scorer
`tools/score_exl3_compression.py`, orchestrator `orchestrate_compression.sh` — all committed before any arm ran.
Reference: Qwen3.8-27B Q8_0 @ `4ca72078`, wikitext-2 test, 40 chunks × 512, `-ub 8`, f16 KV — test 3's reference,
so all thirteen points share it. **All nine new arms exited 0 with no decode failures.** EXL3 snapshots are
turboderp's, pinned and hash-verified; the GGUFs are size-checked only, as declared.

## The curve

| arm | file | peak VRAM MiB | mean KLD | same top |
|---|---|---|---|---|
| E25 | EXL3 2.50bpw | 9,116 | 0.0934 | 87.3% |
| G2x | AD-IQ2_XS | 9,272 | 0.1745 | 81.7% |
| G2u | UD-Q2_K_XL | 9,404 | 0.0842 | 87.3% |
| E30 | EXL3 3.00bpw | 10,568 | **0.0462** | 90.7% |
| G3xx | AD-IQ3_XXS | 11,358 | 0.0737 | 88.5% |
| G3u | UD-IQ3_XXS | 11,532 | 0.0476 | 90.9% |
| E35 | EXL3 3.50bpw | 12,016 | **0.0250** | 93.3% |
| G3m | i1-IQ3_M | 12,240 | 0.0613 — *off the curve: UD-IQ3_XXS is smaller and closer* | 89.8% |
| E | EXL3 4.00bpw | 13,468 | **0.0120** | 95.4% |
| G4 | UD-IQ4_XS | 13,500 | 0.0157 | 94.2% |
| G5 | UD-Q4_K_M | 15,448 | 0.0078 | 96.2% |
| E5 | EXL3 5.00bpw | 16,372 | **0.0040** | 97.2% |
| G6 | Q6_K | 21,276 | 0.0028 | 97.7% |

## Findings

**1. EXL3 sits below the controlled GGUF curve everywhere it can be compared** (P-C1, confirmed on both curves).
Against unsloth's UD recipe at matched VRAM — the curve Amendment 1 named as the one to quote:

| EXL3 point | EXL3 KLD | UD curve at that VRAM | ratio |
|---|---|---|---|
| 3.00bpw @ 10,568 MiB | 0.0462 | 0.0617 | **1.34×** |
| 3.50bpw @ 12,016 MiB | 0.0250 | 0.0363 | **1.45×** |
| 4.00bpw @ 13,468 MiB | 0.0120 | 0.0160 | **1.33×** |

**2. In VRAM, that is a GGUF needing 5–10% more memory for the same fidelity:** +1,019 MiB (9.6%) at 3.00bpw,
+662 (5.5%) at 3.50bpw, +788 (5.9%) at 4.00bpw — and +2,854 MiB (17.4%) at 5.00bpw, against all packagers. **Real,
steady, and far smaller than turboderp's Flash-Next chart**, which puts EXL3 3.05bpw level with UD-IQ4_XS.

**3. No trend with size.** P-C2 predicted the advantage would widen as size falls. The log-gap is flat: 0.289 at
10.6 GB vs 0.288 at 13.5 GB on the UD curve, 0.522 vs 0.509 on all packagers. Both score CONFIRMED by the rule —
the smaller-size gap is larger — by margins of 0.001 and 0.013. **In substance the advantage is constant.** The
premise that compression at the low end is where EXL3 pulls away is not supported on this model.

**4. At the bottom, the packager matters as much as the format.** EXL3 2.50bpw (9,116 MiB, 0.0934) and UD-Q2_K_XL
(9,404 MiB, 0.0842) are about even. Weaker recipes at nearly the same sizes are far worse: AD-IQ2_XS 0.1745 at
9,272 MiB; AD-IQ3_XXS 0.0737 at 11,358 MiB against UD-IQ3_XXS 0.0476 at 11,532; and i1-IQ3_M at 12,240 MiB is beaten
outright by the smaller UD-IQ3_XXS. **Choosing the GGUF packager is worth as much as choosing the format.**

**5. The builds are interchangeable** (P-C0). BRIDGE ran E30's snapshot on **`da458765d`** and reproduced E30 on
**`9ae8f0f40`** to six decimals — mean KLD 0.046152 on both, peak 10,568 MiB on both. Every cross-build comparison
in this campaign stands.

## Mark's crossover — P-C5 confirms as coded, but its premise does not hold here

EXL3 3.00bpw (0.0462) is **1.8× closer to the reference than UD-Q2_K_XL** (0.0842) — **at 10,568 vs 9,404 MiB, 12%
more VRAM.** "3 bpw in the same space as UD-Q2 XL" does not hold on the 27B; the same-space pair (E25 vs G2u) is
about even. **P-C5 was defined only in the scorer** (lower KLD wins, no VRAM condition) and in Amendment 1's commit
message, not in the prereg text; recorded as a deviation.

Why a published chart can say otherwise, as hypotheses: its x-axis is bits per weight excluding embeddings and the
head, where ours is peak VRAM; unsloth's recipe differs per model; and Flash-Next's MoE experts may favour trellis
quantization more than dense layers do. A same-method Flash-Next KLD would separate these, and needs a reference
this fleet cannot hold.

## Predictions

| id | prediction | result |
|---|---|---|
| P-C0 | the bridge reproduces E30 across builds | **CONFIRMED** — identical to six decimals |
| P-C1 | EXL3 below the GGUF curve at every EXL3 point | **CONFIRMED** on both curves; E25 excluded as below every GGUF point, as Amendment 1 declared |
| P-C2 | the advantage widens as size falls | **CONFIRMED by the rule, flat in substance** (0.001 / 0.013 margins) |
| P-C3 | E25 beats the GGUF nearest its size (G2x) | **CONFIRMED** — against the weak recipe; UD-Q2_K_XL at a similar size is about even |
| P-C4 | E30 closer to the reference than G3xx | **CONFIRMED** — 0.0462 vs 0.0737. In VRAM that GGUF is **790 MiB** larger, not the ~1.8 GB the prereg's disk sizes implied. Against UD-IQ3_XXS, EXL3 3.00bpw matches fidelity at **964 MiB less** |
| P-C5 | EXL3 3.00bpw beats UD-Q2_K_XL | **CONFIRMED as coded**; 12% more VRAM, see above |

## Numbers not to quote

- **E25's exchange rate (+269 MiB)** is interpolated across the near-vertical G2x → G2u step (132 MiB, KLD 0.1745 →
  0.0842). In VRAM G2x is the smaller of the two, the reverse of their disk sizes, so the lower envelope keeps both.
- **The all-packagers interpolation at 10.6 GB (0.0778)** is pulled up by AD-IQ3_XXS sitting 174 MiB below the much
  better UD-IQ3_XXS; the envelope rule keeps a weak point whenever it is slightly smaller. Quote the UD curve.

## What it means for Mark's bar, and a problem with test 11

**Mark asked for "a substantial difference in usable quality".** This test measures distribution, and the
distribution advantage is real but modest: 1.3–1.5× lower KLD, worth 5–10% of VRAM. Against it on Pascal: EXL3
decodes at 0.646× the daily driver as served, and gets less from MTP.

**Test 11's arm-selection rule is ambiguous, and the ambiguity was found only now, with the data in hand.** It asks
for the EXL3 point with the largest advantage over "the GGUF lower envelope" without naming the curve:

- **all packagers** selects EXL3 3.00bpw (log-gap 0.522) against the nearest envelope point above it, **AD-IQ3_XXS**
  — a weak recipe;
- **UD only** selects EXL3 3.50bpw (log-gap 0.373) against **UD-IQ4_XS, 1.5 GB larger and closer to the reference**
  — a pair EXL3 is expected to lose.

Neither is the comparison the rule was written to produce. Any resolution now is post-data, so it goes to Mark with
the options before test 11 launches.

## Deviations

- **P-C5's definition lives in the scorer**, not the prereg text.
- **P-C4's "~1.8 GB larger" came from disk sizes**; the scored comparison is in VRAM, where the gap is 790 MiB.
- **The GGUFs are size-checked, not hash-verified** — declared in the prereg.
- **Test 3's rows predate the `bin` field**; per test 3's receipt they ran on `9ae8f0f40`, as the BRIDGE confirms.

Working notes written mid-run, before the last three arms: `NOTES_TEST10_PARTIAL.md`.

---

### Provenance note added 16:25 — G3u's file is unsloth revision `f9758630`, not today's published cut

Staging test 11 hash-checked this file and it did **not** match what unsloth publishes now
(10,934,860,704 B, `c0b7c303…`). Walking the repo's history: **our copy is revision `f9758630`, 2026-08-19,
11,913,559,104 B, `0a6129dc…`** — and unsloth re-cut UD-IQ3_XXS the same day, so every later revision carries
the smaller file. Ours is genuine unsloth UD-IQ3_XXS, one cut earlier.

**Read the G3u row, and the "UD curve" built through it, as revision `f9758630`.** The measurement stands; the
label needed the revision. The prereg declared the GGUFs size-checked only, which is exactly the gap this
closes — a size check would not have caught a re-cut of a *different* size either, but it never compared
against anything published. Test 11 pins the revision in its own gate.

### Provenance sweep, 16:25 — the rest of the UD curve is hash-verified

Prompted by the re-cut above, every unsloth file in this curve was hashed and checked against the repo's
last 30 revisions (`usable/provenance_sweep.log`):

| arm | file | provenance |
|---|---|---|
| G2u | UD-Q2_K_XL | **matches unsloth's current publication** |
| G3u | UD-IQ3_XXS | revision **`f9758630`** (2026-08-19; re-cut the same day) |
| G4 | UD-IQ4_XS | **matches current** |
| G5 | UD-Q4_K_M | **matches current** |

**So the UD curve — the one this receipt quotes — is now hash-verified**, three files against today's
publication and one against a named revision, rather than size-checked as the prereg declared. The check was
run after the measurements, on the same bytes, so it changes provenance and not a number.

**Still unverified:** the AD-IQ2_XS, AD-IQ3_XXS and i1-IQ3_M files (other packagers, no published hashes
recorded here) and the Q6_K reference. They sit on the all-packagers curve, which this receipt already
declines to quote.

---

### CORRECTION added 2026-09-14 — the 1.45× at 3.50bpw was an interpolation artifact

Full result: `RESULT_EXL3_UD3_XL.md`. Prereg `PREREG_EXL3_UD3_XL.md`, committed before the files were fetched.

**This receipt measured no GGUF within 2 GB of EXL3 3.50bpw.** Its nearest points were UD-IQ3_XXS
(11,532 MiB) and UD-IQ4_XS (13,500 MiB), and the 1.45× came from interpolating between them. unsloth
publishes a **`UD-*_XL` family that this receipt never fetched** — including **UD-Q3_K_XL, which lands
inside that gap**:

| | VRAM | mean KLD |
|---|---|---|
| EXL3 3.50bpw (E35) | 12,016 MiB | 0.024979 ± 0.000723 |
| **UD-Q3_K_XL** (measured 2026-09-14) | 12,446 MiB | **0.024951 ± 0.000804** |

**Identical fidelity, 0.11% apart. EXL3's advantage at that point is not 1.45× — it is 430 MiB (3.6%) of
VRAM at the same KLD.**

**UD-Q4_K_XL** (16,494 MiB, 0.005607) likewise replaces an interpolation across the 5.8 GB gap between
UD-Q4_K_M and Q6_K. It leaves EXL3 5.00bpw ahead **1.40× at 122 MiB (0.7%) difference** — the cleanest
matched-VRAM pair in the campaign, and stronger evidence than the number it replaces.

**Corrected exchange rates** (all other points unchanged):

| EXL3 point | as published above | corrected |
|---|---|---|
| 3.50bpw | +662 MiB (+5.5%) | **+428 MiB (+3.6%)** |
| 5.00bpw | +2,854 MiB (+17.4%) | **+2,422 MiB (+14.8%)** |

**Read this receipt's Finding 1 and 2 as "1.33–1.35×, worth 3.6–9.5% of VRAM, 1.40× and 14.8% at 5 bpw."**
Not 1.33–1.45× / 5–10% / 17.4%.

**The measurements in this receipt are unchanged and were reproduced exactly** — UD-IQ4_XS re-ran on a
different node, a different build and a regenerated reference and returned 0.015727 at 13,500 MiB, identical
to six decimals. **What was wrong was not a number but a missing point**, and the interpolation that stood in
for it.
