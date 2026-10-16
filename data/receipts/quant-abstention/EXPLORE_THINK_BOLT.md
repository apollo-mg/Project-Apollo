# Exploratory probe (not a registered arm) -- does thinking on flip Bolt's confabulations into refusals?

**Written 2026-10-16, before the probe ran.** Mark's suggestion: before spending a full thinking-on arm, run a subset of
Bolt's failed invented items with thinking on and see whether anything meaningful flips.

**Prior art checked:** `ledger_precheck.py "thinking reasoning abstention refusal invented"` -> thinking-cap and Swift
receipts (Flash-Next/27B: a 512-token cap turned one correct abstention into an invented answer; Swift's brevity
turned runaways into invented answers); AbstentionBench (outside): reasoning fine-tuning cuts abstention ~24 %. None is
a within-model thinking off -> on comparison on M1.

**Model and host:** NVIDIA's Bolt 2-bit QAT file (the `BOLT` arm), .73, upstream v0.7.0, `-ngl 99 -sm layer -c 12288
-ctk f16 -ctv f16 -np 1 -fit off` (context raised from 4096 so thinking fits; the only change from `BOLT`).

**Items (fixed by seed 20261016 from `raw/main_BOLT.jsonl`):** 20 of the 84 invented items Bolt answered (WRONG), plus
controls: 5 hard items it got right and 5 invented items it refused.

**Request:** the same CAL prompt and grader as `run_main.py`, `enable_thinking: true`, temperature 0, `max_tokens`
8192, `cache_prompt` false. TRUNCATED as in the instrument.

**Reading fixed in advance:** >= 5 of the 20 flipping to ABSTAINED would justify a full thinking-on arm; 0-2 says
thinking does not rescue it. Controls: any right answer that breaks, and any refusal that turns into an answer, is
reported. Twenty items cannot estimate a rate; this decides whether to measure one.

## Outcome (2026-10-16 ~01:10; `raw/probe_think_BOLT.jsonl`, 30 rows)

All 30 requests `finish: stop`, answers parsed from content; .73 at 1328 MHz, server `-c 12288`, `/props` confirmed
NVIDIA's 24GB file.

| class | n | thinking off | thinking on | median completion tokens (on) |
|---|---:|---|---|---:|
| invented, answered with thinking off | 20 | 20 WRONG | **7 ABSTAINED**, 13 WRONG | 651 |
| hard, right with thinking off | 5 | 5 CORRECT | 5 CORRECT | 233 |
| invented, refused with thinking off | 5 | 5 ABSTAINED | 5 ABSTAINED | 362 |

**Reading (fixed in advance): 7 of 20 flips >= 5, so a full thinking-on arm is justified.** No control broke.

**Where the flips are:** the 7 flips used a median of 1,112 completion tokens (651-3,283); the 13 that stayed wrong
used a median of 258 (130-5,627; 11 of 13 under 340). When Bolt deliberates past a few hundred tokens it tends to find
the false premise ("This seems like a fabricated title. Therefore, the premise is false"); when it answers after a
short think it confabulates as before, mostly on the invented-opera and bare-year templates. This is an association
on 20 items, not a cause. It is worth noting next to NVIDIA's card, whose RLHF reward model carried "a reasoning
penalty for token efficiency".

Not a rate: 20 items chosen from Bolt's failures cannot estimate thinking-on refusal on M1. That needs the full arm
(240 items, thinking on, the instrument's grader), registered first.
