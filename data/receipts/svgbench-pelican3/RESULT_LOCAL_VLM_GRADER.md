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

## Addendum — quantising the judge changes the verdict

**2026-09-11.** The same rubric, the same 15 drawings, the same tool, at two grader precisions.
`vlm_q6k_73/` grades on `.73`'s Q6_K daily driver via `--base-url`; thinking was forced off with a
**per-request** `chat_template_kwargs` override (that server's own default is
`reasoning_effort=medium`), verified by `reasoning_chars = 0` on all 45 grades.

**Q6_K is also perfectly self-consistent** — 15/15 identical across three repeats — despite running
through MTP speculation, VBR KV and a tensor split. Temperature 0 determinism survives all three.

| instrument | ordering |
|---|---|
| grader **Q6_K** | DAVIDAU 7.40 > BASE 7.00 > QWOPUS 6.80 |
| grader **IQ3_XXS** | BASE 6.60 > DAVIDAU 6.40 > QWOPUS 6.00 |

**The top two swap between precisions of the same grader.** Agreement between them is Spearman
**+0.67** — not 1.0, on identical inputs with a deterministic decoder. The difference is the
quantisation of the judge and nothing else.

**The low-bit grader is systematically harsher:** Q6_K mean 7.07 vs IQ3_XXS 6.33, and 12 of 15
drawings scored higher at Q6_K. Mean absolute movement 1.13 points.

### The decisive case: BASE r3

Only one drawing in this set has a defect verified from source rather than from a score.
`RESULT_PELICAN3.md` establishes that **BASE r3's neck is an unoutlined white stroke on a
transparent (white-rendering) canvas** — the head visibly floats, and this was confirmed by reading
the SVG, not by trusting the probe.

| instrument | BASE r3 |
|---|---|
| structural probe | 9/10 |
| grader IQ3_XXS | 7 |
| Gemini blind | 5 |
| **grader Q6_K** | **4** — the lowest, and it moved −3 from IQ3_XXS |

On the one drawing where we know the answer independently, **the higher-precision grader is the
one that caught it.** This is the strongest available evidence that Q6_K is a better instrument
here and not merely a different one.

**The counter-example, stated honestly:** DAVIDAU r1 moved the other way, 4 → 7, and there IQ3_XXS
agrees with Gemini (4) while Q6_K does not. One case each way; the BASE r3 case is the one with
independent ground truth.

**Q6_K also agrees marginally better with the other instruments:** vs Gemini +0.30 (IQ3_XXS +0.24),
vs the structural probe +0.31 (IQ3_XXS +0.20). Both differences are small at n = 15.

### Consequence

**Grade at Q6_K.** `.73` already serves it with the mmproj loaded, so the better instrument is also
the one that needs no new download — point `vlm_grade.py` at it with `--base-url` and the
per-request thinking override.

And the self-referential point this campaign keeps producing: **quantisation costs the judge as well
as the artist.** A 3-bit grader missed the only verified defect in the set. Any future use of a
local VLM as a scorer should state its quant in the receipt, exactly as we state the subject's.
