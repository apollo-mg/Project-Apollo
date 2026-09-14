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

---

## Amendment 1 — 2026-09-14 13:55, before any download: the run moves to `.194`, and a BRIDGE gate is added

**Node changed from `.73` to `.194`.** Checked before committing to either:

- **`.73` is serving Mark's daily driver** (`llama-server`, both cards, 14,048 + 12,912 MiB) and is
  disk-starved on every mount — `/` 20 GB free, `/mnt/models` 9.9 GB, `/mnt/optane` 9.3 GB. **No single
  mount holds even one of the two files plus a reference.** It has since returned to S3 sleep.
- **`.194` is idle with 61 GB free** on one filesystem, and already holds `wiki.test.raw` and
  `UD-IQ4_XS`.
- **Neither node holds the Q8_0 reference or its base-logits file**, so that cost is identical either way
  and `.73` has no remaining advantage.

### The reference has to be regenerated, and that is not a free step

`exl3_kld_arm.py:67` requires a **base-logits file** (`--kl-divergence-base`), not the Q8_0 GGUF. Test 3
produced it on `.73` and it is gone. So this run: fetch **Qwen3.8-27B-Q8_0 @ `4ca72078`** (27.05 GiB,
hash-verified), regenerate the base on `.194` **with byte-identical flags** —
`-ngl 99 -sm layer -c 512 -b 512 -ub 8 --chunks 40 -fa on -ctk f16 -ctv f16` — then run the arms against it.

### BRIDGE — a new gate, and the run is VOID without it

Test 10's numbers were produced on `.73` with **two** P100s. Comparing new points measured on `.194`
against that curve assumes cross-node equivalence, which is **untested**. Test 10 tested cross-*build*
equivalence and found identical KLD to six decimals; this is the same instrument applied to a new variable.

- **`UD-IQ4_XS` is already on `.194` and is re-run first**, at no download cost.
- **It must reproduce test 10's `0.015727` within ±1%.** Outside that band, **the run is VOID** and reported
  as a cross-node discrepancy — the new arms are not compared to test 10's curve at all.
- Any nonzero delta inside the band is recorded in the receipt rather than rounded away.
- **All arms run on two GPUs** (`CUDA_VISIBLE_DEVICES=0,1`) to match `.73`'s device count, so the only
  remaining difference is the host.

### Disk plan, given 61 GB free

Sequential, with deletes between: Q8_0 (27) + base (~5) + Q3_K_XL (12.2) → run → delete Q3_K_XL →
Q4_K_XL (16.4) → run. **Peak usage leaves ~13 GB free.** Each file is hash-verified against unsloth's
published sha256 before it runs:

| file | published sha256 |
|---|---|
| `UD-Q3_K_XL` | `8c2a45ff85e7674ca185ec8eb6cdeab0e617ed9d8018caed0b64380eb2a67a5e` |
| `UD-Q4_K_XL` | `3f227079003add2511437e5b1e94812e363385225bf6a9b47b0054a72bc8b01e` |

**Not touched:** 145.2 GB of stale KLD artifacts from earlier campaigns sit on `.194`
(`puzzle_lab/w1/q8_base_logits.bin` 68.6 GB and seven `.kld`/`.dat` files). Per standing guidance these are
**moved, not deleted**, and that is a separate decision — this run fits without them.

**Predictions P-X1 through P-X4 are unchanged.**
