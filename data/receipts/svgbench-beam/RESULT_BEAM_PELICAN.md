# Pelican -- Reflection Beam 1.0 501B-A23B (2-bit) on .194: 8, 10, 9, 7, 10 / 10; all five render, median 9

**Date:** 2026-10-17, 14:32-16:24 EDT. A look, not a registered panel.
**Prior art checked:** `ledger_precheck.py "pelican svg bicycle"` -> the svgbench receipts (ladder, pelican3,
Turbo-Brilliance, blind panel) and `svgbench-bolt/RESULT_BOLT_PELICAN.md` (Bolt 0, 0, 8, 9, 7). This adds a fourth
model family, the largest model on the pelican, and a 2-bit file spread across GPUs and system RAM.

**Protocol (as svgbench, one change):** `Generate an SVG of a pelican riding a bicycle.`, temperature 1.0,
server-default samplers, `max_tokens` 20000, streamed; model default reasoning, which for Beam is `max`
(`/apply-template` rendered `Reasoning effort: 512`). Scored with the unchanged `tools/svgbench/svg_probe.py` (last
`<svg>` of the answer, 64x30 grid) by `score_beam.py`.
- **Change: the 480 s generation cap became 5400 s.** Beam decodes at ~4.7 tok/s here, so 480 s would stop it near
  2,200 tokens. All five would have been cut off mid-reasoning (the shortest took 791 s). None came near either cap:
  every rep ended on `finish: stop`, the longest at 8,282 tokens.

**Server:** upstream llama.cpp `f74e2fa6a` (after the Beam merge), AtomicChat `AD-IQ2_XXS` (133.8 GB, sha256-verified for
`PREREG_BEAM`), .194 4x P100 at 150 W / 1063 MHz, `PREREG_BEAM`'s placement (routed experts of the last 28 MoE layers on
CPU, `-ts 8,6,6,33`, `--no-op-offload`) with `-c 24576`, f16 KV, `-np 1`, fresh server (`serve_pelican.sh`). `/props`
confirmed the file and `n_ctx` 24576. VRAM after load 12.7 / 14.3 / 15.9 / 14.4 GB.

| rep | score | failed checks | tokens | reasoning chars | elapsed | decode |
|---|---:|---|---:|---:|---:|---:|
| r1 | **8** | subject_attached, assembly_coherent | 7,942 | 12,755 | 28.7 min | 4.67 tok/s |
| r2 | **10** | | 6,200 | 10,274 | 21.7 min | 4.77 tok/s |
| r3 | **9** | assembly_coherent | 3,778 | 4,331 | 13.2 min | 4.78 tok/s |
| r4 | **7** | two_lower_clusters, clusters_separated, structure_between | 8,282 | 16,377 | 29.0 min | 4.76 tok/s |
| r5 | **10** | | 5,384 | 10,029 | 18.8 min | 4.77 tok/s |

Median **9/10**, 6,200 tokens, 21.7 minutes per drawing; five drawings in 1 h 52 min.

**Looking at them** (`BEAM_contact_sheet.png`, r1-r3 top row, r4-r5 bottom): every rep is a recognisable white pelican with
an orange or yellow pouch, seated on a two-wheeled bicycle with its legs to the pedals. r1 is the most finished (sky
gradient, motion lines, a shaded frame); its failed checks are structural judgements of a body drawn across the top
tube. r4's three failures come from the dark shadow ellipse under the bicycle: in the occupancy grid
(`BEAM_r4_p1.grid.txt`) it bridges the two wheels into one lower cluster. To the eye its two wheels are clear.

**Against Bolt** (same protocol except the cap, .73, 2x P100): Bolt scored 0, 0, 8, 9, 7 (median 7), and both zeros
were one token-level slip that made the file invalid XML. Beam's five files all parse and render. One drawing per rep,
five reps each: this is a look, not a ranking.

Files: `BEAM_r*.content.txt`, `.reasoning.txt`, `_p1.svg/.png/.grid.txt`, `BEAM_contact_sheet.png`, `results.jsonl`,
`scores.json`, `server.log` (timing lines dropped), `state.log`, `pelican.py`, `pelican_chain.sh`, `serve_pelican.sh`,
`score_beam.py`.
