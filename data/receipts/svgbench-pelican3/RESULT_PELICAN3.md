# Result — pelican three-way: base Qwen3.8-27B vs Qwopus3.8-27B-Flash vs DavidAU Twin-Turbo, matched IQ3_M

**Run 2026-09-11, 17:07–17:59, RX 9070 XT at 330 W.** Graded by the scorer committed before any
data (`tools/svgbench/score_pelican3.py`, `e129413`) against `PREREG_PELICAN3.md` (`5fbc2be`,
17:01). Raw output is in `score_output.txt`. The drawings are in `contact_sheet.png`; rows are BASE,
QWOPUS, DAVIDAU.

## Headline

- **DavidAU's Twin-Turbo thinks about a third as much as the matched base, but total tokens barely
  move.**
  - Median reasoning 1,387 vs 3,949 chars (0.35×, exact p = 0.024, 5 v 5).
  - Its answers run 1.23× longer, so total tokens are 3,927 vs 4,440 (0.88×, p = 0.155).
  - This replicates the earlier result (`svgbench-davidau/RESULT_TOKENS.md`), now against a base
    quantized the same way.
- **Qwopus3.8-27B-Flash, as packaged in mradermacher's i1 GGUF, skipped thinking in 2 of 5 reps.**
  - The rendered prompt never opens `<think>`. The template is copied from Jackrong's safetensors
    repo (`f2e03cfdf930`).
  - Jackrong's own GGUF ships the stock Qwen3.8 template (`c3cf9e34abf4`, identical to base's),
    which opens thinking every time.
  - So this is a finding about **this packaging on this prompt**, not about Jackrong's GGUF release.
- **One real structural failure in 15 drawings** (BASE r3). The four other non-ceiling scores are
  scorer artifacts, three of them from scenery near the subject.

## Per drawing

| arm | rep | tokens | thinking chars | answer chars | score | elapsed |
|---|---|---|---|---|---|---|
| BASE | 1 | 4,440 | 3,903 | 5,628 | 9/10 · artifact | 163 s |
| BASE | 2 | 5,100 | 6,926 | 3,850 | 10/10 | 187 s |
| BASE | 3 | 3,197 | 3,949 | 3,422 | 9/10 · **real** | 116 s |
| BASE | 4 | 5,556 | 6,335 | 5,632 | 10/10 | 204 s |
| BASE | 5 | 3,923 | 3,949 | 4,736 | 10/10 | 143 s |
| QWOPUS | 1 | 4,190 | **none** | 9,032 | 6/10 · artifact | 155 s |
| QWOPUS | 2 | 8,310 | 9,636 | 8,447 | 10/10 | 308 s |
| QWOPUS | 3 | 3,251 | **none** | 6,477 | 10/10 | 118 s |
| QWOPUS | 4 | 3,267 | 294 | 6,531 | 9/10 · artifact | 118 s |
| QWOPUS | 5 | 12,201 | 18,857 | 6,728 | 10/10 | 456 s |
| DAVIDAU | 1 | 3,709 | 1,240 | 7,155 | 9/10 · artifact | 135 s |
| DAVIDAU | 2 | 4,216 | 1,387 | 7,447 | 10/10 | 154 s |
| DAVIDAU | 3 | 4,240 | 5,026 | 3,650 | 10/10 | 154 s |
| DAVIDAU | 4 | 3,927 | 2,791 | 5,821 | 10/10 | 143 s |
| DAVIDAU | 5 | 1,386 | 206 | 2,709 | 10/10 | 50 s |

**Medians [range]:**

| arm | tokens | thinking chars | answer chars |
|---|---|---|---|
| BASE | 4,440 [3,197–5,556] | 3,949 [3,903–6,926] | 4,736 [3,422–5,632] |
| QWOPUS | 4,190 [3,251–12,201] | 9,636 [294–18,857], thinking reps only (n = 3) | 6,728 [6,477–9,032] |
| DAVIDAU | 3,927 [1,386–4,240] | 1,387 [206–5,026] | 5,821 [2,709–7,447] |

- **BASE thought in every rep, and stably:** 3.9k–6.9k chars.
- **QWOPUS is the least predictable arm.** Two reps went straight to the SVG, one thought for 294
  chars, and one produced the longest output of the whole run: 12,201 tokens in 456 s.
- **QWOPUS writes the longest answers** (1.42× BASE), so even its reps without thinking cost 3.3k–4.2k
  tokens.

## Predictions

| id | prediction | conf | result |
|---|---|---|---|
| P-P1 | DAVIDAU thinks less than BASE (Mann-Whitney 5 v 5) | 80% | **CONFIRMED** — U = 3, p = 0.024 |
| P-P2 | DAVIDAU uses fewer tokens than BASE | 45% | **FALSIFIED** — U = 7, p = 0.155 |
| P-P3 | QWOPUS median tokens ≥ BASE median | 55% | **FALSIFIED** — 4,190 vs 4,440 |
| P-P4 | QWOPUS opens thinking in all 5 reps | 85% | **FALSIFIED** — 3 of 5 (r1 and r3 did not) |
| P-P5 | No rep hits the 480 s cap | 85% | **CONFIRMED**, narrowly — max 455.7 s (QWOPUS r5) |
| P-P6 | All 15 drawings structurally sound, or failing only on known artifact types | 50% | **FALSIFIED** — BASE r3 is real |

