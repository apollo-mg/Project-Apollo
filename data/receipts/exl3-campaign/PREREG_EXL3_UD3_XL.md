# Prereg — the UD3 `*_XL` family was never measured, and it sits exactly where test 10 claims EXL3's biggest win

**Written 2026-09-14 ~13:40, before either file is downloaded.** Follow-up to test 10
(`RESULT_EXL3_COMPRESSION.md`). Mark's go.

## Why this exists

Test 10's headline is **"EXL3 is 1.33–1.45× closer to the reference than the UD GGUF curve at matched
VRAM."** The 1.45× — the largest figure, and the one most likely to be quoted — is EXL3 3.50bpw at
**12,016 MiB against an *interpolated* envelope of 0.0363**, with the nearest measured GGUF points at
11,532 MiB (UD-IQ3_XXS, 0.0476) and 13,500 MiB (UD-IQ4_XS, 0.0157). **There is no measured GGUF point
within 1.5 GB of it.**

unsloth publishes a **`UD-*_XL` family** — `Q3_K_XL` (12.24 GiB), `Q4_K_XL` (16.35), `Q5_K_XL`, `Q6_K_XL` —
and **test 10 measured none of it.** Its README calls these Dynamic 3.0 and claims *">10% top-1% better
accuracy at the same size compared to every other provider."* Verified 2026-09-14: the repo has been
unchanged since 2026-08-20, so this is the current generation and our other three UD arms already match it.

**`UD-Q3_K_XL` at 12.24 GiB lands in the unmeasured gap, next to the 1.45× claim.**

## This test can only hurt our published claim

**Adding points to a lower envelope can only push it down, never up.** So EXL3's advantage at 3.50bpw can
only **shrink or stay the same** — it cannot improve. There is no outcome where this test flatters the
campaign's headline. That is precisely why it is worth running before the number travels further.

## Setup — identical to test 10, nothing new

- **Node `.73`**, 2× P100, wake proxy paused, one model at a time.
- **Reference: the same one all thirteen test-10 points share** — Qwen3.8-27B **Q8_0 @ `4ca72078`**,
  wikitext-2 test, 40 chunks × 512, `-ub 8`, f16 KV.
- **Driver** `exl3_kld_arm.py`, **scorer** `tools/score_exl3_compression.py` — both committed before test 10
  and unchanged.
- **Arms:** `UD-Q3_K_XL`, `UD-Q4_K_XL`.
- **Provenance upgraded over test 10:** both files are **hash-verified against unsloth's published sha256**
  before they run. Test 10 declared its GGUFs size-checked only; that gap is closed here.
- **VRAM is peak VRAM**, as in test 10 — not disk size, not nominal bpw.

## Predictions

| id | prediction | confidence |
|---|---|---|
| P-X1 | **UD-Q3_K_XL lands at or below test 10's interpolated UD envelope at its own VRAM** (≤ 0.0246 at ~12,700 MiB) — i.e. it improves the envelope rather than sitting above it | 70% |
| P-X2 | **Redrawing the envelope through it cuts EXL3 3.50bpw's advantage below 1.30×** (from 1.45×) | 55% |
| P-X3 | **EXL3 3.50bpw still leads the redrawn envelope** (ratio > 1.0) | 85% |
| P-X4 | **UD-Q4_K_XL improves the envelope above 15 GB** relative to UD-Q4_K_M (0.0078 at 15,448 MiB) | 65% |

**Arithmetic behind P-X2, so the band is not drawn after the fact.** With UD-Q3_K_XL at VRAM *V* and KLD *X*,
the envelope at 12,016 MiB is the log-linear interpolation between UD-IQ3_XXS (11,532 / 0.0476) and
(*V*, *X*). For the ratio against EXL3's 0.0250 to fall below 1.30×, Q3_K_XL needs roughly **≤ 0.019 at
~12,700 MiB**. A point landing exactly on the current line changes nothing — the ratio stays 1.45×.

## Declared in advance

- **P-X1 and P-X2 are the ones that can embarrass the campaign**, and P-X3 is the one that would rescue it.
  If P-X3 falsifies — EXL3 3.50bpw loses outright to a redrawn UD3 envelope — **test 10's headline is
  withdrawn and rewritten**, not amended.
- **Two arms only.** `Q5_K_XL` and `Q6_K_XL` sit above the region in dispute and are not run. If P-X4
  confirms, extending upward becomes worth doing separately.
- **This does not revisit EXL3's own points.** They are measured, hash-verified and unchanged; only the
  GGUF envelope moves.
- **G3u stays as declared.** UD-IQ3_XXS remains revision `f9758630`, hours older than the 08-19 re-cut, as
  `RESULT_EXL3_COMPRESSION.md` already records. This test does not fix that and does not pretend to.
- **A null is publishable.** If UD-Q3_K_XL lands *above* the interpolation, test 10's 1.45× is confirmed
  against a real neighbouring point rather than an assumption — a strictly stronger claim than it has today.

**Scorer:** `tools/score_exl3_compression.py`, unchanged, run over the extended `results.jsonl`.
