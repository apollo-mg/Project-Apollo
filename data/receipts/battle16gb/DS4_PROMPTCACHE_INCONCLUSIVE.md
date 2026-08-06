# DS4 prompt cache: caching engages, but this test was underpowered for the question it asked

`.194`, 4× Tesla P100-PCIE-16GB (1063 MHz / 150 W), DS4-Flash UD-IQ1_S 82.5 GB, build
`42974d12` clean, `-c 8192 -ngl 99 -sm layer -ts 3,4,4,1 -fit off -fa on -ncmoe 40`.
Date 2026-08-01. Predictions: `PREDICTIONS_ds4_promptcache.md`.

**Verdict: direction confirmed, magnitude not measured, practical question still open.**
Recorded because the failure modes are reusable, not because the result is.

## Raw data

Three-turn chat, temp 0, `max_tokens` 200 per turn. `PROMPT_TOKENS` = tokens actually
processed (from `prompt eval time = X ms / N tokens`) — the number that separates a cache
hit from a fast re-prefill.

| arm | turn 1 | turn 2 | turn 3 |
|---|---|---|---|
| `cache_prompt=true` | 27 tok / 33.6 s | **92** tok / 25.6 s | **31** tok / 15.3 s |
| `cache_prompt=false` | 27 tok / 5.9 s | **115** tok / 19.8 s | **170** tok / 18.0 s |
| total time (cache) | 131.2 s | 83.1 s | 83.0 s |
| total time (nocache) | 65.9 s | 67.0 s | 65.7 s |

Output stayed coherent throughout: gzip 0.4545–0.5515, CJK 0, 874–991 chars per turn.

## What is defensible

**Processed prompt tokens grow without caching and do not grow with it.** No-cache goes
27 → 115 → 170, monotonic. Cache goes 27 → 92 → 31, non-monotonic and small by turn 3.
That is the expected signature and it is the one real result here.

## Three reasons the magnitude is not measured

**1. The control did not control.** With `cache_prompt=false`, turn 2's full prompt is
~242 tokens (27 + a 200-token reply + ~15 new). It processed **115**. Turn 3's full prompt is
~460; it processed **170**. So roughly half the context was reused *with caching disabled* —
`cache_prompt=false` does not produce a cold re-prefill in this build. The cache arm is
therefore being compared against "partial caching," not "no caching," and the ratio between
them (1.25× at turn 2, 5.5× at turn 3) understates the true effect by an unknown amount.

**P-C1 is scored FALSIFIED on its own terms** — it predicted a ≥5× drop at turn 2 and
measured 1.25×. But the honest reading is that the instrument could not have measured what
P-C1 described, so the falsification is uninformative about caching itself.

**2. Arm order confounds every timing comparison.** The no-cache arm ran second and is
*faster on every turn* (≈66 s vs ≈83 s). Caching cannot make generation slower. With
`-ncmoe 40`, expert weights stream from CPU memory on every token, so the second arm
inherited a warm page cache. **Timings between arms are not comparable**, only within an arm.
A correct design randomises or alternates arm order, or restarts the server between arms.

**3. The context never got near the regime the question is about.** This is the important
one. `DS4_FLASH_P100_LOAD.md` measured **478 ms/token prefill**, which is painful at 4k+
context — a 4k prompt costs ~32 minutes. This conversation peaked around **460 tokens**.
At that size prefill is 15–26 s while decode is 47–68 s, so **decode dominates and prefill
was never the bottleneck being tested.** The test ran in a regime where the problem does not
occur.

## Prediction scoring

| id | claim | conf | outcome |
|---|---|---|---|
| P-C1 | turn-2 prompt tokens drop ≥5× vs no-cache | 0.80 | **FALSIFIED** — 1.25× (but see above: control was broken) |
| P-C2 | turn-2/3 wall-clock < 180 s | 0.60 | **CONFIRMED** — 83.1 s, 83.0 s |
| P-C3 | no-cache grows monotonically (full re-prefill) | 0.85 | **PARTIAL** — grows (27→115→170) but never full re-prefill |
| P-C4 | coherent across 3 turns, gzip 0.42–0.60, CJK 0 | 0.70 | **CONFIRMED** — 0.4545–0.5515, CJK 0 |
| P-C5 | cache works despite `-ncmoe 40` | 0.75 | **WEAK CONFIRM** — direction right, magnitude unmeasured |

P-C2 confirmed at 83 s/turn, but that is a **200-token answer on a ~460-token context**. It
does not generalise to the research-companion use it was meant to inform.

## Method defects found (all mine)

1. **Log markers were destroyed.** The script appended `===TURN n===` to the same file
   llama-server had open via `>` redirection. Two independent write offsets on one file:
   **0 of 6 markers survived.** The parsed numbers happened to be correct anyway — with the
   marker missing, `rsplit` returned the whole file and the parser took the *last* match,
   which is the right line for that turn. Correct by luck, not design. Verified after the
   fact by confirming exactly 6 prompt-eval lines in request order. Parse by ordinal
   position, or have the harness write to its own file.

2. **Wall-clock printed `?` on every row** — a `python3 -c` one-liner used `sys.argv`
   without `import sys`. Harmless here because `total time` is in the server log, but the
   script's own timing column was dead for the entire run and nothing failed loudly.

3. **No arm-order control**, as above.

## What the real test looks like

Load ~3,500 tokens of context in turn 1 (the realistic pattern: paste a document, then ask
questions about it), then 2–3 short follow-ups with `max_tokens` small so prefill dominates
the measurement rather than decode. At 478 ms/token an uncached re-prefill is ~28 minutes
per turn versus seconds cached — a difference no confound can hide. Alternate arm order or
restart the server between arms.

That test answers "is DS4-Flash usable as a research companion on this hardware." **This one
does not, and the `DS4_FLASH_P100_LOAD.md` framing should stay flagged as open until it is
run.**

## Provenance

- `.194:~/ds4_cache/` — `cache.log`, `server.log`, `resp_{cache,nocache}_t{1,2,3}.json`
- Script `~/ds4_promptcache.sh`; local copy in `scratchpad/ds4_promptcache.sh`
- Build `~/llama_tq_ds4/build_ds4` @ `42974d12`, `version: 10245`, tree clean
