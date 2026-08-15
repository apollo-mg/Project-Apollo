# Split mode x MTP composes cleanly, and speculation multiplies variance by ~8x

**2026-08-15, `.73` (2x P100, 150 W / 1063 MHz), same harness throughout.** Resolves
`PREREG_SPLIT_X_MTP.md` and its IQ2 addendum, and restates the ratios in
`NOTE_PRECISION_VS_SPECULATION.md` from same-harness data as that note required. 16 arms,
320 responses, all present (AFM-7 checked). Raw: `raw73/`, verdict via `../verdict.py`.

| arm | median t/s | spread | acceptance | reps stable |
|---|---:|---:|---:|---|
| `sing_off` | 8.53 | 5.4 % | — | yes |
| `sing_on` | 12.84 | 46.6 % | 65.68 % | 1 prompt bad |
| `layer_off` | 8.59 | 5.1 % | — | yes |
| `layer_on` | 12.98 | 49.8 % | 65.68 % | 1 prompt bad |
| `tens_off` | 13.89 | 7.3 % | — | yes |
| `tens_on` | 20.75 | 57.6 % | 65.93 % | yes |
| `iq2_sing_off` | 8.75 | 5.4 % | — | yes |
| `iq2_sing_on` | 13.32 | 41.2 % | 65.70 % | 1 prompt bad |
| `iq2_layer_off` | 8.75 | 5.1 % | — | yes |
| `iq2_layer_on` | 13.32 | 40.5 % | 65.70 % | 1 prompt bad |
| `iq2_tens_off` | 14.16 | 6.6 % | — | yes |
| `iq2_tens_on` | 21.05 | 42.3 % | 62.89 % | yes |
| `bart_off` | 7.87 | 2.4 % | — | yes |
| `bart_on` | 14.48 | 40.8 % | 70.70 % | yes |
| `unsl_off` | 7.68 | 2.2 % | — | yes |
| `unsl_on` | 13.96 | 43.7 % | 71.50 % | yes |

## P1–P6: the ladder composes multiplicatively

| effect | IQ3_XXS | IQ2_M |
|---|---:|---:|
| `-sm tensor` over single (MTP off) | **1.628x** | **1.618x** |
| `-sm layer` over single (MTP off) | 1.007x | 1.000x |
| MTP multiplier, single | 1.505x | 1.522x |
| MTP multiplier, layer | 1.511x | 1.522x |
| MTP multiplier, tensor | 1.494x | 1.487x |

**`-sm layer` is inert at both tiers** — 1.007x and 1.000x. Confirms
`RESULT_P100_SM_TENSOR.md` on a second quant.

**The MTP multiplier is independent of split mode** (1.487–1.522x across all six cells), so
the two effects compose without interference: `tens_on / sing_off` = 20.75/8.53 = **2.433x**
against 1.628 x 1.494 = 2.432x predicted. Exact to three digits. They are orthogonal knobs.

**The MTP multiplier does depend on the quant tier**: ~1.50x at IQ3/IQ2 against **1.82–1.84x**
at Q6_K. A less-damaged target accepts more drafts (65.7 % vs 70.7–71.5 %) *and* gains more
from each. That is `S3` reconfirmed on the clean harness.

## The precision-vs-speculation restatement

`NOTE_PRECISION_VS_SPECULATION.md` flagged that its ratios came from two different harnesses
and had to be redone. Same-harness numbers, `-sm layer` throughout:

| | t/s | vs `IQ3_XXS` no-MTP |
|---|---:|---:|
| `UD-IQ3_XXS`, MTP off | 8.59 | 1.000x |
| `Q6_K` (unsloth), MTP off | 7.68 | 0.894x |
| `Q6_K` (unsloth), MTP on | **13.96** | **1.625x** |

Same conclusion, now unconfounded. **Q6_K with MTP beats IQ3_XXS without it by 1.63x at
roughly twice the weight precision.** The measured throughput cost of that precision is
8.59/7.68 = **1.118x**, against a file-size ratio of 1.921x — so the size ratio overstates the
cost by 72 %, and the corrected rule (`speculative multiplier > measured throughput ratio`)
stands: 1.82x clears a 1.12x bar comfortably.

**IQ2_M is only 2.6 % faster than IQ3_XXS** (8.75 vs 8.53) for a 13 % smaller body. Third
independent confirmation that this hardware is not bandwidth-bound at 150 W.

## The unplanned finding: speculation multiplies throughput variance ~8x

Look at the spread column. Every `off` arm sits at **2.2–7.3 %**; every `on` arm at
**40.5–57.6 %**. Turning speculation on increases within-arm throughput spread by roughly an
order of magnitude, on both quants, both split modes, both packagers, and on completely
different hardware — `qwen35-drafters` saw the same thing on RDNA4 (`off` stdev 0.74 against
`dfl_n15` 55.48).

The mechanism is the same one that produced the content split there: acceptance is strongly
content-dependent, so throughput inherits that dependence. **A speculative t/s figure is a
statement about the prompt mix, not about the model.** Anyone quoting a single speculative
speedup without saying what was generated is quoting their prompt set.

This also has a practical consequence for benchmarking that we walked into ourselves: when
`off` arms are tight and `on` arms are 8x noisier, a paired design across the same prompts is
not optional — comparing unpaired speculative means needs far more samples than it looks.

## Limits

- 5 prompts x 2 reps per arm, 20 responses. Reps are near-deterministic replays (AFM-6); four
  `_on` arms had one prompt each that did not reproduce, all at `sing`/`layer`, none at
  `tens`. Not investigated.
- Packager arms ran `-sm layer -ts 1,1`, which is inert (1.007x), so they compare to the
  `layer` rows directly. Stated rather than assumed.
- Clock state: 150 W / 1063 MHz fleet standing config. Pre-2026-07-17 receipts are
  autoboost-1328 and are not comparable.
