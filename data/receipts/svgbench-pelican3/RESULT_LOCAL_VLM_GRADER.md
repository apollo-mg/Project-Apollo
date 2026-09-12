# Result — a local vision grader we fully control, and what it agrees with

**2026-09-11.** Built because a vendor web chat cannot be specified in a receipt: the served
checkpoint, system prompt and personalisation are all unknowable, and the temporary-chat notice
promises only that the conversation is not stored or trained on. Tool: `tools/vlm_grade.py`,
rubric `tools/vlm_rubrics/pelican_capability.txt`. Raw run in `vlm_local/`.

## The instrument

| | |
|---|---|
| model | `Qwen3.8-27B-UD-IQ3_XXS.gguf`, sha256 in `vlm_local/manifest.json` |
| vision tower | `mmproj-F16.gguf` (unsloth), 0.93 GB |
| binary | `buun-aad85/build_rocm/bin/llama-server` @ `aad850104` |
| flags | `-ngl 99 -c 8192 -np 1 -fa on --kv-unified -ctk q8_0 -ctv q8_0` |
| thinking | **off**, via `--chat-template-kwargs '{"enable_thinking":false}'` |
| sampling | temperature 0 |
| card | RX 9070 XT at 330 W, peak 13,933 MiB of 16,304 |

Everything above is recorded in `manifest.json` with file hashes, so the run is restatable by
someone who has the same two files.

**Three findings while building it, each a trap avoided:**
- **`/health` returns 200 before the model is loaded** — it answered in 4 s with 1.7 GB of VRAM
  resident. The readiness probe is now a real completion request. (`readiness-probes-lie` again.)
- **`--reasoning-budget 0` does not stop this template thinking.** It kept emitting
  `reasoning_content` and spending the whole token budget on it. `enable_thinking:false` via
  `--chat-template-kwargs` does work: the rendered prompt ends `<think>\n\n</think>\n\n`, and all 45
  grades came back with `reasoning_chars = 0`.
- **The preprocessor letterboxes non-square images**, and the model described the padding
  ("framed by black bars") as if it were content. The tool now pads to square on white.

**Positive controls gate every run.** Synthetic red circle, blue square and blank white are graded
first and the run aborts unless all three are described correctly. A vision model that ignored the
image would otherwise return plausible scores from the prompt alone.

**Blind by construction.** The model never receives a filename, arm name or prior score; images are
keyed by opaque codes and the mapping is written to a separate file. This is the direct lesson of
`RESULT_VLM_LABEL_LEAK.md`.

## Self-consistency: exact

15 drawings × 3 repeats = 45 grades, 0 errors. **Every image scored identically on all three
repeats** — mean spread 0.00, 15/15 identical. Consistent with `agent-benchmark-determinism`:
temperature 0 at `-np 1` is deterministic.

Cost: **median 1.0 s per grade, 0.9 minutes total**, 26 tokens each. Free and repeatable.

## Scores

| drawing | local VLM | Gemini blind | structural probe |
|---|---|---|---|
| BASE r1 | 6 | 6 | 9 |
| BASE r2 | 6 | 6 | 10 |
| BASE r3 | 7 | 5 | 9 |
| BASE r4 | 8 | 5 | 10 |
| BASE r5 | 6 | 5 | 10 |
| DAVIDAU r1 | 4 | 4 | 9 |
| DAVIDAU r2 | 8 | 4 | 10 |
| DAVIDAU r3 | 7 | 7 | 10 |
| DAVIDAU r4 | 7 | 6 | 10 |
| DAVIDAU r5 | 6 | 3 | 10 |
| QWOPUS r1 | 6 | 3 | 6 |
| QWOPUS r2 | 4 | 5 | 10 |
| QWOPUS r3 | 6 | 4 | 10 |
| QWOPUS r4 | 7 | 7 | 9 |
| QWOPUS r5 | 7 | 4 | 10 |

**Per arm:**

| instrument | ordering |
|---|---|
| local VLM | BASE 6.60 > DAVIDAU 6.40 > QWOPUS 6.00 |
| Gemini blind | BASE 5.40 > DAVIDAU 4.80 > QWOPUS 4.60 |
| structural probe | DAVIDAU 9.80 > BASE 9.60 > QWOPUS 9.00 |
| Gemini **labeled** | DAVIDAU 6.0 > BASE 5.5 > QWOPUS 4.8 |

**Both blind vision instruments give the same ordering, and it is not the ordering the labeled run
produced.** That is further evidence for the label leak, since the labeled ranking matches the
printed structural scores instead.

**This does not establish which model draws better pelicans.** Five drawings per arm, arm means
within 0.6 of each other, no significance test, and the ordering match between two instruments is
1-in-6 by chance alone.

## Agreement between instruments

Spearman over the 15 drawings:

| pair | rho |
|---|---|
| local VLM vs Gemini blind | **+0.24** |
| local VLM vs structural probe | +0.20 |
| Gemini blind vs structural probe | +0.04 |

**Calibration:** in the blind art panel the three *human* raters agreed with each other at
+0.26, +0.34 and +0.26 (`RESULT_BLIND_ART.md`). So two vision models agree with each other about as
much as two people did — modest, and at n = 15 not distinguishable from zero (about 0.51 is needed
for p < 0.05). The honest reading is that these instruments are correlated weakly and measure
overlapping but different things, exactly as the human raters did.

**A concrete convergence:** DAVIDAU r1 scores 4 on both vision instruments and 9 on the structural
probe. QWOPUS r1 scores 6 on the local model and on the probe, but 3 from Gemini. The vision models
and the probe disagree about specific drawings in both directions.

## Limits

- **The reasons are formulaic.** Only 12 distinct reason strings across 45 grades; one
  ("*Pelican anatomy and bicycle frame mostly correct; minor geometry issues.*") covers 12. The
  score discriminates; the justification is close to boilerplate and should not be quoted as
  analysis.
- **3-bit quant.** Graded at `UD-IQ3_XXS`. Whether a higher-precision quant scores differently is
  untested, and is a natural next control given that this whole campaign is about quantisation.
- **One rubric, one prompt wording.** `RESULT_COMPLEXITY_CONFOUND.md` shows rubric wording moves
  results; this is one wording.
- **Not pre-registered.** Exploratory validation of a new instrument, not a test of a hypothesis.
- **Gemini side is a single run**, against three local repeats.

## Reusable beyond this campaign

`vlm_grade.py` takes any image set and any rubric file. It is not pelican-specific: the rubric is a
committed text file, the controls are synthetic, and the manifest pins whatever model is used.
