# Note — at matched footprint the EXL3 quality gap is visible to trained readers, and I could not see it

**2026-09-14 12:27–13:05, `.194`.** Flash-Next, three builds, byte-identical settings: `-c 24576 --kv-unified
-ctk q8_0 -ctv q8_0 --reasoning-effort medium --min-p 0 --jinja -lv 4`, temperature 1.0, `max_tokens` 8000,
three draws each, thinking on. Scorer `svg_probe.py` unchanged. Page:
`https://claude.ai/code/artifact/0a94c170-b14f-4ba2-b549-f7648d146bdb`

| build | resident | cold load | decode | KLD (turboderp) | scores |
|---|---|---|---|---|---|
| UD-IQ4_XS `-ncmoe 2` | 61,566 MiB | ~137 s | 17–18 tok/s | **0.0165** | 10, 9, 9 |
| **EXL3 3.05bpw_h5_ng5** | **51,080 MiB** | **768 s** | 14.5–14.6 tok/s | 0.0177 | 10, 10, 10 |
| UD-Q2_K_XL | 51,122 MiB | **106 s** | **18.3–20.0 tok/s** | 0.0533 | 10, 10, 10 |

**EXL3 and Q2_K_XL are 42 MiB apart** — the cleanest matched-footprint pair in the campaign.

## The result, and my error

**Mark and buun independently judged the EXL3 row better. I had written "I cannot tell these apart" into a
published page, and it was wrong.** The claim was made after examining only two of the three pairs closely;
the third was rendered and never looked at. **Q2_K_XL's third draw is the weakest of all nine** — no sky, sun
or ground at all, a neck drawn as a thin stroke that does not meet the body, both legs merged into one shape,
and a stray path trailing off the head.

**Mechanically defensible:** EXL3 3/3 complete scenes, IQ4_XS 3/3, **Q2_K_XL 2/3**. Consistency across draws
separates the rows without appealing to taste.

**The process failure is the lesson:** I had the render on disk and asserted a conclusion without opening it.
The rule that would have caught it — *look at every artifact before drawing a conclusion from the set* — costs
seconds and I skipped it on the one that mattered.

## What this does to the campaign's reading of KLD

The two results line up rather than conflict:

- **Test 11** (27B, HumanEval+, 164 paired problems, mechanical): the pair was a **KLD tie**
  (0.046152 vs 0.047609) → **task tie**, p = 1.000, CI excluding ±5 points.
- **Here**: the pair is **3× apart** (0.0177 vs 0.0533) → **visible** to two trained readers.

**Where KLD ties, the task ties; where it differs threefold, the difference reaches the drawing.** KLD is
doing real work. It is not sufficient alone — Mark's point before the run — but this is evidence *for* its
validity, not against it.

## What is left open, deliberately

**IQ4_XS vs EXL3 is not called here.** IQ4 costs **11.5 GB more** and is marginally ahead on KLD; EXL3 loads
**5.6× slower** and decodes ~20% slower. Both drew three complete scenes. Having just been wrong on an
aesthetic judgement, I am not making the next one from the same chair — the nine drawings are on the page at
identical settings for readers better calibrated than the scorer.

## Operational findings alongside

- **EXL3 costs 7.2× the load time of a same-footprint GGUF** (768 s vs 106 s) because its loader stages a
  31 GB temp file. `-lm dio` cannot help; that is the safetensors path, not the GGUF read.
- Disk fell **61 → 30 GB** during that staging and recovered fully on exit. The arm gated on ≥ 40 GB free
  and would have aborted rather than risk the ENOSPC that killed Stage 2 once.
- **The scorer contributed nothing.** All nine drawings scored 9 or 10, and the two 9s were the sun defect
  (`SUN_REPRO.md`), not quality.

## Limits

Three draws per arm, one prompt, one model, one task. The quality judgements are two readers' and mine, not
blind ratings — and mine was wrong. A blind round with the existing svgbench raters is the way to settle
IQ4 vs EXL3 properly.
