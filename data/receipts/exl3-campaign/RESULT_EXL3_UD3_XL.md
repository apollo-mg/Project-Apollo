# Result — the 1.45× was an interpolation artifact; the 5 bpw advantage survives and is now measured directly

**Run 2026-09-14, 14:00–15:08, `.194`** (2 of 4 P100s, sm_60). Pre-registered in `PREREG_EXL3_UD3_XL.md`
(`075e488`, Amendment 1 `e06ff34`), both committed **before either file was downloaded**. Driver
`exl3_kld_arm.py` and scorer `tools/score_exl3_compression.py` are test 10's, unmodified except for a
registry entry (see Defects). Reference: Qwen3.8-27B **Q8_0 @ `4ca72078`**, hash-verified, base logits
regenerated on `.194` with byte-identical flags. Both new files **hash-verified against unsloth's published
sha256** — an upgrade over test 10, which declared its GGUFs size-checked only.

## The BRIDGE passed exactly, which is what makes the rest usable

| | test 10, on `.73` | this run, on `.194` |
|---|---|---|
| UD-IQ4_XS mean KLD | 0.015727 | **0.015727** |
| peak VRAM | 13,500 MiB | **13,500 MiB** |

**Identical to six decimals and to the MiB**, across a different host, a different build of the fork
(`c7f114d34` vs `buun-sm60-qual`), and a reference base regenerated from scratch 25 days later. Test 10 had
demonstrated cross-*build* equivalence; this extends it to cross-*node* and shows **the reference file itself
is reproducible** — which also means the campaign's old `.kld` bases are caches, not irreplaceable artifacts.

## The two new points

| arm | file | peak VRAM | mean KLD | same top |
|---|---|---|---|---|
| **G3XL** | UD-Q3_K_XL | **12,446 MiB** | **0.024951 ± 0.000804** | 93.225% |
| **G4XL** | UD-Q4_K_XL | **16,494 MiB** | **0.005607 ± 0.000241** | 96.647% |

## 1. At 3.50bpw the advantage disappears — the 1.45× was an artifact of an empty gap

| | VRAM | KLD |
|---|---|---|
| EXL3 3.50bpw | 12,016 MiB | 0.024979 ± 0.000723 |
| **UD-Q3_K_XL** | 12,446 MiB | **0.024951 ± 0.000804** |

**The same number, 0.11% apart, far inside both error bars.** EXL3 is 430 MiB (3.6%) smaller at equal
fidelity — a directly measured matched-fidelity pair with no interpolation at all.

Test 10 reported **1.45×** there. That figure came from interpolating the UD envelope across a **2 GB gap**
whose nearest measured points were UD-IQ3_XXS (11,532 MiB) and UD-IQ4_XS (13,500 MiB). **UD-Q3_K_XL lands in
that gap and sits on top of EXL3's result.** The advantage was never 1.45×; it was an artifact of having no
neighbour.

## 2. At 5 bpw the advantage is real, and is now measured rather than interpolated

| | VRAM | KLD |
|---|---|---|
| EXL3 5.00bpw | 16,372 MiB | 0.003994 ± 0.000227 |
| **UD-Q4_K_XL** | 16,494 MiB | **0.005607 ± 0.000241** |

**122 MiB apart — 0.7% — and EXL3 is 1.40× closer to the reference.** This is the cleanest matched-VRAM
comparison in the campaign, and it *replaces* an interpolation across an even wider gap (UD-Q4_K_M at 15,448
to Q6_K at 21,276 — 5.8 GB with nothing in between).

## What changes in test 10's published numbers

| EXL3 point | test 10 | corrected | change |
|---|---|---|---|
| 2.50bpw | +269 MiB (+3.0%) | +269 MiB (+3.0%) | — |
| 3.00bpw | +1,019 MiB (+9.6%) | +1,008 MiB (+9.5%) | negligible |
| **3.50bpw** | **+662 MiB (+5.5%)** | **+428 MiB (+3.6%)** | **−35%** |
| 4.00bpw | +788 MiB (+5.9%) | +788 MiB (+5.9%) | — |
| **5.00bpw** | **+2,854 MiB (+17.4%)** | **+2,422 MiB (+14.8%)** | **−15%** |

**The campaign's headline becomes "EXL3 is 1.33–1.35× closer at matched VRAM on the controlled UD curve,
worth 3.6–9.5% of memory, rising to 1.40× and 14.8% at 5 bpw."** Previously "1.33–1.45×, 5–10%, 17% at
5 bpw." **Smaller, and now anchored on measured neighbours instead of interpolation at the two points that
mattered most.**

## Predictions

| id | prediction | result |
|---|---|---|
| P-X1 | UD-Q3_K_XL lands at or below the interpolated envelope at its VRAM | **CONFIRMED** — 0.024951 against an interpolation of 0.02843 at 12,446 MiB |
| P-X2 | the redraw cuts EXL3 3.50bpw's advantage below 1.30× | **FALSIFIED** — it fell to **1.354×**, missing the bar |
| P-X3 | EXL3 3.50bpw still leads the redrawn envelope | **CONFIRMED** — 1.354×, so test 10's headline is corrected, not withdrawn |
| P-X4 | UD-Q4_K_XL improves the envelope above 15 GB | **CONFIRMED** — 0.005607 against an interpolation of ~0.0065 at 16,494 MiB |

**P-X2 is the honest miss.** It predicted the advantage would fall below 1.30× and it stopped at 1.354×. The
prereg fixed that bar before the file was downloaded; it is scored as written.

**The test was one-directional by construction** — adding points to a lower envelope can only push it down —
so no outcome here could have flattered the campaign. That was the reason to run it.

## Defects found

**`score_exl3_compression.py` silently drops any arm missing from its `GGUF` label map.** The first scoring
run produced a complete, plausible report with every prediction confirmed and *nothing changed*, because
`G3XL` was never placed on the curve. No error, no warning. It was caught only because arm names are printed
in the output table and the new one was absent. **Registry entries added for `G3XL` and `G4XL`; no scoring
logic was changed.** Same failure family as the waiter bugs of 2026-09-13: a check that returns a clean
result without having run.

## Limits

- **Two arms.** `UD-Q5_K_XL` and `UD-Q6_K_XL` remain unmeasured; the curve above 16.5 GB still interpolates
  to Q6_K across 4.8 GB. **P-X4's confirmation makes extending upward worth doing** — the same defect could
  be hiding there.
- **G3u remains revision `f9758630`**, hours older than unsloth's 08-19 re-cut, exactly as
  `RESULT_EXL3_COMPRESSION.md` records. This run does not fix that.
- Verified 2026-09-14: the unsloth repo has been unchanged since 2026-08-20 and its README labels these
  **Dynamic 3.0**, so this is the current generation — the curve was not stale, it was incomplete.
- Peak VRAM is measured on two P100s; a different device count would change placement and therefore VRAM.

Artifacts: `ud3xl/` — `merged.jsonl`, `new_rows.jsonl`, `score_output.txt`, `kld.log`, `ppl_*.log`.
