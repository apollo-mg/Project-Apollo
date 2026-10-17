# Result -- at equal coverage, a 100-second self-labelled LoRA and IBM's purpose-built certainty adapter give the same answers on Granite 4.1 3B (both 35 right, 26 wrong on 61 real questions answered, against the base's 37 right, 62 wrong); one logit bias does not help here

> **Correction, added 2026-10-17 before reporting (the registered verdicts below are unchanged).** The first version of
> this receipt led with Net ("ties IBM, triples the base"). Net rewards refusing invented items, so a policy that
> answers UNKNOWN to everything scores **0.417**, just under the LoRA's 0.454, and most of the gain over the base is
> refusals of invented items a constant policy gets free. The number that carries the result is **net answers on the
> 140 real questions** (correct minus wrong): IBM +15, LoRA +9, refuse-all 0, base -25. Three claims in the first
> Reading were also checked against the stored rows and are restated below: "learned *when* to refuse" (survives a
> within-template cross-tab), the slot AUROC (now on the base's labels), and the logit bias (it did not help within
> the registered range; the calibration optimum is degenerate). Found in review, before the result was shared.

**Prereg:** `PREREG_IDK_LORA.md` (`670941c5`, before any M1 row or training), Deviation 1 (`925360bd`, toolchain, before
any row), Deviation 2 (`078068ce`, bare-answer rule, **after the Stage A rows were seen**, before any Stage B row).
**Analysis:** `analyze_idk.py` -> `RESULT_idk.json` (Stage A also as `RESULT_idk_stageA*.json`). **Raw:**
`quant-abstention/raw/main_IDK_{B41,B42,BPHI,LORA,CTRL}.jsonl`, `raw/IDK_{BIAS,IBM}.jsonl`, `raw/labels_G41.jsonl`.

**Run (2026-10-17, 18:30-18:49, RX 9070 XT):** buun `build_rocm` 38ada0e1b, Q8_0 files converted here, `-c 4096 -np 1`
f16 KV, greedy, thinking off, fresh server per arm. Labelling the 3,864-item pool took 9 minutes; Stage B (BIAS fit
and run, IBM, two trainings, two M1 runs) took 7. Every arm finished: at most 1 unfinished answer in 240.

## Results on M1 (bare-answer rule applied to every arm; 240 items: 40 easy, 100 hard, 100 invented)

| arm | Net | real-question net | wrong answers (E / H / invented answered) | correct (E / H) | refused (E / H / invented) |
|---|---:|---:|---|---|---|
| **IDK_B41** Granite 4.1 3B base | 0.154 | -25 | **81** (13 / 49 / 19) | 37 (25 / 12) | 2 / 38 / 81 |
| **IDK_BIAS** one logit bias, answer-first | -0.071 | -43 | 120 (15 / 68 / 37) | 40 (25 / 15) | 0 / 17 / 63 |
| **IDK_IBM** IBM uncertainty adapter, tau 0.70 | **0.479** | **+15** | **5** (0 / 5 / 0) | 20 (12 / 8) | 28 / 87 / 100 |
| **IDK_LORA** our self-labelled LoRA | **0.454** | **+9** | **26** (9 / 17 / 0) | **35** (22 / 13) | 9 / 70 / 100 |
| **IDK_CTRL** same recipe, answers only | -0.479 | -55 | 177 (16 / 81 / 80) | 42 (24 / 18) | 0 / 1 / 20 |
| IDK_B42 Granite 4.2 3B base | 0.304 | -23 | 44 (16 / 26 / 2) | 19 (14 / 5) | 9 / 69 / 98 |
| IDK_BPHI Phi-4-mini base | -0.567 | -46 | 185 (14 / 76 / 95) | 44 (26 / 18) | 0 / 6 / 5 |

| *reference: answer UNKNOWN to everything* | *0.417* | *0* | *0* | *0* | *40 / 100 / 100* |

Net: +1 a correct answer or a refusal of an invented item, -1 a wrong answer or an answer to an invented item, 0 a
refusal of a real question or no finished answer.

**Self-knowledge AUROC, on the base model's labels** (real questions only: does the score separate the questions G41
answered correctly from the ones it did not?): G41's own slot 0.558, **LORA slot 0.897**, **IBM certainty 0.914**. (With
each arm's own labels and invented items included, as first reported: G41 0.696, LORA 0.945, IBM 0.954, CTRL 0.689,
G42 0.947, Phi 0.851. The LoRA's slot sits right after a forced `Exact Answer:`, the format it was trained to write
UNKNOWN into, so the matched-label number is the fair one.)

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

