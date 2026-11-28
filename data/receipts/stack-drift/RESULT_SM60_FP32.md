# RESULT: the sm_60 fp32 carve-out closes the P100s' gap to the CPU -- mean KLD 0.0065 -> 0.0006, same top 94.6 % -> 99.1 %, now as close as the desktop -- but M1 answers still differ in wording from the desktop as often as before, so scores never depended on it

**Prereg:** `PREREG_SM60_FP32.md` (`73874af4`, before any patched-build row). **Run:** 2026-11-27 19:04-19:24 EST, .73
(one P100), mainline `33aeb17f8`; patched build from `data/scorecard/build_engine.sh` (BUILD_OK names `+sm60-fp32-carveout`,
binary `59bf26a1...`); unpatched = the drift study's build. **Records:** `raw/state_fp32_n73.log`, `raw/build_fp32_n73.log`,
`raw/kld_fp32_OLD.log`, `raw/kld_fp32_NEW.log`, `quant-abstention/raw/main_DR_N73F_1.jsonl`; comparison
`summary_fp32.txt`.

## Results

| Qwen3.5-9B Q8_0 vs the CPU reference (wikitext, 10 x 512) | mean KLD | 99.9 % KLD | same top token | PPL ratio |
|---|---|---|---|---|
| P100, mainline as shipped (today; drift study 11-24 identical) | 0.006451 | 0.0632 | 94.59 % | 1.0033 |
| **P100, with the carve-out** | **0.000603** | 0.0358 | **99.06 %** | 1.0006 |
| desktop 9070 (drift study, for reference) | 0.00067 | | 98.8 % | |

| prediction / gate | result |
|---|---|
| G1 the unpatched build reproduces 0.006451 / 94.588 % | **passes**, to every printed digit |
| F1 patched mean KLD <= 0.002 (0.75) | **holds:** 0.000603 |
| F2 patched same top >= 98 % (0.65) | **holds:** 99.06 % |

M1 (reported without prediction): the patched P100 gives the same answer text as the desktop on 154 of 240 items (the
unpatched P100s: 153) and the same grade on 228 (unpatched: 230); against the unpatched P100 it differs in wording on 74
items and in grade on 12. Totals: invented declined 67 (unpatched 66, desktop 64), hard right 44 (44, 42), easy right 31
(34, 34).

## Reading

1. **The cause of the P100 gap is found.** The drift study left it untested; the carve-out removes 91 % of the P100s'
   divergence from the CPU and puts them level with the desktop. Mainline's fast-FP16 gate for sm_60 was the whole story.
2. **It never touched the scores.** Answers still differ in wording from the desktop on a third of items, as before, and
   grades on about 5 %: greedy decoding on any two numeric paths eventually picks a different word and diverges from
   there, even when the probabilities are ten times closer. Machine-to-machine wording drift is a property of greedy
   decoding, not of this bug.
3. **What changes for us:** patched P100 builds are now the default (`build_engine.sh`). Logit-level work on the P100s
   (KLD, perplexity comparisons) is now trustworthy on mainline-based builds. Byte-for-byte replays of runs made on
   unpatched builds need the unpatched build (`SM60_FP32=0`); score comparisons do not.

## Limits

One model (9B dense Q8_0), one card, one context length; the CPU is a reference with its own rounding, not truth; one M1
run per build.
