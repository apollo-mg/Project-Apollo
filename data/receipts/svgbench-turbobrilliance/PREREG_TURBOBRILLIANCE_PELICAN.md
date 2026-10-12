# Pre-registration — DavidAU's Turbo-Brilliance modes on the pelican, at 27B, template isolated on stock weights

**Logged 2026-10-12 00:15 EDT, before any generation.** The only runs so far are the render-only gate below
(`render_check.py`, no tokens generated).

**Prior art checked:** `ledger_precheck.py "DavidAU turbo brilliance template modes pelican"` -> receipts found:
- `davidau-templates/RESULT_LFM25_MODES.md` and `RESULT_LFM25_SYSPROMPTS.md` (09-28): the same Turbo-Brilliance
  system on LFM2.5-2.6B bought no accuracy and cost calibration on factual CAL items (default `high` refused 7/24
  invented questions vs 20/24 with no system prompt; only `omni` held, at 4x tokens).
- `svgbench-pelican3/RESULT_PELICAN3.md` and `svgbench-davidau/RESULT_TOKENS.md`: Twin-Turbo **weights** on the
  pelican, token counts only.
- **What this adds:** the first Turbo-Brilliance test at 27B (the card says the system "scales up with
  parameters"); the template isolated on matched stock weights, with byte-identity of the untagged render proven;
  a creative-code task instead of factual calibration; and blind human preference as the primary outcome, which is
  the "UX, hard to benchmark" case for the system.

## The question

DavidAU's card for `Qwen3.8-27B-Turbo-Brilliance-50X-Reasoning-Instruct-NEO-MAX-MTP-GGUF` says the system "vastly
augments the models core performance", that "one shot/two shot 'Brilliance' is the standard", and that it saves
tokens. The card has no benchmarks. The system is a chat template: typing `{REASON:mode}` injects a persona or
method prompt as a system message.

On "Generate an SVG of a pelican riding a bicycle", with the weights held fixed, does typing a mode tag produce
drawings people prefer, and what does it cost in tokens and time?

## The template, pinned

- **Source:** `DavidAU/Qwen3.8-27B-Turbo-Brilliance-50X-Reasoning-Instruct-NEO-MAX-MTP-GGUF` @ `cbb40c02`.
- **Read from the GGUF header** (`tokenizer.chat_template`) of the IQ3_M and the Q6_K files at that commit: both
  226,718 bytes, sha256 `e5b216667a07964c3855d43fa0a7fa22bc4894c0a3182851c2ec6a04141572fb`, identical to each
  other and to the Hub API's copy. Stored as `templates/turbo_brilliance_cbb40c02.jinja`. **Used exactly as shipped.**
- **A gate inside the template:** modes apply only while `l_car == '8'`. Branches lower it to "7" or "5" if the
  help block is missing or lacks the `.co/DavidAU` link, and then the tag is still stripped from the user turn. An
  edited template would turn every mode arm into the control with no error. Hence G1.

## Render gate (done before this prereg; `render_check/summary.json`)

The server's own `/apply-template` (buun `38ada0e1b`, `build_rocm`, run_ladder flags, `--reasoning-effort medium`):

| gate | result |
|---|---|
| G1: each tagged render contains a 160-char slice from the middle of its mode block, the task text, and no `{REASON:` | **pass**, all four modes |
| G2: the untagged render under DavidAU's template is byte-identical to the stock template's | **pass** |
| G3: the stock untagged render equals `svgbench-pelican3/prompt_BASE_r1.txt` | **pass** |

Rendered system blocks: `coder` 10,594 chars, `quinn` 10,143, `omni` 4,504 (`ultra` 1,733, not an arm). The tag
overrides the server's `--reasoning-effort medium`; untagged, `medium` injects nothing, under either template.

## Arms

All arms: the same weights, the same server flags, DavidAU's template via `--chat-template-file`.

| arm | user turn | why this mode |
|---|---|---|
| CTRL | `Generate an SVG of a pelican riding a bicycle.` | untagged; renders byte-identical to the stock model (G2) |
| CODER | `{REASON:coder} ` + the task | card flowchart: "Code / software / systems? -> coder" (an SVG is code) |
| QUINN | `{REASON:quinn} ` + the task | card flowchart: "Creative art / perform life? -> quinn"; card: "art direction" |
| OMNI | `{REASON:omni} ` + the task | the one mode that held calibration on the 2.6B (continuity arm) |

Chosen from the card's own routing before any generation. `ultra` ("perfect final answer, no iteration") was the
other candidate and is not run.

## Held identical to `svgbench-pelican3`

- **Weights:** `Qwen3.8-27B.i1-IQ3_M.gguf`, `mradermacher/Qwen3.8-27B-i1-GGUF` @ `9eb2d6db`, 12,768,331,744 bytes,
  sha256 `7544860b…0f3cd40` (`/mnt/TG_2TB/AI/Models/pelican3/manifest.txt`).
- **Server flags:** `-c 24576 -n 20000 -np 1 -fa on --kv-unified -ctk q8_0 -ctv q8_0 --reasoning-effort medium
  --min-p 0 --jinja` (+ `--chat-template-file` here).
- **Sampling:** temperature 1.0; other samplers at server defaults.
- **Card:** RX 9070 XT. **Scorer:** `svg_probe.py`, unchanged. **Memory safeguards:** preflight, watchdog, cooldown.
- **Procedure:** first drawing only, fresh server per rep (this also satisfies the card's "new chat for each mode /
  no caching" advice). Generation capped at 480 s; 585 s wall-clock backstop.
- **Harness:** `tools/svgbench/run_tb_p1.py` via `tb_rep.sh`, one rep per foreground call.

**Not held identical:** the binary is buun `38ada0e1b`, not pelican3's `3823c9eb6`. pelican3's BASE reps are
quoted for orientation only and never pooled.

## Design

5 reps per arm, fresh server each, rotated:

| rep | order |
|---|---|
| 1 | CTRL, CODER, QUINN, OMNI |
| 2 | CODER, QUINN, OMNI, CTRL |
| 3 | QUINN, OMNI, CTRL, CODER |
| 4 | OMNI, CTRL, CODER, QUINN |
| 5 | CTRL, CODER, QUINN, OMNI |

**Recorded per drawing:** completion and prompt tokens, reasoning chars, answer chars, structural score, SVG and
render, elapsed time, rendered-prompt sha256 and `kv_bpv`.

## Rules, fixed before any generation

- **R1, capped rep.** A rep that hits the 480 s cap, or the backstop once generation started, is a runaway:
  recorded, not rerun. In token comparisons it ranks above every completed rep (capped reps tie with each other). It
  is excluded from thinking-length and structural comparisons. For the panel, see "Missing drawings".
- **R2, parser miss** (as pelican3). If `reasoning_content` is empty but `content` contains `</think>`, thinking
  chars are the text before the last `</think>`, and the scored SVG is the last `<svg…</svg>` after it, re-probed.
- **R3, no generation.** A rep whose server never became ready is rerun. A rep the memory watchdog killed mid-
  generation is rerun once and logged as an incident.
- **R4, prompt integrity.** The runner renders each rep's tagged request with `/apply-template` before generating
  and refuses the rep unless its sha256 equals the arm's render-gate sha256. A refused rep is investigated, then rerun.
- **R5, KV integrity.** `kv_bpv` reads 8.5 (q8_0) in every rep, or the rep is invalid and rerun.

## Primary outcome: blind pairwise preference

**Pairs, fixed by design:** MODE_rk vs CTRL_rk for each mode and k = 1..5: **15 pairs**. Each CTRL drawing appears
in three pairs, once per mode.

**Page:** renders only (composited on white, re-encoded, no metadata), random codes, pair order and left/right
sides drawn once from the OS RNG. The code-to-drawing mapping is sealed: its sha256 is committed in an addendum to
this file **before the page is shared with anyone**, and the mapping stays out of git until rating is done.

**Questions per pair:**
1. "Which is the better picture of a pelican riding a bicycle?" — left / right / can't decide.
2. "One of these was made with a long persona prompt. Which one?" — left / right / no idea.

**Leak pre-check, before building the page:** count per arm the SVGs containing `<text>`, emoji, or a caption or
signature. Drawings are shown as drawn, never edited. The counts are reported, and question 2 measures the leak.

**Missing drawings.** If one side of a pair has no drawing (runaway, or no SVG in the answer), the pair is not shown
and counts as a win for the side that has a drawing, for every rater: a user who waited and got nothing has had the
worse experience. Both sides missing: the pair is excluded. A drawing that exists but renders blank is shown.

**Scoring:**
- **Per rater:** wins for the mode side over decisive pairs ("can't decide" excluded).
- **Pooled:** each pair's mode-side win rate is averaged over eligible raters (can't decide = 0.5), as in
  `svgbench-blind`. A pair counts for the mode if that average is > 0.5 and for CTRL if < 0.5; exactly 0.5 is
  excluded.
- **Registered test (H-1):** exact two-sided sign test over the 15 pooled pairs, alpha 0.05.
- **Per mode:** descriptive only. Five pairs cannot reach p < 0.05 on a two-sided sign test (minimum 0.0625).
- **Raters:** Mark first. Outside raters through the share page; an outside rating is pooled only if the rater
  confirms they rated without AI assistance. Handles as they choose; names only with consent.

## Secondary outcomes: cost

- **Completion tokens, per mode vs CTRL:** exact two-sided Mann-Whitney, 5 v 5, alpha 0.05 (minimum p 0.0079).
  Capped reps per R1.
- **Elapsed time, reasoning chars, answer chars, prompt tokens:** descriptive.
- **Structural score:** descriptive (it saturates near 10/10).

## Predictions

| id | prediction | conf |
|---|---|---|
| H-1 | The pooled 15-pair sign test does NOT find a preference either way (p >= 0.05) | 60% |
| H-2 | Mark's own decisive picks favour the mode side in at most 9 of 15 pairs | 60% |
| H-3 | Mark's persona guesses are right on more than half of his decisive guesses (a visible style tell exists) | 55% |
| H-4 | OMNI uses more completion tokens than CTRL (Mann-Whitney p < 0.05) | 60% |
| H-5 | CODER uses more completion tokens than CTRL (p < 0.05) | 50% |
| H-6 | QUINN uses more completion tokens than CTRL (p < 0.05) | 40% |
| H-7 | No CTRL rep hits the cap | 85% |
| H-8 | At least one mode rep hits the cap | 35% |
| H-9 | All 20 drawings score 10/10, or fail only on the artifact types in `svgbench-ladder/RUN_NOTES.md` | 45% |

**Why H-4 to H-6 lean "more":** on the 2.6B, `omni` cost 4x tokens and `einstein` 12.6x; the 27B blocks for
`coder` and `quinn` are 10k-char personas that ask for thoroughness. Against that, Twin-Turbo (a different
mechanism, in the weights) thought less. **Why H-1 leans null:** the 2.6B modes bought no accuracy, and earlier
blind art panels found raters agreeing on only 58-66% of decisive pairs, so a small effect would not show at n=15.

## Limitations, declared

- **Quant.** IQ3_M, not the "MAX"/BF16 the card says works best ("Higher quant -> Better performance"). Chosen for
  continuity with pelican3 and because it fits the 9070 XT. A null here does not speak for Q6_K or BF16.
- **Sampling.** The harness's (temperature 1.0, min-p 0), not the card's (temp 0.5-1, top-k 64, min-p 0.05,
  top-p 0.95). Held identical across arms, so the tag is still the only difference.
- **This tests the template system, not DavidAU's NEO-imatrix quant files.** The card calls the weights stock
  Qwen3.8-27B; that is card-reported only (the imatrix file is named after the Turbo-Brilliance model). The
  transplant onto mradermacher's stock quant makes the question moot for this test.
- **CTRL is `medium`, which injects no system text.** The Qwen default when no effort is set (`xhigh`, a 207-char
  prompt) is not an arm.
- **n = 5 per arm, one prompt.** The panel is small; per-mode preference is descriptive.

## Deviation 1 (2026-10-12 00:40 EDT, after rep 1 of all four arms, before rep 2): the client streams, so reasoning text is kept

**What changed.** `run_tb_p1.py` now sends the same request with `"stream": true` (plus
`stream_options.include_usage`) and assembles the reply itself. The server, its flags, the template, the sampling
and the 480 s cap (now an overall deadline from the request start) are unchanged; the returned record has the same
fields. New files per rep: `<ARM>_r<k>_p1.reasoning.txt`; a capped rep instead leaves
`.partial_reasoning.txt` / `.partial_content.txt` and a `"step": "partial"` record (chunk count, chars).

**Why.** Mark asked to compare the reasoning between modes. The harness kept only `reasoning_chars`, and a capped rep
kept nothing, because a non-streamed reply never arrives. Reasoning text is a new descriptive outcome; no registered
outcome or rule changes.

**What was seen before the change:** rep 1's summary lines only (CTRL 5,022 tokens 10/10; CODER 5,510 10/10;
QUINN 5,841 9/10; OMNI capped at 480 s). No drawing has been looked at, no panel exists.

**Consequence.** Rep 1 has no reasoning text for any arm (counts only). The reasoning comparison uses reps 2-5. A
capped rep's token count stays "capped" under R1 whatever the partial chunk count says. The first streamed rep is
checked for a non-null token count, a non-empty reasoning file and an SVG in the content before the run continues.
