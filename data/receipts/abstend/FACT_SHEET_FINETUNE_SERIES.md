# Fact sheet: post-trained variants say "I don't know" less, and know no more (2026-11-17)

> **Exception, 2026-11-19 (`pi-adapter/RESULT_PI_ADAPTER.md`):** a sixth variant, the pi adapter (an agent-RL LoRA on
> Qwen3.8-27B, applied to the same Q8_0 file), did NOT move: invented refused 0.60 vs 0.60 (0.00 [-0.03, +0.03]), hard
> 0.52 vs 0.50. "Every variant we measured" is no longer true; say "five of six", and name this one as the RL adapter.
> As an agent it declared impossible tasks impossible far more often than its base (13 of 21 vs 4).

For Mark to write from. Every number below was read from the receipt named beside it on 2026-11-17. ASCII only, so
any line can be pasted. Nothing here is new data: it gathers six receipts from 2026-10-25 to 2026-11-10.

## The claim, stated as strongly as the data allows

**Every post-trained variant of an open model we measured refused fewer questions about things that do not exist than
the model it was built from, and none of them knew more.** Five variants, five moved the same way, four of them clear
of noise. The sixth case, a reasoning distill, shows the biggest drop of all, but only with thinking on.

Words to avoid: "every fine-tune" (two of the five are not fine-tunes in the usual sense, see the table), "dishonest"
(the models are not lying; they answer when they should not), "proves" (five variants from three families).

## The instrument, in one paragraph

M1: 240 short factual questions built from Wikidata. 40 easy real ones (capitals and the like), 100 hard real ones
(obscure but true facts), and 100 invented ones (a novel, a university or a person that does not exist, built from
real patterns). The prompt asks for a final line `Exact Answer: ...` and OFFERS the word UNKNOWN for questions that
cannot be answered. Greedy decoding, thinking off, the model's own chat template, one llama.cpp build per comparison,
each base and its variant run in the same sitting. In every comparison the base was replayed the same day and matched
its stored run byte for byte. "Refused" = the share of the 100 invented questions answered UNKNOWN; "hard" = the share
of the 100 hard real questions answered correctly.

## The five variants

| variant | what it is | files | hard: base -> variant | refused invented: base -> variant | difference [95% CI], paired test |
|---|---|---|---|---|---|
| Sage-A1.5 (InternScience) | science/agent fine-tune of Qwen3.6-35B-A3B | both Q6_K, one packager | 0.67 -> 0.64 | 0.67 -> 0.48 | **-0.19** [-0.28, -0.11], 2 vs 21 flips, p = 0.0001 |
| Spark-X2.6-4B vs Spark-X2.5-4B | a point release by the same maker | both official Q8_0 | 0.15 -> 0.15 | 0.46 -> 0.31 | **-0.15** [-0.23, -0.08] |
| Arete-27B (Nous Research) | values fine-tune of Qwen3.8-27B | both Q8_0 | 0.50 -> 0.50 | 0.60 -> 0.48 | **-0.12** [-0.18, -0.06], 0 vs 12 flips, p = 0.0005 |
| Qwen3.8-27B Uncensored (OrcaRouter) | abliteration: a weight edit that removes refusals | both Q6_K | 0.52 -> 0.50 | 0.63 -> 0.55 | -0.08, 3 vs 10 flips, p = 0.09 (**not significant**) |
| Qwopus3.8-27B-Coder-Flash (Jackrong) | code/agent distillation of Qwen3.8-27B | both Q8_0 | 0.50 -> 0.48 | 0.60 -> 0.53 | **-0.07** [-0.13, -0.02], 1 vs 8 flips, p = 0.039 |

Receipts: `quant-abstention/RESULT_SAGE_MATCHED.md`, `abstend/RESULT_SPARK_25_vs_26.md`, `arete/RESULT_ARETE.md`,
`abliteration/RESULT_ABLITERATION_CALIB.md`, `qwopus/RESULT_QWOPUS_CODER.md`.

- **"Made up" is the other side of the same number.** Arete answered 52 of the 100 invented questions with something
  (its base 39); Qwopus 47 (base 39).
