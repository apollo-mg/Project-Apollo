# Fed Bonsai's exact loop text, a near-Q8 Qwen3.8 makes the same close-or-continue call at 26 of 26 decision points: Bonsai's stopping behaviour is intact, and what loops is the content it generates

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

## What it means

- **Bonsai's close-or-continue decision is Qwen3.8's.** Given the same text, the near-Q8 model makes the same call
  every time, including re-checking correct UNKNOWN drafts (X2 false). The ternary quantization did not break
  stopping.
- **So the loop is upstream, in what Bonsai writes.** On the same prompts, the healthy quants' *own* traces
  converge on "no such thing" (`RESULT_MARKER_PENALTY_BONSAI.md`: Q6_K and IQ3_XXS abstain; Bonsai invents "1385",
  "9013", "1971", "1991"). Bonsai generates plausible invented candidates, such as a "Treaty of Kellworth, 1329 or
  1330". Any Qwen3.8 reading that text would keep checking it, and Q6_K does.
- **Stopping is not what to fix. What Bonsai believes is.** The calibration damage (invented facts on unanswerable
  items) produces contexts where continuing is the right move for the model family. A penalty on re-check words
  fights the family's normal behaviour, not the defect.
- **buun's "the tokens are model-specific" point, refined.** The re-check vocabulary ("Double", "Let", "But",
  "Need") is **Qwen3.8's**, shared by Bonsai and Q6_K. It is not Bonsai-specific; it differs from the paper's list
  because the paper studied other models.
- **The legitimately-hard-vs-pathological detector should watch content, not stopping probabilities.** A
  healthy model and Bonsai emit the same stopping signals on the same text.

## Not established

- A teacher-forced replay: Q6_K read Bonsai's words; it did not generate its own.
- 26 decision points from 13 traces, one healthy quant (Q6_K, not BF16), CAL unanswerable items only.
- `.73` runs VBR KV (dynamic); the effect of KV quantization on these distributions is not separated, though it is
  small at Q6_K scale.
