# Pre-registration -- EXL3 vs GGUF on RDNA4, re-run on buun `0b2789f23` (was `da458765d`)

**2026-09-26, before any run on the new build.** Mark: *"might be worth loading up an EXL3 model and checking
performance figures again on a current build."*

**Prior art checked:** `ledger_precheck.py "EXL3 RDNA4 9070 speed tokens per second GGUF"` ->
`RESULT_EXL3_RDNA4_MTP.md` (09-13, `da458765d`): EXL3 ~22.5 t/s at every MTP depth (no gain); GGUF 30.5 -> 54.0
(IQ3_XXS) and 28.2 -> 47.7 (i1-IQ3_M) with MTP; A(4) row scaling 1.27 (EXL3) vs 2.30 (GGUF). There are **81 buun
commits** since `38ada0e1b`, including EXL3 load fixes (`a2fd78181`, `5f4fa8c28`) and HIP VRAM accounting
(`0b2789f23`). None is an EXL3 kernel change by title.

**What this adds:** the same instrument on the current build. It shows whether the 2.1-2.4x gap and EXL3's
row-scaling penalty still hold.

## Instrument

- **Unchanged:** `exl3_rdna4_mtp.py`, the same four arms (E3, G3x, E35, G3m), MTP depths 0-3, `llama-bench -ub
  1,2,4,8,16`, the same prompts, flags and port.
- **The only change:** `RDNA4_BUILD=/mnt/TG_2TB/Projects/buun-0b278/build_rocm`, which is `0b2789f23` built for
  gfx1201 with the `da458765d` build's CMake options: HIP, gfx1201, Release, HIP graphs.
- **Output:** `rdna4_mtp_0b278/`.
- **Box:** the 9070 with the speech server stopped, the same state as the 09-13 run as far as the card is
  concerned. The desktop session is running (not controlled; the same was true on 09-13).

## Predictions

| # | claim | test | conf |
|---|---|---|---:|
| R1 | EXL3 decode unchanged | E3 and E35 best-depth t/s within +/-5 % of 22.49 / 22.83 | 0.55 |
| R2 | GGUF with MTP unchanged | G3x and G3m best-depth t/s within +/-5 % of 54.02 / 47.70 | 0.55 |
| R3 | still no MTP gain for EXL3 | E3 and E35 best / depth-0 <= 1.05 | 0.70 |
| R4 | row-scaling penalty unchanged | E3 A(4) within +/-10 % of 1.27 | 0.60 |
| R5 | the headline gap holds | GGUF-best / EXL3-best in [1.9, 2.6] for both pairs | 0.60 |

**Gate:** MTP engages on every arm at depth >= 1 (drafted > 0 and accepted > 0), as P-N1 required on 09-13. A gate
failure is reported and that arm's depth rows are excluded.

**Reading:**
- **R1-R5 true:** the 09-13 decision table stands on the current build.
- **Any of R1-R4 false:** the build changed performance, reported with the direction and size.

## Not established by design

One run per point (as on 09-13), one card, one prompt; decode only, no quality measurement.
