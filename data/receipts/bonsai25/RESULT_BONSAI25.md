# RESULT: PrismML's agentic retrain made Ternary Bonsai more careful, not bolder -- Bonsai 2.5 declines 62 of 100 invented questions against Bonsai 2's 44, knowing the same few facts; same binary, same day, and Bonsai 2 replayed its September run 240 of 240

**Prereg:** `PREREG_BONSAI25.md` (`5a573344`, before any M1 row). **Run:** 2026-11-27 00:05-00:23 EST, desktop RX 9070 XT,
PrismML `9a9394a89` build_hip (the BONB9 binary) on the ROCm 7.2.4 runtime via `tools/rocm724.sh`; PQ2_0 files; M1,
thinking off, greedy, 1,024 tokens. **Records:** `quant-abstention/raw/main_BON2R.jsonl`, `main_BON25.jsonl`; `raw/`
(state, server, run and smoke logs). **Analysis:** `analyze_bonsai25.py` -> `summary.txt`, `RESULT_bonsai25.json`.

## Gate

**G1 passes:** Bonsai 2 today gave the same answer text as on 2026-09-28 (BONB9) on 240 of 240 items. The desktop
instrument, on this binary and runtime, is unchanged by the 11-24 OS update.

## Results (M1, bare-answer rule)

| | Bonsai 2 (BON2R) | Bonsai 2.5 (BON25) | 2.5 - 2, 95 % CI | Qwen3.8-27B Q8_0 (DR27_N73, .73, context) |
|---|---|---|---|---|
| invented declined (of 100) | 44 | **62** | **+0.18 [+0.09, +0.27]** | 59 |
| invented answered | 56 | **36** | **-0.20 [-0.29, -0.11]** | 39 |
| hard right / wrong / declined | 18 / 76 / 5 | 20 / 69 / 8 | right +0.02 [-0.04, +0.08] | 48 / 49 / 3 |
| easy right (of 40) | 23 | 21 | -0.05 [-0.175, +0.075] | 33 |
| unfinished (1,024-token cap) | 2 | 6 | | 2 |
| slot P(UNKNOWN), invented, mean | 0.62 | **0.93** | **+0.30 [+0.25, +0.36]** | 0.70 |
| median output tokens | 30 | 62.5 | | 58.5 |

| prediction | result |
|---|---|
| H1 Bonsai 2.5 declines fewer invented questions (0.55) | **fails, the other way:** 62 vs 44 |
| H2 hard right within 5 (0.6) | **holds:** 20 vs 18 |

Per item (exploratory, written after the registered results): on invented questions 21 made-up answers became declines
and 3 declines became made-up answers; on hard questions 7 wrong answers became declines, 4 declines became wrong, 6
wrong became right and 3 right became wrong. Neither model shows the trailing-UNKNOWN habit (2 and 0 rows,
`olmo3-ladder/hedge_counts.py`'s rule).

## Reading

1. **The agentic retrain raised caution.** Bonsai 2.5 declines 18 more invented questions and makes up 20 fewer answers.
   The forced answer slot, read before the model writes anything, moved the same way (0.62 -> 0.93 probability of
   "UNKNOWN" first), so this is not only a longer written style: the model's first instinct changed.
2. **It knows no more.** Hard right 18 -> 20, easy right 23 -> 21: the ternary 27B still knows far fewer facts than
   Qwen3.8-27B at Q8_0 (48 hard right). Bonsai 2.5 now declines invented questions as often as that model (62 vs 59)
   while knowing less than half as much.
3. **It reasons in the open with thinking off.** Every answer starts with prose (Bonsai 2: 209 of 240), median length
   doubled, and the 6 cap hits are visible self-correction ("Wait," "Actually, I think the answer is UNKNOWN").
   Premise checks ("The premise of the question is false") are common.
4. **A decline is not always clean (observation, not counted).** Some declines come wrapped in made-up detail: for an
   invented Kenyan region it said the name is a town in Nandi County and named Nakuru as that county's seat (wrong). The
   grade counts the decline; the surrounding claims would mislead a reader.
5. **Against the prediction:** we expected tuning for tool use and task completion to push toward answering. Here it
   pushed the other way, consistent with the pi adapter on the RL page (an efficiency-rewarded agent learned to stop and
   say "this can't be done"). PrismML has not published the 2.5 recipe, so the mechanism is open.

## Limits

Thinking off only (the card defaults to xhigh reasoning); greedy, where the vendor recommends 0.7 to 1.0; one packing
(PQ2_0) on one machine; M1 is short factual English questions and does not test the tool calling 2.5 was tuned for;
the Qwen3.8-27B row is another machine and engine, for context only.

## Follow-up (2026-11-27, exploratory, after the registered results): why? A closer copy of its teacher

PrismML's two whitepapers (Bonsai 2, September; Bonsai 2.5, November) describe benchmarks, format and kernels, and say
nothing about how either model was trained or about factuality, hallucination or abstention. So the recipe is unknown;
what our data shows is that Bonsai 2.5 behaves much more like its full-precision base, Qwen3.8-27B (two Q8_0 thinking-off
references: DR27_N73 on .73 and C.A; grades only, other machines):

| | Bonsai 2 | Bonsai 2.5 |
|---|---|---|
| same grade as Qwen3.8-27B, invented items (DR27_N73 / C.A) | 74 / 73 | **81 / 81** |
| same grade, all 240 items | 162 / 160 | **173 / 170** |
| Qwen's invented declines (59 / 60) it also makes | 39 / 39 | **51 / 52** |
| declines Qwen does not make | 5 / 5 | 11 / 10 |
| median output tokens (Qwen 58.5) | 30 | 62.5 |

Reading: ternary compression (Bonsai 2) lost about a third of the base model's declines -- the ones Qwen made and Bonsai 2
answered instead -- and Bonsai 2.5 recovered most of them, along with the base model's answer length. PrismML's own tables
show the same direction on their targets (2.5 closer to FP16 on every agentic benchmark, e.g. AppWorld 51.2 -> 90.5 against
93.2). The simplest account is that whatever closed the agentic gap to FP16 also brought back the teacher's caution: a
compression loss repaired, not a new behaviour. It does not account for everything: 2.5 adds about 10 declines of its own,
and its forced-slot probability of "UNKNOWN" (0.93) is above Qwen's (0.70, another engine and machine), so something
pushes it past its teacher; its declines are also longer than its answers (median 83.5 vs 60.5 tokens: premise checks).
This matches our compression data, where low-bit files decline less than Q8_0 of the same model
(`quant-abstention/RESULT_MAIN.md`), and contrasts with the Olmo ladders, where caution moved with the training stage.
