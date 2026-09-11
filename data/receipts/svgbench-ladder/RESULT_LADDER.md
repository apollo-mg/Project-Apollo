# Result — the svgbench ladder could not measure its question; its bit-depth "confirmations" rest on scorer artifacts

**Date:** 2026-09-10. **Design:** `PREREG_BITDEPTH_FEEDBACK.md` (predictions and every protocol change
committed before the data they govern). **Annotations:** `RUN_NOTES.md`. **Data:** `results.jsonl`
(33 records) plus per-step SVG/PNG/grid/content files.
**Reproduce (all read-only):** `tools/svgbench/score_ladder.py` (pre-registered grading),
`sensitivity_ladder.py` (artifact sensitivity), `explore_ladder.py` (exploratory only).

> **Amended the same night, after review.** The first version (`337c7d0`) said both bit-depth
> confirmations reverse once the artifact reps are annotated. That holds under only one of the two
> ways of handling those reps. **Excluded** rather than counted as drawn, P-L3 stays CONFIRMED. The
> sensitivity section now shows both handlings. The P-L1 ceiling clause and the provenance of the run
> conditions were also added.

**Run:**
- **Model:** stock Qwen3.8-27B, unsloth UD quants.
- **Binary:** `engines/buun-llama-cpp` build 11804 @ `3823c9eb6`. The working tree differs only in
  `tests/test-backend-ops.cpp`, which is not part of llama-server.
- **Card:** gfx1201 at **330 W**. LACT's config reads `power_cap: 330.0` and was last written at 18:30:34,
  before the run; sysfs `power1_cap` also reads 330 W.
- **Server flags,** as passed by `run_ladder.py`:
  `-c 24576 -np 1 -fa on --kv-unified -ctk q8_0 -ctv q8_0 -n 20000 --reasoning-effort medium --min-p 0`,
  temperature 1.0 (no VBR, no turbo KV). The server logs confirm `n_ctx_slot = 24576` and `kv_unified`;
  they do not print KV types.
- **Reps:** UD-Q2_K_XL ×3, UD-IQ2_M ×3, UD-IQ4_XS ×3, UD-Q4_K_M ×1 partial — **10 reps, 22 corrections**
  (23 attempted; one lost to the OOM).
- **Generations:** all 32 that completed finished with `stop`. The longest used 13,660 of 20,000
  tokens.

## Headline

**The instrument could not measure what the experiment asked.** 7 of 10 first drawings hit the
10-check scorer's ceiling, so no correction could register a gain. Of the 3 that didn't, **2 were
non-ceiling only because of scorer artifacts.**

- **P-L2's confirmation comes entirely from those two reps.** It reverses whether they are counted as
  drawn or excluded.
- **P-L3's confirmation depends on an unregistered choice of how to handle them.** It reverses if they
  are counted as drawn and survives if they are excluded. Even then, the classes do not separate by
  rank: 8 of 16 cross-class pairs.
- **The single clean framing data point went against the prediction.**

What the run does show cleanly: **2-bit drew as soundly as 4-bit**, **no correction ever returned its
input unchanged**, and **models diagnosed semantic faults the scorer cannot see — and fixed three.**

## Pre-registered verdicts, exactly as computed (`score_ladder.py`)

| | prediction | conf | verdict |
|---|---|---|---|
| P-L1 | framing effect > 0 over non-ceiling reps | 60% | **FALSIFIED as computed** — n=3 (effects 0, 0, −1), mean −0.33. **NOT EVALUABLE under the proportional ceiling reading** (below) |
| P-L2 | mean first-draw score Q2-class < Q4-class | 60% | **CONFIRMED** — 9.17 vs 9.75 |
| P-L3 | median tokens-to-converge Q2 > Q4 | 55% | **CONFIRMED** — 8,376 vs 4,778 *(rule not pre-specified: unconverged = +∞)* |
| P-L4 | error correction degrades faster than generation | 50% | **NOT EVALUABLE** — Q4 goal gain is zero |
| P-L5 | intent returns its input unchanged more often than goal | 65% | **FALSIFIED** — 0/10 vs 0/9 *(unchanged = extracted SVG text identical after trimming)* |

## How much of that the artifacts carry (`sensitivity_ladder.py`)

