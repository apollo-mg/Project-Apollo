# PREREG: SenseNova-Loop-9B at 1, 2 and 3 loops on M1 -- does more depth buy facts or caution? (2026-11-25, before any M1 row or reference number at 1 or 3 loops)

**Why (Mark, 11-23 and 11-25):** the loop count as a dial, "a perfect substitute for reasoning effort, or at least more
granularity". GLM-5.4's iso-parameter ablation (their blog, 11-24) gained most on reasoning benchmarks (AIME +11.3, GPQA
+8.7) and least on the knowledge-heavy MMLU-Pro (+3.4), with shorter outputs; SenseNova's card shows benchmark peaks at
3-4 loops. Nobody has reported what the loop count does to factual recall and to declining invented questions. **Prior
art checked:** `ledger_precheck.py "loop count dial looped depth abstention"` -> only our SenseNova result at its trained
count (`../RESULT_SENSENOVA_LOOP.md`): hard right 14, invented declined 53. **What this adds:** the same weights at 1, 2
and 3 loops.

## Files and setup (built and checked before this prereg)

- `rewrite_loops.py` rewrites the official Q8_0 for another loop count: block count, loop count and the per-layer
  attention list in the header, the four tail blocks and the MTP block renamed to their new logical indices; the 9.8 GB of
  weights are copied byte for byte. **Self-test passed:** asked for 2 loops it reproduces the original file exactly (sha256
  `0db6188d...`). 1 loop: sha256 `45fd78ba...`; 3 loops: `cc713d9c...` (`rewrite_log.txt`).
- **Seen before this prereg** (llama.cpp PR 32588 `4bc61eed7` build_rocm, the 7.2.4 runtime via `tools/rocm724.sh`,
  wikitext-2, `-c 512`, 20 chunks): perplexity 44.11 at 1 loop, 17.54 at 2 (the original's value exactly), 20.61 at 3.

## Gate: the port at 1 and 3 loops against the reference

SenseTime's `modeling_sensenova_loop.py` with `loop_settings.counts = [n]` and `eval_count = n` (a config copy; the
weights are the same files), FP32 on .194's CPUs, the same 20 chunks, scored as `llama-perplexity` does (`../ref_ppl.py`).
Accept a count if the reference is within 5 % of llama.cpp's value above; at 2 loops this was 0.999 (`../RESULT_SENSENOVA_LOOP.md`).
A count that fails gets no M1 claim.

## Arms (desktop RX 9070 XT, old `4bc61eed7` binary on the 7.2.4 runtime, as the 11-23 SNL arm; flags as SNL)

`SNL_L1`, `SNL_L3` (the rewritten files) and `SNL_L2R` (the original file again: a replay that must match the 11-23 SNL arm
240/240, or the setup has drifted and the comparison stops). M1 240 items, greedy, thinking off, `run_main.py --max-tokens
1024 --usage`; bare-answer rule.

## Predictions (S2 = the 2-loop numbers: hard right 14, invented declined 53)

- **D1 (fewer loops than trained hurt):** hard right at 1 loop is at most S2's 14. Confidence 0.7.
- **D2 (more loops buy no facts):** hard right at 3 loops is at most 14 + 3. Confidence 0.75.
- **D3 (exploratory, no direction):** invented declined at 1, 2 and 3 loops, with paired differences against 2 loops
  (bootstrap over items, 10,000, seed 20261125); also wrong answers, unfinished items, output tokens and decode speed.

## Limits stated now

One model, trained at 2 loops, so 1 and 3 are off its training distribution (as in SenseTime's own loop-scaling figures);
greedy, thinking off; M1 is short factual English; one quant.
