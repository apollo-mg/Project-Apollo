# Pelican -- Nemotron 3.5 Bolt 74B-A9B (NVIDIA 2-bit QAT) on .73: 0, 0, 8, 9, 7 / 10; both zeros are one slip, `y1` written where `y2` belongs

**Date:** 2026-10-15, 19:44-20:01 EDT. A release-day look, not a registered panel.
**Prior art checked:** `ledger_precheck.py "pelican svg bicycle"` -> the svgbench receipts (ladder, pelican3,
Turbo-Brilliance). This adds a third model family and the first 2-bit QAT model on the pelican.

**Protocol (as svgbench):** `Generate an SVG of a pelican riding a bicycle.`, temperature 1.0, server-default
samplers, `max_tokens` 20000, streamed, 480 s generation cap; model default reasoning (on). Scored with the unchanged
`tools/svgbench/svg_probe.py` (last `<svg>` of the answer, 64x30 grid) by `score_bolt.py`. Server: upstream llama.cpp
v0.7.0 `620d222`, `-ngl 99 -c 24576 -np 1 -fa on`, no drafter, fresh server; .73, 2x P100 at 1328 MHz.

| rep | score | tokens | reasoning chars | elapsed | notes |
|---|---:|---:|---:|---:|---|
| r1 | **0** | 7,792 | 16,645 | 285 s | invalid XML: `x2="330" y1="155"` (duplicate `y1`) |
| r2 | **0** | 2,794 | 5,605 | 102 s | invalid XML: `x2="130" y1="185"`, same slip |
| r3 | **8** | 5,420 | 10,100 | 198 s | best: white pelican seated on the frame, orange legs to the pedals, open beak with pouch |
| r4 | **9** | 1,745 | 2,096 | 64 s | body slung between the wheels, beak on the stem, legs dangling |
| r5 | **7** | 11,971 | 23,821 | 439 s | good bike; pelican in pieces (small body under the frame, loose beak shapes) |

Median 7/10 and 5,420 tokens; no rep capped; decode 27.3-27.5 tok/s throughout.

**The slip:** after writing `x2=`, the model writes `y1=` again where `y2=` belongs. 2 of 35 `<line>` elements across
the five drawings, each one invalidating its whole file (strict XML; Chrome rejects a standalone .svg with a duplicate
attribute too). At temperature 1.0 this is a sampling slip, not a misunderstanding: the other 33 are right. It is the
kind of single-token precision error that also breaks a tool call's JSON.

`.lenient.svg/.png` copies drop the duplicate attribute (keeping the first, as an HTML parser does) so the drawing can
be seen; they are never scored. Their long stray line is the missing `y2`, which defaults to 0.

Files: `BOLT_r*.content.txt`, `.reasoning.txt`, `_p1.svg/.png/.grid.txt`, `results.jsonl`, `scores.json`,
`server.log`, `state.log`, `pelican.py`, `pelican_chain.sh`, `score_bolt.py`.