**P-P3 caveat:** the QWOPUS arm mixes reps with and without thinking. The card's median claim
concerns the model's own evaluation setup, which this packaging does not reproduce.

## The non-ceiling drawings (rule from `svgbench-ladder/RUN_NOTES.md`)

**Method.** The flagged fragments were located by re-running the unchanged probe's segmentation
(`_ink`, `_components`) on the saved renders and taking each fragment's bounding box.

| drawing | failing | flagged fragment | verdict |
|---|---|---|---|
| BASE r3 | `assembly_coherent` | head + beak, 180 cells (x 232–364, y 72–116) | **REAL** — see below |
| BASE r1 | `assembly_coherent` | right cloud, 137 cells (x 256–352, y 20–52), just above the head | artifact |
| DAVIDAU r1 | `assembly_coherent` | sun merged with a cloud, 268 cells (x 352–476, y 16–80) | artifact |
| QWOPUS r4 | `assembly_coherent` | sun with a bird stroke, 226 cells (x 380–464, y 32–96), beside the beak | artifact |
| QWOPUS r1 | wheel checks ×3 + `assembly_coherent` | full-width ground lines, 403 cells (x 16–504, y 300–348) | artifact |

- **BASE r3 is real: the neck is invisible.** It is
  `<path … stroke="#ffffff" stroke-width="18">` with no outline, on a transparent canvas that renders
  white. The head visibly floats: the IQ4_XS r2 pattern from the ladder.
- **QWOPUS r1's ground lines do double duty.** Together with a grey shadow ellipse they make the lower
  band one continuous run, which fails all three wheel checks (the IQ2_M r2 type). The same lines are
  the near fragment. The bird and bike are one component.
- **A new artifact type: scenery near the subject.** BASE r1, DAVIDAU r1 and QWOPUS r4 fail
  `assembly_coherent` because a cloud or the sun lies within `FRAG_MARGIN` of the subject and exceeds
  `FRAG_MIN` of its size.
  - The probe's own comment assumes *"the sun and clouds are far"*.
  - This type is not in `RUN_NOTES.md`; it is recorded here for svgbench v2.
- **Correction.** Before locating the fragments I guessed, in chat, that QWOPUS r4 failed on its pale
  neck and QWOPUS r1 on a near-white body. Both guesses were wrong.
  - QWOPUS r4's `#ECF0F1` neck is attached; the head is in the main component.
  - QWOPUS r1's bird is whole.

**Scores are near ceiling again:** 10/15 at 10/10. Structural scoring does not separate these three
arms, and taste was not assessed.

## Integrity

- **R4, prompts:** each arm rendered one prompt hash across all 5 reps, from the server's own
  `/apply-template`. BASE and DAVIDAU both `0e0d9d80ec69`, ending `assistant\n<think>\n`; QWOPUS
  `89e9dbb0dee8`, ending `assistant\n`.
- **R5, KV:** `kv_bpv` 8.5 (q8_0) in all 15 reps.
- **R3:** no server failures and no watchdog trips.
- **R2's parser-miss path never fired.** Every QWOPUS rep either thought and had its thinking parsed
  into `reasoning_content`, or never opened a think block at all (no tags anywhere in `content`).
- **R1, the declared cap, never bound.** The closest rep was 24 s short.
- **Memory:**
  - Peak VRAM 14,412–14,875 MiB of 16,304, GTT ≤ 196 MiB, minimum MemAvailable 21.8 GB
    (`memtrace.csv`).
  - At 17:06, before rep 1, the tool harness killed two background tasks on "low memory" (a hash
    check and a .194 watcher) with 20 GB available. The runs were unaffected: every rep ran in the
    foreground.

## Replication: the three earlier DAVIDAU reps (not pooled)

| | tokens | thinking chars |
|---|---|---|
| earlier (`RESULT_TOKENS.md`) | 3,072 / 2,389 / 4,172 | 1,229 / 1,220 / 2,545 |
| this run | 3,709 / 4,216 / 4,240 / 3,927 / 1,386 | 1,240 / 1,387 / 5,026 / 2,791 / 206 |

These are consistent: short thinking, and total tokens in the same band.

## A decision recorded

After QWOPUS r1 skipped thinking, I considered adding an arm: the same Qwopus file under the stock
template. It was not added.
- **The shipped-template result is the finding.**
- **A post-hoc fifth arm would blur it.**
- **The decisive fact is already evidenced:** Jackrong's own GGUF template is the stock one.

All four templates are saved under `templates/` with their hashes.

## What this does not show

- **Nothing about Jackrong's own GGUF.** It opens thinking; its thinking length on this prompt is
  untested.
- **Nothing about other prompts, effort modes or benchmarks.**
- **No taste ranking.** The contact sheet goes to Mark unblinded.
- **Nothing about tails.** 5 draws per arm cannot test a P95 claim. QWOPUS's 12,201-token rep is one
  observation.
