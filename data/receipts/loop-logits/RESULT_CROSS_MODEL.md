# At the end of Bonsai's wrap-up lines, a near-Q8 Qwen3.8 fed the same text makes the same close-or-continue call (16 of 16, plus 10 of 10 real ends): that decision is not where Bonsai breaks

**2026-09-26.** Prereg `PREREG_CROSS_MODEL.md` (`d11cfe1`). The healthy model was `.73`'s Qwen3.8-27B **Q6_K** (KLD
0.0028 against Q8_0), buun `0b2789f23`, called directly with `cache_prompt: false`. It was fed Bonsai 2's exact
token sequences from the 13 replayed traces that have wrap-up lines. Raw: `raw/xmodel_q6k.jsonl`,
`raw/logs/run_xmodel.log`.

- **Gate S** (identical token ids at every probe position): **PASS on all 13 traces**, 0 mismatches.
- **Run history:** the first attempt crashed `.73`'s server at the 11,003-token probe
  (`vbr-artifact-store/INCIDENT_73_META_SPLIT_STATE_STACK_OVERFLOW.md`). This run is the complete re-run after the
  512 MiB stack mitigation. The same probe then succeeded.

## Result

| # | claim | result | verdict |
|---|---|---|---|
| X1 | control: at Bonsai's real END points, Q6_K P(`</think>`) >= 0.5 at >= 80 % | **10 / 10** (0.997-1.000) | **held** |
| X2 | at the 3 points where Bonsai drafted **UNKNOWN** and re-checked, Q6_K would close (>= 2 of 3) | **0 / 3**: Q6_K re-checks too ("Double" 0.74 / 0.63 / 0.65) | **false** |
| X3 | at the 5 loop reopen points, Q6_K would also continue (>= 4 of 5) | **5 / 5** (P(`</think>`) 0.000) | **held** |

**Descriptive: the top-1 next token is identical at 26 / 26 points,** with close probabilities:

| point | Bonsai | Q6_K |
|---|---|---|
| LOOP U5 r2 @5722, after "Need final: Exact Answer: 1330." | But 0.90 | But 0.886 |
| LOOP U2 r3 @8049, after "Need decide final: UNKNOWN or a unit..." | But 0.97 | But 0.976 |
| LOOP U2 r3 @9825 | Let 0.996 | Let 0.998 |
| LONG-OK U2 r2 @7957, after an UNKNOWN draft | Double 0.77 | Double 0.737 |
| SHORT U8 r1 @1749 | Let 0.98 | Let 0.984 |
| every real END | `</think>` 0.98-1.00 | `</think>` 0.997-1.000 |

## What it means (scoped)

- **The 26/26 is 10 real ENDs (the X1 control, trivially shared) plus 16 wrap-up points.** Those points were
  chosen post hoc because the text nearly dictates the next move there, so agreement is expected even from a
  moderately damaged model. The supported claim is narrow: **at the end of a wrap-up line, Q6_K makes the same
  close-or-continue call Bonsai made**, including re-checking Bonsai's correct UNKNOWN drafts (X2 false).
- **Not shown: that Bonsai's stopping is intact overall.** The untested question is whether a healthy model would
  **start** wrapping up earlier in the same loop text, for example writing "Need final: Exact Answer: UNKNOWN" at a
  boundary where Bonsai kept enumerating. That is Amendment 1 of the prereg (every 10th boundary inside the three
  loops), run separately.
- **The re-check vocabulary is shared.** "Double", "Let", "But" and "Need" at these points are Qwen3.8's, not
  Bonsai-specific. They differ from the paper's list because the paper studied other models. That refines buun's
  "model-specific tokens" point: specific to the model family.
- **The "invented candidates" reading rests on one loop.** Only U5 r2 drafted an invented value ("1330") and kept
  checking it. U2 r3 circled "UNKNOWN or a unit" without inventing one, and U5 r3 never drafted. On the same
  prompts, the healthy quants' own traces converge on UNKNOWN (`RESULT_MARKER_PENALTY_BONSAI.md`), so the
  difference is in what gets written upstream of these points. Which part of the upstream text differs is what
  Amendment 1 looks at.

## Not established

- A teacher-forced replay: Q6_K read Bonsai's words; it did not generate its own.
- 26 decision points from 13 traces, one healthy quant (Q6_K, not BF16), CAL unanswerable items only.
- `.73` runs VBR KV (dynamic); the effect of KV quantization on these distributions is not separated, though it is
  small at Q6_K scale.