The rule: a failed check is **real** if the responsible element is invisible in the render (e.g.
drawn in the backdrop colour), so a viewer sees the fault the scorer reports; it is an **artifact** if
the element is visible and the scorer mis-segments it.

- **Q2_K_XL r2 — artifact:** the curved tips of a grass ellipse counted as ink.
- **IQ2_M r2 — artifact:** a ground-shadow ellipse merges the wheel profile; a white body on white
  isolates the wing; 4-connectivity breaks the thin neck.
- **IQ4_XS r2 — real:** a `#ffffff` neck on a white canvas. The head genuinely floats.

Neither handling of the artifact reps was pre-specified, so both are shown:

| | raw (6 v 4 reps) | counted as drawn (6 v 4) | excluded (4 v 4) |
|---|---|---|---|
| P-L2 mean first draw, Q2 vs Q4 | 9.17 vs 9.75 → CONFIRMED | **10.00 vs 9.75 → FALSIFIED** | **10.00 vs 9.75 → FALSIFIED** |
| P-L3 median tokens to converge | 8,376 vs 4,778 → CONFIRMED | **3,742 vs 4,778 → FALSIFIED** | 5,396 vs 4,778 → CONFIRMED |

- **P-L2 is an instrument artifact.** Every sound first drawing scored 10/10; the Q2 deficit is two
  mis-segmented drawings.
- **P-L3 is undecided by this data.**
  - Which way it falls depends on a choice nobody registered.
  - With the artifact reps excluded, a Q2 rep needs more tokens than a Q4 rep in exactly **8 of 16**
    cross-class pairs (descriptive; half means no separation).
  - The Q2 values span 2,940–10,503 tokens.
- **Convergence path makes no difference.** Letting a rep converge via `intent2` as well as the goal
  path changes neither median.

**When the calls were made.**
- The two artifact calls were committed at 20:51:55 (`5ebbec7`), before any rep-3 data existed.
- The real call and the written rule were committed at 21:06:05 (`8d73b91`), 32 s after rep 3's first
  drawing completed. That drawing (Q2_K_XL r3) scored 10/10, a ceiling rep that needed no call.
- Every rep-3 first drawing hit ceiling, so no call was made after that.

The calls are my judgement from renders. I made them with the running scores visible, and wrote the
rule down after the first two calls. The colour test behind them can be re-checked from the saved
SVGs.

## The ceiling rule — both readings

7 of 10 reps hit the ceiling. The literal pre-registered threshold ("≥ 8 of 12") is not met —
dropping Q4_K_M made 12 reps impossible. The same proportion (67%) applied to the 10 reps that ran
*is* met, and `eeecdb7` commits that when the threshold is met, P-L1 and P-L4 are reported NOT
EVALUABLE.

So P-L1 is FALSIFIED under the literal reading and NOT EVALUABLE under the proportional one. P-L4 is
NOT EVALUABLE under both. Either way, P-L1 rests on at most one clean rep.

## Clean findings

1. **2-bit drew as structurally soundly as 4-bit.** First drawings that were sound (ceiling, or
   failed only on artifacts): **Q2-class 6/6, Q4-class 3/4.** The only real structural failure among
   first drawings was a 4-bit one (IQ4_XS r2). At this resolution there is no evidence that 2-bit
   costs structural competence on this task.
2. **0 of 22 corrections returned their input unchanged** (extracted SVG text compared after trimming).
   This morning's byte-identical result (Qwen3.8-27B-GSQ-RCO IQ3_XXS, `svgbench-run/`) did not recur
   under a scaffold that asks for a fault list in both arms. That fits the correction recorded against
   that result: the fault-list request, not the reference clause, may be what drives revision. The
   model build also differs, though, so this does not settle it.
3. **Semantic fault-finding outran the scorer.** Working from a 64×30 text grid:
   - IQ4_XS r1 `intent2`: *"No wing/arm reaching to the handlebars… a rider should be gripping
     them."* It added a wing-arm gripping the bars.
   - IQ2_M r2 `goal3`: *"No wings/arms on the handlebars… so it doesn't read as 'riding.'"* It added a
     front wing reaching to the bars.
   - Q2_K_XL r2 `goal3`: *"Near leg dangles in mid-air – its foot hovers at (173, 201) with no pedal
     beneath it; only one pedal is drawn."* This was the final step, so no later step could repair it.
   - IQ4_XS r2 `intent2`: *"Neck has no outline… a floating white tube."* It outlined the neck in
     grey, and the drawing went from 3 components to 1.

   Only the last of these moved the score.
