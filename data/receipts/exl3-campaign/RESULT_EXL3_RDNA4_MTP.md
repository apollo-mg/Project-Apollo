# Result — on RDNA4, MTP gives EXL3 nothing and GGUF 1.7×, so the gap at matched size is 2.1–2.4×

> **Superseded on the current build (2026-09-26):** on buun `0b2789f23`, MTP gives EXL3 1.80-1.96x and the gap is 1.19-1.29x. The EXL3 int8 GEMV rework (09-17/18) fixed the 4- and 8-row scaling measured below. See `RESULT_EXL3_RDNA4_RERUN.md`. The numbers here remain correct for `da458765d`.

**Run 2026-09-13, 09:55–10:07, on the control plane's RX 9070 XT (gfx1201), buun `da458765d`.**
Pre-registered in `PREREG_EXL3_RDNA4_MTP.md` (`4b581ef`), driver and scorer `exl3_rdna4_mtp.py`,
committed with it. Raw data in `rdna4_mtp/`. EXL3 campaign test 9, ledger O5. **Mark's question:** the
MTP-enabled delta between EXL3 and GGUF at roughly equal bpw.

## The answer

| arm | size (resident) | d0 | d1 | d2 | d3 | best | MTP gain |
|---|---|---|---|---|---|---|---|
| **EXL3 3.00bpw** | ~10.3 GB | **22.49** | 22.22 | 20.78 | 20.04 | **depth 0** | **1.00× (none)** |
| GGUF IQ3_XXS | 10.02 GB | 30.54 | 43.55 | **54.02** | 53.94 | depth 2 | **1.77×** |
| **EXL3 3.50bpw** | ~11.8 GB | **22.83** | 22.31 | 21.02 | 20.74 | **depth 0** | **1.00× (none)** |
| GGUF i1-IQ3_M | 12.21 GB | 28.21 | 41.58 | **47.70** | 47.48 | depth 2 | **1.69×** |

- **With MTP enabled, GGUF is 2.40× faster at ~10 GB and 2.09× at ~12 GB.**
- **Without MTP the gap is only 1.36× and 1.24×.** MTP is what doubles it.
- **MTP is a net loss for EXL3 at every depth on this card.** Not a small gain — a loss.
- **Acceptance is not the cause.** At depth 1 the drafts land equally well (EXL3 58/68, GGUF 55/71), and
  drafted-per-token rises with depth in all four arms, so drafting works. The cost of verifying is the
  problem.

| id | prediction | result |
|---|---|---|
| P-N1 | **Gate:** MTP engages on both formats on RDNA4 | **CONFIRMED** in all four arms |
| P-N2 | both formats gain from MTP | **FALSIFIED.** EXL3 gains nothing: 1.00× in both pairs |
| P-N3 | EXL3's MTP gain is below GGUF's | **CONFIRMED.** 1.00 vs 1.77, and 1.00 vs 1.69 |
| P-N4 | EXL3's best depth ≤ GGUF's | **CONFIRMED.** 0 vs 2, both pairs |
| P-N5 | EXL3 is slower at best depth | **CONFIRMED.** 22.49 vs 54.02; 22.83 vs 47.70 |
| P-N6 | the ratio is within ±0.15 of Pascal's 0.648 | **FALSIFIED.** 0.416 and 0.479 — worse here |
| P-N7 | the micro-batch penalty transfers | **CONFIRMED.** A(4) 1.27 vs 2.30 |

## The mechanism, and why this is not a Pascal artefact

`llama-bench -p 64 -ub 1,2,4,8,16` on pair A, one load per model (test 4's instrument, warm baseline):

| A(m) | 2 | 4 | 8 | 16 |
|---|---|---|---|---|
| **EXL3 3.00bpw** | 1.16 | **1.27** | 1.25 | 1.59 |
| **GGUF IQ3_XXS** | 1.73 | **2.30** | 3.38 | 6.41 |

**A 4-row verify batch costs EXL3 3.15× a single row on RDNA4** (4 ÷ 1.27) against GGUF's 1.74×. On
Pascal the same measurement gave 2.08× and 1.37×. **The row-scaling penalty is intrinsic to the EXL3
kernel, and RDNA4 exposes it more**, which is exactly why speculative decoding cannot pay for itself
here: three drafts plus a verify cost more than the tokens they save.

**This settles the transferability question the prereg posed.** It is not the P100's compute-to-bandwidth
balance. The kernel does not amortize rows on either architecture.

## What it means

- **On the 9070, the honest recommendation is GGUF.** At every size that fits the card, a GGUF with MTP
  is roughly twice as fast as EXL3, and 1.2–1.4× faster even with MTP off.
- **Test 8's "EXL3's advantage becomes purchasable here" needs this qualification.** It is true that
  Q6_K does not fit the 9070 while EXL3 3.00bpw does — but the GGUF that *does* fit at the same size
  (IQ3_XXS, 10.02 GB) is 2.4× faster. **Whether EXL3's quality edge at that size is worth 2.4× is a
  question this test cannot answer**, and it is the obvious next measurement: KLD for EXL3 3.00bpw
  against IQ3_XXS, which runs on `.73` against the reference already there.
- **For buun, this is the strongest version of the row-scaling finding yet:** the same defect, measured
  on two architectures, costing EXL3 the entire benefit of his own MTP implementation on RDNA4.

## Deviations and limits

- **`q8_0` KV at 8192 context, not the daily driver's VBR at 262k**, because the 9070 has ~13.2 GB usable
  after the compositor. These speeds are internally comparable only.
- **Provenance gap:** the `GSQ-RCO-IQ3_XXS-mtp` file has been on this box since 2026-09-03 and appears in
  our receipts, but **no published sha256 is recorded for it**. Declared in the prereg as an exception to
  verify-before-use. The `i1-IQ3_M` and both EXL3 snapshots are hash-verified.
- **Three quantization recipes, not one.** IQ3_XXS, i1-IQ3_M and EXL3 trellis quants differ in method;
  this is a speed comparison at matched footprint, not a quality one.
- **Three reps of 128 tokens per point, one card.**
- **Our own prior for context:** `KNOWN_GOOD_STATE_20260909.md` recorded this GGUF at 27.4 t/s without
  MTP and 43–60 with it, on an older build (`3823c9eb6`). Today's 30.54 and 54.02 sit just above that
  range.