- **Arete's flipped items are novels, universities and capitals,** far from anything a values fine-tune targets
  (`arete/RESULT_ARETE.md`). The drop is not about the tuned topic.
- **Spark's release also ran away more:** thinking runaways 3.3% -> 17.5% (`abstend/RESULT_SPARK_25_vs_26.md`).

## Sage: the one we checked three ways

The first Sage run compared Sage at Q8_0 with its base at a plain Q6_K, and refusal fell by 0.22
(`quant-abstention/RESULT_SAGE.md`). An outside reader's MLX probe on Hugging Face (discussion #23 on
NousResearch/Arete-27B) found a much smaller gap and raised the precision mismatch. We reran it:

- **matched precision** (both mradermacher Q6_K): -0.19 [-0.28, -0.11] (`quant-abstention/RESULT_SAGE_MATCHED.md`);
- **under Sage's own recommended sampling,** three seeded replicates: -0.16 [-0.22, -0.10]
  (`quant-abstention/RESULT_SAGE_SAMPLED.md`).

Neither precision nor decoding explains the gap. This is the strongest single result in the series, and the history is
worth telling: a critic raised a fair point, and the result survived it.

## The sixth case: a reasoning distill, thinking on

DeepSeek-V4-Pro-Qwen3.5-9B (Jackrong; about 250K math and science reasoning traces) against Qwen3.5-9B, thinking on:
refused invented questions 0.94 -> 0.58 (**-0.36** [-0.46, -0.25], 3 vs 39 flips); it made up answers to 40 of 100
invented questions where the base made up 6; hard facts 0.39 -> 0.34 (-0.05 [-0.12, +0.02], not significant)
(`sci-distill/RESULT_SCI_DISTILL.md`). It is NOT counted in the five: with thinking off, the setting the five were
measured in, its non-thinking mode is broken (a median reply of two tokens) and it refuses MORE.

## The counter-case: training for "I don't know" does work

On Granite 4.1 3B, a LoRA trained in about 100 seconds on its own labelled answers took refusal of invented questions
from 81 to 100 of 100 and its wrong answers overall (all 240 questions) from 81 to 26; IBM's purpose-built
uncertainty adapter got to 100 of 100 with 5 wrong answers overall. Both pay for it in real questions refused: hard real questions refused rose from 38 to 70 (the LoRA) and
87 (IBM) of 100 (`idk-lora/RESULT_IDK_LORA.md`). So the drop above is not a law of fine-tuning: it is what you get when
nothing in the training rewards saying "I don't know", and the fix has a cost that also has to be measured.

## Caveats that must travel with the claim

1. **One kind of question.** Short English factual questions from Wikidata. "Knew no more" means obscure facts, not
   the skill each variant was built for: the coder may well code better and the science model may reason better
   (though the science distill reasoned worse on GPQA, `sci-distill/RESULT_SCI_DISTILL.md`).
2. **UNKNOWN is offered.** The prompt names it. Whether the same variants refuse less when nobody offers the word is
   not yet measured (design: `freeform-abstention/DESIGN_FREEFORM_ABSTENTION.md`).
3. **Thinking off,** greedy, at the precisions named. Sage held under sampling; the others were not rerun that way.
4. **Five variants from three base families, chosen because people were using them,** not a random sample of Hugging
   Face. Effects are modest (0.07 to 0.19) and the abliteration's is not significant on its own.
5. **Two of the five are not ordinary fine-tunes:** Spark is a point release, and abliteration is designed to remove
   refusals, so its direction is the least surprising.

## Pastables (ASCII, Mark's voice to adjust)

- One line: "Five popular variants of open models, five drops in how often they say 'I don't know' to made-up
  questions, zero gains in what they actually know."
- Two lines: "We test the actual files people download. Every post-trained variant we measured (Sage, Spark 2.6,
  Arete, Qwopus Coder, an abliteration) refused fewer questions about things that don't exist than its base, and none
  knew more facts. Receipts and caveats: <link>"
