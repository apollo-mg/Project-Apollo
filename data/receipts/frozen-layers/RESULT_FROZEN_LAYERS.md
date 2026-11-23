# RESULT: freezing the last 10 of 40 layers never protects "I don't know" from fine-tuning -- over three training seeds the model declined 18, 5 and 2 of 100 invented questions, against 20, 3 and 0 with every layer trained and 81 before; an adapter on the first half of the network does more damage than one on the last half on every seed

**Prereg:** `PREREG_FROZEN_LAYERS.md` (`c1f47f42`, before any training) and Amendment 1 (`79d86a32`, committed 14:12:07,
one second before the replicate started; its "~14:25" heading time is a slip). **Runs:** 2026-11-23, RX 9070 XT, buun
`38ada0e1b` `build_rocm`: the registered seed 13:58-14:07 (`run_frozen.sh`), training seeds 1 and 2 14:12-14:29
(`run_replicates.sh`). **Analysis:** `analyze_frozen.py` (`--suffix _S1`, `_S2` for the replicates) -> `summary.txt`,
`summary_S1.txt`, `summary_S2.txt` and the matching `RESULT_frozen*.json`. **Records:** M1 rows in
`quant-abstention/raw/main_FZ_*.jsonl`; training, conversion, server and run logs, per-step losses and adapter hashes
in `raw/`.

**The question (Altimor, 11-22):** "what about SFT with end layers frozen". **Checks:** the base replayed the October base
byte for byte (240 of 240 answers); the all-layers arm at the registered seed replayed the October IDK control byte for
byte (240 of 240; its step-40 training loss matched to every digit); every adapter held exactly its registered layers
(560 / 420 / 280 / 280 tensors); all 12 trainings used the same 449 items (one item hash). One stated difference from
October's server flags: `--cache-ram 0`, which the two replays show changed nothing.

## Results: invented questions declined, of 100 (M1, bare-answer rule)

| adapter on layers | registered seed | seed 1 | seed 2 | mean |
|---|---|---|---|---|
| none (the base) | 81 | | | 81 |
| all 40 (the October control) | 20 | 3 | 0 | 8 |
| 0-29 (last 10 frozen) | 18 | 5 | 2 | 8 |
| 0-19 (last 20 frozen) | 48 | 11 * | 45 | 35 |
| 20-39 (first 20 frozen; same adapter size) | 57 | 47 | 61 | 55 |

\* This adapter also ran away without finishing on 16 invented items; all the other adapters together left one unfinished.

Hard real questions declined follow the same order (base 38): all layers 1 / 1 / 0, last 10 frozen 0 / 0 / 0, last 20
frozen 14 / 4 / 8, first 20 frozen 20 / 13 / 19. Every adapter answered more hard questions, mostly wrongly (64 to 82
wrong against the base's 49), with a few more right (15 to 21 against 12). Easy questions barely moved (23 to 27 right
against 25). Training: 449 examples (the model's own correct answers, no "I don't know"), 42 to 53 seconds each.

## Predictions

| | result |
|---|---|
| M the control replicates (<= 0.40) | **holds:** 20 of 100, the October answers exactly (seeds 1 and 2: 3 and 0) |
| H1 freezing the last 10 does not protect (S >= 0.5) | **holds:** S = 1.03 [1.00, 1.09] |
| R1 H1 on both new seeds (0.9) | **holds:** S = 0.97 and 0.98 |
| H2 freezing the last 20 does not protect (S >= 0.5) | **holds by the registered rule, barely:** S = 0.54 [0.42, 0.67]; at the new seeds 0.90 and 0.44 -- not stable |
| H3 first half vs last half (no direction) | the first half does more: +0.09 [+0.03, +0.15] |
| R2 the first half does more on both new seeds (0.55) | **holds:** +0.36 [+0.26, +0.46] and +0.16 [+0.09, +0.23] |

S = the arm's drop as a share of the all-layers drop at the same seed; intervals are paired bootstraps over the 100
invented items and hold no training variance -- the seeds are that.

## Reading

1. **Freezing the end layers, as usually meant, does not help.** With the adapter off the last quarter of the network,
   the model lost "I don't know" as completely as with every layer trained, on all three seeds.
2. **The first half of the network does more of the damage than the last.** Two adapters of the same size: the one on
   the first half cut declines to 48, 11 and 45; the one on the last half to 57, 47 and 61. The first 30 layers alone
   did everything all 40 did. Training only the last half was the gentlest option tried, and it still cost a third of
   the model's "I don't know" on average.
3. **The size of the drop depends a lot on the training seed.** The October control's 81 to 20 was the mildest of
   three: the same data and recipe at two other seeds went to 3 and 0. The last-half-frozen arm swings too (11 to 48), which
   is why the first run's "freezing the last half protects about half" did not hold up.
4. **The training loss did not line up with the damage.** The last-half adapter reached the lowest loss on every seed
   (0.044 to 0.049) and did the least damage. (Loss is the mean of the last five logged steps, a rough measure.)

## Limits

One 3B model (Granite 4.1, 40 layers), one data set (short factual answers in M1's own format, so the push lands on the
test's home ground), LoRA rather than a full fine-tune, three training seeds, greedy decoding. A first-layer adapter's
change flows through every later layer, so "where it sits" includes how far its effect travels. No claim about the
fine-tunes on the RL page, which are other models trained on other data.
