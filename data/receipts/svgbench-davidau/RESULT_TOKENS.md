# Result — DavidAU's Twin-Turbo thinks about a quarter as much as stock on the pelican, but its answers run longer, so total tokens fall only about a third

**Date:** 2026-09-11.
- **Prereg:** `PREREG_TOKENS.md`, commit `d5a211b` at 15:07:43, before any generation. The first
  drawing completed at 15:09:52.
- **Data:** `results.jsonl`, `run.log`, `memtrace.csv`, server logs, and per-drawing
  `*.svg/.png/.grid.txt/.content.txt`.
- **Harness:** `tools/svgbench/run_single_p1.py`, which calls run_ladder's functions unchanged.

**Setup.**
- **Model:** `…TTURBO-Fable-C-Fusion-709-…-NEO-MTP-IQ3_M.gguf`, sha256 verified against Hugging Face.
- **Settings:** the ladder's, at reasoning effort **medium**. Both templates inject nothing there.
- **Where:** the 9070 at 330 W, binary `3823c9eb6`, q8_0 KV set explicitly.

## Pre-registered verdicts (total completion tokens)

| id | prediction | conf | verdict |
|---|---|---|---|
| P-D1 | median at most 2,235 tokens (half of stock) | 35% | **FALSIFIED** — 3,072 |
| P-D2 | fewer tokens than stock; exact one-sided Mann-Whitney, α 0.05 | 60% | **FALSIFIED** — U = 23/30, p = 0.108 (lower, but not significantly) |
| P-D3 | all 3 first drawings structurally sound | 65% | **CONFIRMED** — 10/10, 10/10, 10/10 |

| | DAVIDAU (n = 3) | STOCK ladder (n = 10) |
|---|---|---|
| completion tokens | 3,072 / 2,389 / 4,172 (median **3,072**) | median **4,470** (2,639–10,503) |
| structural score | 10, 10, 10 | 10 ×7, 9 ×2, 6 ×1 |

All but one of stock's below-10 scores were scorer artifacts; IQ4_XS r2 was the real failure.

## Descriptive — where the tokens go (NOT pre-registered)

The card's claim is about *thinking* tokens, but the prereg tested *total* tokens. Splitting the
output:

| per first drawing | DAVIDAU median | STOCK median | ratio |
|---|---|---|---|
| thinking (`reasoning_content`), characters | **1,229** (1,229 / 1,220 / 2,545) | **5,582** (2,506–15,065) | **0.22** |
| answer (`content`), characters | **5,650** (5,650 / 3,990 / 6,658) | **3,996** (2,972–7,908) | **1.41** |
| thinking as a share of output characters | 0.23 | 0.55 | |

**Thinking.** Two of the three DAVIDAU values fall below all ten stock values, and the third below
eight: U = 28/30, one-sided p = 0.014. This test was not registered, and it counts characters, not
tokens.

**So:** on this task the model thinks about a quarter as much, within the card's "1/5 to 1/2" range.
But it writes answers about 40% longer (more detailed SVGs), so total output falls only by about a
third.

## What this says about the card's claim

- **Plausible for thinking tokens, at medium, on this task** (descriptively). The template's medium
  injects nothing, as stock's does, so this comes from the weights.
- **Not a cost claim.** The longer answers took back more than half the thinking saving here.
- **Drawing quality held:** 3 of 3 first drawings were structurally sound.

## The first attempt was killed by the system monitor

- **What happened:** the harness's low-memory monitor stopped the first run while rep 2's model was
  loading. It also stopped an unrelated background watcher.
- **No damage:** no desktop app was killed, and no server was orphaned. Rep 1's record was already
  saved.
- **The rerun:** the remaining two reps ran in the foreground with a 1 s memory trace
  (`memtrace.csv`).
  - Available memory never went below **21.1 GB**.
  - Shared GPU memory (GTT) peaked at **0.17 GB**, so there was no spill.
  - VRAM peaked at **14.14 GB**.
- **Conclusion:** the model fits and the run does not stress RAM. What tripped the monitor is not
  identified; a browser tab was closed between the two attempts.

## Caveats

- **Sample:** 3 drawings, one prompt, one mode (medium).
- **Historical control:** stock ran the day before on the same box, binary and settings, not
  concurrently.
- **Declared differences:** a different packager (DavidAU's NEO imatrix vs unsloth UD) and quant level
  (IQ3_M vs the ladder's 2-bit and 4-bit).
- **Units:** thinking is measured in characters, because the server does not report reasoning tokens
  separately.
