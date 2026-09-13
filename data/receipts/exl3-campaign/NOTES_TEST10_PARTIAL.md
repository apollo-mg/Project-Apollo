# Working notes — test 10 read at 13:59, before the last three arms (to fold into RESULT_EXL3_COMPRESSION.md)

**Done:** E25, E30, E35, G2u, G2x, G3u, joined with test 3's E, E5, G4, G5, G6. **Pending:** G3xx, G3m, BRIDGE.
Read with `tools/score_exl3_compression.py` on a copy of `.73`'s `results.jsonl`. **Nothing here is final.**

## Things the final receipt must not lose

1. **P-C5 is defined only in the scorer** (`pair()`: lower KLD wins, no VRAM condition) and in Amendment 1's
   commit message — **not in the prereg text.** As coded it CONFIRMS: E30 0.0462 vs G2u 0.0842. **But E30 sits at
   10,568 MiB against G2u's 9,404 — 12% more VRAM.** The premise Mark took from the chart ("3 bpw in the same space
   as UD-Q2 XL") **does not hold on the 27B.** The same-space pair is **E25 (9,116 MiB, 0.0934) vs G2u (9,404,
   0.0842): UD-Q2_K_XL is 10% closer to the reference for 3% more VRAM — about even.**
2. **Amendment 1's near-vertical-segment worry came true the other way round.** On disk G2x was larger than G2u; in
   VRAM **G2x (9,272) is smaller than G2u (9,404)**, so the envelope keeps both, and the 132-MiB step G2x → G2u
   drops KLD from 0.1745 to 0.0842. **E25's "+269 MiB" exchange rate is interpolated across that step and must not
   be quoted.**
3. **P-C2:** all-packagers **FALSIFIED** — the advantage grows with size (log-gap 0.289 at 10.6 GB, 0.509 at 16.4 GB).
   UD-only scores CONFIRMED at 0.289 vs 0.288 — **a tie in substance; report it as no trend.**
4. **The compression exchange rate on the dense 27B (UD-only, bracketed):** 3.00bpw saves **1,019 MiB (9.6%)**,
   3.50bpw **662 (5.5%)**, 4.00bpw **788 (5.9%)**; 5.00bpw saves **2,854 MiB (17.4%)** against all packagers. EXL3's
   matched-fidelity saving here is **~5–10% of VRAM in the 10–14 GB range** — real, and far smaller than turboderp's
   Flash-Next chart implies (EXL3 3.05 ≈ UD-IQ4_XS there). Consistent with test 3 (1.3× lower KLD at ~4 bpw vs his 2.5×).
5. **P-C3 confirms against the weak recipe.** E25 beats AD-IQ2_XS (0.0934 vs 0.1745), but at nearly the same VRAM
   UD-Q2_K_XL has less than half AD-IQ2_XS's KLD. **At the bottom of the range the packager matters as much as the
   format.**
6. **P-C1 is CONFIRMED on both curves** at every bracketed EXL3 point: 3.00, 3.50, 4.00bpw (and 5.00 against all
   packagers). E25 is excluded as below every GGUF point, as Amendment 1 declared.

## Why the 27B and Flash-Next may differ (hypotheses, not findings)

- turboderp's chart is on a **bpw axis excluding embeddings and head**; ours is **peak VRAM**. UD-Q2_K_XL's real bpw
  differs per model recipe, so "same space" is model-specific.
- MoE experts may simply favour trellis quantization more than dense layers do — or his in-domain trace and FP
  reference differ from our wikitext against Q8_0. Only a same-method Flash-Next KLD could separate these, and a
  Q8_0 reference of a 180B model cannot run on this fleet.