**On the real questions, the LoRA turns a losing model into a winning one, and at equal coverage it matches IBM's tool
exactly.** The base Granite 4.1 answers 99 of the 140 real questions and gets 62 wrong (net -25). Trained for 100
seconds on 898 examples it labelled itself (449 it got right, 449 it got wrong; no invented items, no human labels),
the LoRA answers 61 and gets 26 wrong (net +9). IBM's adapter at its registered threshold answers only 25 and gets 5
wrong (net +15). *Exploratory, chosen on M1:* letting IBM's certainty answer the same number of real questions as the
LoRA (its top 61) gives **35 right and 26 wrong, identical to the LoRA**. The registered difference between the two is
where each sits on the same curve, not how good the curve is.

**Why IBM sat so far toward refusing.** Its threshold was fitted to maximise Net on the 772 held-back real questions,
about 85 % of which the base gets wrong, so any threshold fitted there drifts toward refusing almost everything (tau
0.70 refused 28 of 40 easy questions on M1). The LoRA was trained on a 50/50 balance. So "IBM is the safer gate, ours
the more useful one" is partly the calibration set's base rate, not the tools. The real difference in kind: IBM's
output is a score, so the threshold can be moved at run time; the LoRA is one fixed operating point with no second pass.

**It learned when to refuse, not which question types to refuse.** The training classes were confounded (known items
are mostly capitals; unknown mostly novels and universities), so the LoRA could have learned "obscure template ->
UNKNOWN". Within each template and difficulty group it did not: across the 140 real questions it refuses 37 of the 62
the base got wrong and 3 of the 37 the base got right (university hard: 17 of 22 base-wrong refused, 0 of 1
base-correct; novel hard: 9 of 16 against 0 of 8; capital easy: 3 of 3 against 0 of 5). On the base's own labels its
answer-slot score separates right from wrong at 0.897 AUROC, where the base's own slot was near chance (0.558) and
IBM's certainty is 0.914.

**The control.** The same recipe trained only on the answers it got right does not learn to refuse; it unlearns it
(invented items refused 0.81 -> 0.20) and answers 80 invented questions.

**One logit bias did not help within the registered range.** Forcing the answer first (`Exact Answer:` before anything
else) makes this model answer: calibration Net was negative at every bias from -4 to +12 and still rising at the top,
so the chosen b = 12 sits at the grid's edge and the calibration optimum is degenerate (refuse everything). Granite's
own habit is a bare `UNKNOWN`, which the answer-first format suppresses. The no-training rung that worked on quantized
Qwen files (`RESULT_CALIB.md`) does not carry over here.

**Mark's hypothesis, read honestly.** Granite says "I don't know" far more than Phi (81 against 5 of 100 invented items
refused), but it is caution rather than calibration: Granite 4.1 also refuses 38 of 100 real hard questions, and 4.2
refuses 98 invented and 69 real hard ones while having the best internal discrimination of the three bases (0.947).
The bare-`UNKNOWN` habit also hid all of this from our grader at first (Deviation 2).

## What was sacrificed, and accounted for

- **Coverage.** The LoRA refuses 70 of 100 real hard questions (base 38) and 9 of 40 easy ones (base 2). On hard items it
  knew only 12 answers to begin with, and it still gives 13.
- **Generality.** Factual lookups in four question types; the opera transfer test hit the base model's ceiling.
- **One base model, one seed, one instrument;** 240 items. The LoRA's final training loss (0.009) shows it fit its
  training set closely, but M1 shares no items with it.

## Exploratory: does it carry over to plain chat? (12 prompts, after the result; `raw/spotcheck/spotcheck.jsonl`)

Mark's question: did it learn to abstain in general, or only on this kind of question? Same server, adapter switched
per request (`lora` scale 0 or 1), plain chat with **no M1 instruction**, greedy, 120 tokens.
- **Normal use is unchanged:** math, a Python function, a haiku, an explanation, famous facts and obscure real facts
  it knows are answered the same way with and without the adapter. No sign of general over-refusal.
- **The better abstention does not obviously carry over:** asked about an invented opera with "and when did it
  premiere?", both versions invent an answer (base: Rossini, 1823; LoRA: Donizetti, 1835), where under the M1
  instruction both refused every invented opera. On an invented novel and an invented town both versions decline, as
  the base already did.
- **Reading:** every training example carried the M1 instruction, so the learned behaviour is most likely tied to that
  instruction and this question family. Twelve prompts is anecdotal. The test that would settle it trains on mixed
  phrasings (with and without the instruction, prose refusals as well as the UNKNOWN keyword) and scores held-out
  wordings and question types.

## Not established

- Whether it helps a model that does not already lean cautious (Phi would be the test: its base refuses 5 of 100).
- IBM's adapter as a full curve: one registered point and one exploratory point (at the LoRA's coverage) are reported (`check_idk.py`, `raw/check_idk.txt`).
- Training-data ordering (buun's idea), larger or smaller training sets, other ranks.
