# Result -- round 2: training on mixed phrasings carries refusal of invented items to a held-out phrasing (0.04 -> 0.42), but only for invented names that sound unfamiliar, not for real questions it gets wrong; one real question it knew is now refused

**Prereg:** `PREREG_IDK_LORA2.md` (`4d911020`, before any round-2 generation or training). **Analysis:**
`analyze_idk2.py` -> `RESULT_idk2.json`. **Raw:** `raw/E2_{BASE,LORA,LORA2}.jsonl`, `raw/E2_audit.json`,
`raw/normal_LORA2.jsonl`, `raw/formats_G41.jsonl`, `quant-abstention/raw/main_IDK_LORA2.jsonl`.

**Run (2026-10-17, 20:04-20:18, RX 9070 XT):** F2/F3 base answers (898), LORA2 training (2,252 examples: 898 in the
M1 phrasing, 595 known + 595 unknown pairs across F2 and F3 after dropping 77 F2 and 144 F3 known pairs whose base answer
was not correct in that phrasing; 359 s), E1, BASE byte-identity smoke (5/5 SAME), E2 for three arms, normal-use
prompts. Every audit gate passed: hand grades agree with the strict grader on 20/20 (BASE), 20/20 (LORA), 19/20 (LORA2;
the miss is a refusal the grader did not recognise, "not specified in my knowledge base", so the grader *under*-counts
LORA2's refusals). Strict and lenient grading are identical on every arm: no hedged answers.

## E2: the M1 questions reworded, under a held-out wrapper with no refusal instruction

| arm | easy | hard | hard refused | invented refused | real-question net |
|---|---:|---:|---:|---:|---:|
| BASE | 0.725 | 0.20 | 0.00 | 0.01 | -42 |
| LORA (round 1) | 0.725 | 0.23 | 0.00 | 0.04 | -36 |
| **LORA2** | 0.65 | 0.18 | 0.06 | **0.42** | -46 |

Invented items refused by template (of 25): capitals BASE 1, LORA 3, **LORA2 15**; universities 0, 1, **23**; novels 0,
0, 3; operas 0, 0, 1. Real questions in E2: LORA2 refuses 6 of 100 hard (all universities) and 0 of 40 easy; of the 89
real questions BASE answers wrong, LORA2 refuses 5.

**E1 (the M1 instruction, as round 1):** LORA2 real-question net +10 (round 1 +9), invented refused 1.00.

## Registered verdicts

| # | prediction | outcome |
|---|---|---|
| R1 | refusal carries to the held-out phrasing (+0.15 over round 1) | **holds**: +0.38 [+0.29, +0.48] |
| R2 | and helps on real questions there | **does not hold**: -0.03 [-0.11, +0.06] per item |
| R3 | round 1's gain under the M1 instruction is kept | **holds**: +10 vs +9 |
| R4 | normal use unchanged (0 of 9 refused) | **does not hold**: 1 of 9. It now says "I don't know." to the founding year of the University of Ouagadougou, which the base answers correctly (1962) |
| R5 | transfer to the unseen opera template in the unseen phrasing | **does not hold**: 1 of 25 vs 0 |

## Reading

**Mixed phrasings did break round 1's dependence on the instruction, for one kind of item.** Round 1's adapter barely
changed behaviour without its instruction (invented refused 0.04). Round 2's refuses 0.42 under a wrapper and wording it
never trained on, and in plain chat it now declines all three invented spot-check items, including the fake opera both
earlier versions confabulated (plain chat is a trained phrasing, so that part is in-distribution).

**But what transferred looks like "this name is unfamiliar", not "I don't know the answer".** The refusals sit almost
entirely on invented capitals and universities, standalone made-up names ("Västerholm University", "Haut-Mabali").
Invented novels and operas, which are pinned to a famous real author or written as a plausible Italian or French opera
title ("Steinbeck's novel The Orchard at Soledad", "Il barone di Modica"), are still answered confidently. And on real
questions the model gets wrong, it refuses almost none (5 of 89). Under the M1 instruction (round 1's E1 cross-tab) the
same recipe refused real questions it got wrong at 37 of 62; under the held-out phrasing that self-knowledge did not
come along.

**Speculation, labelled as such:** this matches Anthropic's 2025 circuit-tracing account of hallucination, in which a
default "can't answer" pathway is switched off by a "known entity" signal, and confabulation happens when familiarity
fires on something unknown. A famous author's name supplies familiarity, so the fake Steinbeck novel gets an answer; a
standalone invented place name supplies none, so the strengthened default wins. If that is right, LORA2 strengthened the
default refusal but did not teach the model to override familiarity, which is the harder and more useful skill.

**The cost showed up where the training mix was lopsided.** Granite knew few university founding years, so universities
were 165 of the 449 unknown training items and 52 of the 449 known (capitals: 131 unknown, 244 known). The one normal-use
regression is a real university question the base answers correctly. A balance within each template, not only overall,
is the obvious fix.

## Not established

- One base model, one seed, one held-out phrasing; 240 items; a 12-prompt normal-use check.
- Whether more phrasings, per-template balance, or training on familiar-sounding unknowns (real obscure items pinned
  to famous names) would carry the self-knowledge, not only the unfamiliarity response.
- The circuit-level reading is a hypothesis from the item pattern; nothing here looks inside the model.
