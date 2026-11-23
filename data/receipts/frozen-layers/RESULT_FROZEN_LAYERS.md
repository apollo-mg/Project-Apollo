# RESULT: freezing the last 10 of 40 layers does not protect "I don't know" at all (18 of 100 invented questions declined, vs 20 with every layer trained and 81 before); freezing the last half protects about half (48); the damage is done more by the first half of the network than the last

**Prereg:** `PREREG_FROZEN_LAYERS.md` (`c1f47f42`, before any training). **Run:** 2026-11-23 13:58 to 14:07 EST, RX 9070
XT, buun `38ada0e1b` `build_rocm`, `run_frozen.sh` (code as committed with this receipt). **Analysis:**
`analyze_frozen.py` -> `summary.txt`, `RESULT_frozen.json`. **Records:** M1 rows in
`quant-abstention/raw/main_FZ_*.jsonl`; training, conversion, server and run logs, per-step losses and adapter hashes
in `raw/`.

**The question (Altimor, 11-22):** "what about SFT with end layers frozen". **Checks:** the base replayed the October base
byte for byte (240 of 240 answers); the all-layers reference replayed the October IDK control byte for byte (240 of
240; its step-40 training loss matched to every digit); each adapter held exactly its registered layers (560 / 420 /
280 / 280 tensors). One stated difference from October's server flags: `--cache-ram 0`, which the two replays show
changed nothing.

## Results (M1, bare-answer rule; 100 invented, 40 easy, 100 hard questions)

| arm | adapter on layers | invented declined | hard: right / wrong / declined | easy: right / wrong | final training loss |
|---|---|---|---|---|---|
| base | none | **81** | 12 / 49 / 38 | 25 / 13 | - |
| all layers (the October control) | 0-39 | **20** | 18 / 81 / 1 | 24 / 16 | 0.056 |
| last 10 frozen | 0-29 | **18** | 18 / 82 / 0 | 25 / 15 | 0.142 |
| last 20 frozen | 0-19 | **48** | 15 / 71 / 14 | 27 / 13 | 0.111 |
| first 20 frozen | 20-39 | **57** | 16 / 64 / 20 | 24 / 15 | 0.044 |

Training: 449 examples (the model's own correct answers, no "I don't know"), 42 to 53 seconds per adapter.

## Predictions (drop D = base minus arm on the invented items; S = share of the all-layers drop; paired bootstrap)

| | result |
|---|---|
| M the control replicates (<= 0.40) | **holds:** 0.20, the October answers exactly |
| H1 freezing the last 10 does not protect (S >= 0.5) | **holds:** D = +0.63 [+0.53, +0.72], S = 1.03 [1.00, 1.09] -- no protection at all |
| H2 freezing the last 20 does not protect (S >= 0.5) | **holds by the registered rule, barely:** D = +0.33 [+0.24, +0.42], S = 0.54 [0.42, 0.67] -- about half protected |
| H3 first half vs last half (no direction) | the first half does more: D(last 20 frozen) - D(first 20 frozen) = +0.09 [+0.03, +0.15] |

## Reading

1. **Freezing the end layers, as usually meant, does not help.** With the adapter off the last quarter of the network,
   the model lost "I don't know" exactly as much as with every layer trained (18 of 100 vs 20).
2. **Freezing the whole back half helps by half.** 48 of 100, against 81 before and 20 with nothing frozen.
3. **The damage lives earlier than the premise assumed.** The two half-network adapters have the same size. The one on
   the first half cut "I don't know" more (to 48) than the one on the last half (to 57), and the first 30 layers alone
   did all of it.
4. **How well an adapter learned the answers does not predict the damage.** The last-half adapter fitted the training
   answers best (final loss 0.044, lower than the all-layers 0.056) and did the least damage; the last-10-frozen
   adapter fitted worst (0.142) and did the most. So the smaller drops are not an adapter that learned less; they come
   from where it sits. (Loss is the mean of the last five logged steps, a rough measure.)
5. **Nothing here protected the hard real questions.** Every adapter answered more of them, mostly wrongly (64 to 82
   wrong against the base's 49), with a few more right (15 to 18 against 12).

## Limits

One 3B model (Granite 4.1, 40 layers), one data set (short factual answers in M1's own format, so the push lands on the
test's home ground), LoRA rather than a full fine-tune, one seed, greedy. A first-layer adapter's change flows through
every later layer, so "where it sits" includes how far its effect travels. No claim about the fine-tunes on the RL page,
which are other models trained on other data.