4. **The one clean framing data point: IQ4_XS r2 — intent +1, goal 0, effect −1.** Intent found the
   invisible neck. Neither goal step touched it: both kept the `#ffffff` neck and still failed
   assembly. goal2 led its fault list with the legs, goal3 with the beak. n = 1.

## Exploratory — NOT pre-registered

Paired render-change magnitude (`changed_of_union`), intent2 vs goal2 from the same parent drawing:
**goal changed more in 7 of 9 pairs**, mean paired difference **+0.125**, two-sided exact sign test
**p = 0.18**.

The measure was designated exploratory in the prereg at 19:25:57 (`eeecdb7`), when only the first
quant×rep cell had completed. The tool itself was committed at 19:41:30 (`2395ba0`), after two cells.
This is a direction, not a finding. It is the candidate primary metric for v2, where it would be
pre-registered.

## Instrument defects this run found

**Fixed before the clean restart** (`79d388d`), and validated with a backdrop-invariance set:
- The corner-median backdrop read sky-over-ground as 99.7% ink. The first live rep was quarantined in
  `invalid_bg_run/`.
- The assembly threshold drifted once shadows merged the ground line into the bike, and a detached
  head started passing. It is now a near-fragment test.
- `clusters_similar_width` penalised detail, a bias against the higher-bit quants. It was removed from
  scoring.

The second and third changes were made with specific drawings in view. That is disclosed in the
prereg as a researcher degree of freedom.

**Still open** (`tools/svgbench/V2_NOTES.md`):
- Backdrop shapes that don't touch the canvas edge count as ink.
- Backdrop-coloured fills isolate interior detail.
- 4-connectivity at 4× downsampling breaks thin diagonal strokes.
- Column-projection wheel detection merges the wheels with the frame, crank and shadows.

## Infrastructure

UD-Q4_K_M did not fit in VRAM at `-c 24576`, and its overflow went to pinned host memory, which
cannot be swapped. At 20:09:53 that triggered a global OOM with ~30 GB of swap free. The kernel
killed the server, Chrome, the desktop compositor (`kwin_wayland`), Discord, a node process and a
python3 process.

Q4_K_M was dropped after rep 1. Three safeguards were added: a memory preflight, a 2.5 GB watchdog,
and a post-stop GTT cooldown. **The watchdog never tripped afterwards** (`ladder.log`).

My first diagnosis was an HTTP timeout, which I believed defaulted to 600 s; the default is 3600 s.
That diagnosis was wrong, and it is retracted in the prereg.

## Caveats

- **Sample:** ten reps (three per quant, one partial for Q4_K_M), one prompt, one model family,
  temperature 1.0.
- **Judgement calls:** the real/artifact calls are mine, made from renders with the running scores
  visible.
- **Unregistered rules:** two scoring rules were not pre-specified. P-L3 counts unconverged reps as +∞.
  Convergence is measured along the goal path only, so IQ4_XS r2 reached 10/10 via `intent2` and still
  counts as unconverged; this second rule changes neither median.
- **Thin Q4 class:** Q4-class comparisons rest on IQ4_XS ×3 plus one partial Q4_K_M rep. Wall times
  are not compared, because Q4_K_M spilled to host memory.

## For the question that started this: is Q6 needed?

This run tested 2-bit against 4-bit, not Q6. On this task, at this scorer's resolution, the step from
2 to 4 bits bought nothing this design can detect.

- **First drawings:** 2-bit stock Qwen3.8-27B drew structurally complete pelicans on the first try as
  reliably as 4-bit.
- **Corrections:** no correction at either depth returned its input unchanged.
- **Cost to converge:** the one reading where 2-bit costs more is P-L3 with the artifact reps dropped —
  medians of 5,396 vs 4,778 tokens, +13%. That is about the "maybe 10% longer" Mark guessed going in.
  But with four reps a side, and the classes tied by rank (8 of 16 pairs), it is not evidence for that
  guess.

So the run offers no case for going higher. It also could not have detected a subtle difference,
because the instrument saturates. That is what v2 is for.
