# RESULT: Ripple-65B-Preview knows more than the 27B, far less than Beam, and on invented questions it rarely says "I don't know": it reasons until it runs out of budget

**Prereg:** `PREREG_RIPPLE.md` (`76806dcd`, before the GGUF existed). **Run:** 2026-11-06 05:16 to 2026-11-08 02:39 on .194
(4x P100, 150 W / 1063 MHz), llama.cpp `67107ac34f`, our own Q6_K (sha256 `7c13c83d...`, converted from the official BF16
at `30cb3b0e`; `convert_and_stage.sh`). Every gate passed (`quant-abstention/raw/logs/ripple.log`). About 45 hours for
240 items. **Numbers:** `RESULT_RIP_vs_{BEAMMED,BEAM,SVNV,C.A}.json`. **Raw:** `quant-abstention/raw/main_RIP.jsonl`.

## The result

| | Ripple-65B Q6_K | Beam (medium) | Super VL | Qwen3.8-27B Q8_0 |
|---|---:|---:|---:|---:|
| easy correct | 0.875 | 0.975 | 0.95 | 0.85 |
| hard real correct | **0.60** | 0.89 | 0.86 | 0.50 |
| hard real refused | 0.00 | 0.01 | 0.01 | 0.03 |
| **invented refused** | **0.29** | 0.96 | 0.92 | 0.60 |
| invented made up | 0.27 | 0.04 | 0.08 | 0.39 |
| **invented, never answered (hit the 8,192-token cap)** | **0.44** | 0 | 0 | 0.01 |
| unfinished, all items | 47 of 240 | 0 | 0 | 2 |

Paired against Beam (medium effort), on the same items: hard -0.29 [-0.38, -0.20] (1 vs 30 discordant), invented refused
-0.67 [-0.76, -0.58] (0 vs 67). Against the 27B: hard +0.10 [-0.01, +0.21] (21 vs 11, p = 0.11), invented refused
-0.31 [-0.41, -0.20].

- **On real questions it answers quickly:** median 175 tokens of reasoning plus answer on hard items, 103 on easy ones.
- **On invented questions it searches and does not stop:** median 6,770 tokens; 44 of 100 ran to the cap without an
  answer line, at about 34 minutes each on this hardware. The reasoning tries to recall the nonexistent place or book
  ("Let's check memory: ..."), then either runs out or settles on a name.
- **When it does finish an invented question, it is close to a coin flip:** 29 refusals and 27 invented answers among
  the 56 it finished, both after about 3,500 tokens.

## Predictions

| # | claim | result |
|---|---|---|
| P1 | a 65B dense model holds fewer facts than Beam (hard RIP - BEAMMED <= -0.05) | **held:** -0.29 |
| P2 | ...but at least as many as the 27B (hard >= 0.50) | **held:** 0.60 |
| P3 | it does not reach Beam's calibration (invented refused RIP - BEAMMED <= -0.10) | **held:** -0.67 |
| P4 | the 8,192-token budget is enough (unfinished <= 5 %) | **FAILED:** 19.6 %, 44 of them on invented items |

## Exploratory (post hoc, not registered): length is an outside "I don't know" signal

Completion length separates invented from hard real items with AUROC **0.936**: over 2,000 tokens, 83 of 100 invented
vs 7 of 100 hard real; over 4,000, 65 vs 4. So for this model, a harness could treat a long deliberation as "it does
not know" without reading the answer. Not tested on other models, and the cut-off would need a held-out set.

## Limits

- One file (Q6_K, our conversion), greedy, the model's own template, no thinking switch (the model decides). Beam ran at
  2 bits (AD-IQ2_XXS) with its own effort levels, Super VL in NVFP4, the 27B thinking off: these comparisons place
  Ripple; they do not isolate a cause.
- The budget shapes the invented-item numbers: with more than 8,192 tokens, some of the 44 would end as refusals and some
  as invented answers. Strict refusal counts only an explicit UNKNOWN.
- A preview model with light post-training focused on agentic coding, as its card says.
