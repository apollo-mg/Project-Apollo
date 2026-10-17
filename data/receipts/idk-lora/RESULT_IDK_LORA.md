# Result -- a 100-second self-labelled LoRA ties IBM's purpose-built certainty adapter on Granite 4.1 3B: wrong answers 81 -> 26 with 35 correct answers against the base's 37; IBM's cuts to 5 but drops 17 correct; one logit bias does not work here

**Prereg:** `PREREG_IDK_LORA.md` (`670941c5`, before any M1 row or training), Deviation 1 (`925360bd`, toolchain, before
any row), Deviation 2 (`078068ce`, bare-answer rule, **after the Stage A rows were seen**, before any Stage B row).
**Analysis:** `analyze_idk.py` -> `RESULT_idk.json` (Stage A also as `RESULT_idk_stageA*.json`). **Raw:**
`quant-abstention/raw/main_IDK_{B41,B42,BPHI,LORA,CTRL}.jsonl`, `raw/IDK_{BIAS,IBM}.jsonl`, `raw/labels_G41.jsonl`.

**Run (2026-10-17, 18:30-18:49, RX 9070 XT):** buun `build_rocm` 38ada0e1b, Q8_0 files converted here, `-c 4096 -np 1`
f16 KV, greedy, thinking off, fresh server per arm. Labelling the 3,864-item pool took 9 minutes; Stage B (BIAS fit
and run, IBM, two trainings, two M1 runs) took 7. Every arm finished: at most 1 unfinished answer in 240.

## Results on M1 (bare-answer rule applied to every arm; 240 items: 40 easy, 100 hard, 100 invented)

| arm | Net | wrong answers (E / H / invented answered) | correct (E / H) | refused (E / H / invented) |
|---|---:|---|---|---|
| **IDK_B41** Granite 4.1 3B base | 0.154 | **81** (13 / 49 / 19) | 37 (25 / 12) | 2 / 38 / 81 |
| **IDK_BIAS** one logit bias, answer-first | -0.071 | 120 (15 / 68 / 37) | 40 (25 / 15) | 0 / 17 / 63 |
| **IDK_IBM** IBM uncertainty adapter, tau 0.70 | **0.479** | **5** (0 / 5 / 0) | 20 (12 / 8) | 28 / 87 / 100 |
| **IDK_LORA** our self-labelled LoRA | **0.454** | **26** (9 / 17 / 0) | **35** (22 / 13) | 9 / 70 / 100 |
| **IDK_CTRL** same recipe, answers only | -0.479 | 177 (16 / 81 / 80) | 42 (24 / 18) | 0 / 1 / 20 |
| IDK_B42 Granite 4.2 3B base | 0.304 | 44 (16 / 26 / 2) | 19 (14 / 5) | 9 / 69 / 98 |
| IDK_BPHI Phi-4-mini base | -0.567 | 185 (14 / 76 / 95) | 44 (26 / 18) | 0 / 6 / 5 |

Net: +1 a correct answer or a refusal of an invented item, -1 a wrong answer or an answer to an invented item, 0 a
refusal of a real question or no finished answer.

**Self-knowledge AUROC** (items it does not get right, every invented item included, against those it does):
G41 slot 0.696, **LORA slot 0.945**, CTRL slot 0.689, **IBM certainty 0.954**, G42 slot 0.947, Phi slot 0.851.

## Registered verdicts

| # | prediction | outcome |
|---|---|---|
| P1 | Granite is better calibrated than Phi (invented refusal +0.10) | **holds with the rule**: +0.76 [+0.68, +0.84]. As originally graded it does not hold: -0.04 [-0.09, 0.00] |
| P2 | the LoRA helps (Net +0.10) | **holds**: +0.30 [+0.21, +0.40] |
| P3 | training beats one number | **holds**: +0.525 [+0.42, +0.64] |
| P4 | IBM's tool at least as good as ours | **holds, as a tie**: +0.025 [-0.04, +0.09] |
| P5 | knowledge kept (E+H correct >= 90 %) | **holds**: 35 vs 37 |
| P6 | refusal transfers to the unseen opera template (+0.20) | **does not hold, and could not**: the base already refuses all 25 invented operas (ceiling) |
| P7 | the control does not learn to refuse | **holds, more strongly than predicted**: refusal falls 0.81 -> 0.20 (-0.61 [-0.70, -0.52]) |

## Reading

**A weekend LoRA matches a lab's calibration tool on the score, at a different operating point.** Trained for 100
seconds on 898 examples the model labelled itself (449 it got right, 449 it got wrong; no invented items, no human
labels), the LoRA cuts wrong answers by two thirds and gives 35 correct answers against the base model's 37. IBM's adapter,
thresholded where it scored best on the same held-out real questions, gives almost no wrong answers (5) but also
drops 17 correct ones, including 13 easy questions. The two Net scores are statistically tied. Which one is better
depends on the cost of a wrong answer: IBM's is the safer gate, ours the more useful one.

**What each costs.** The LoRA decides while it answers: no extra pass, and one 62 MB adapter file. IBM's adapter needs
a second pass per question (here 3.8 s for 240 questions, batched, 25,708 prompt tokens), but its output is a score,
so the threshold can be moved at run time; ours is one fixed operating point.

**The control is the cleanest part.** The same recipe trained only on the answers it got right does not learn to
refuse; it unlearns refusing (0.81 -> 0.20) and answers 80 invented questions. So the LoRA learned *when* to say UNKNOWN,
not merely a format or a general shift. It also sharpened the model's own internal signal: the answer-slot AUROC went
from 0.696 to 0.945, roughly to IBM's 0.954.

**One logit bias does not work on Granite.** Forcing the answer first (`Exact Answer:` before anything else) makes this
model answer: on the calibration split, Net is negative at every bias tried (-0.65 at b = 0, -0.55 at the grid's top,
b = 12, which was chosen at the edge). Granite's own habit is to write a bare `UNKNOWN`, which the answer-first format
suppresses. The no-training rung that worked on quantized Qwen files (`RESULT_CALIB.md`) does not transfer.

**Mark's hypothesis, read honestly.** Granite says "I don't know" far more than Phi (81 vs 5 invented items refused),
but it is caution rather than calibration: Granite 4.1 also refuses 38 of 100 real hard questions, and 4.2 refuses 98
invented and 69 real hard ones while having the best internal discrimination of the three bases (0.947). IBM has moved
4.2 toward not answering. The bare-`UNKNOWN` habit also hid all of this from our grader at first (Deviation 2).

## What was sacrificed, and accounted for

- **Coverage.** The LoRA refuses 70 of 100 real hard questions (base 38) and 9 of 40 easy ones (base 2). On hard items it
  knew only 12 answers to begin with, and it still gives 13.
- **Generality.** Factual lookups in four question types; the opera transfer test hit the base model's ceiling.
- **One base model, one seed, one instrument;** 240 items. The LoRA's final training loss (0.009) shows it fit its
  training set closely, but M1 shares no items with it.

## Not established

- Whether it helps a model that does not already lean cautious (Phi would be the test: its base refuses 5 of 100).
- IBM's adapter at other thresholds (the score allows a whole curve; one registered point is reported).
- Training-data ordering (buun's idea), larger or smaller training sets, other ranks.
