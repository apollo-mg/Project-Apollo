# A prose fine-tune does not cost agentic judgement — Hemmingway-1 vs stock Qwen3.8-27B

**2026-09-22. `.194`, 4x Tesla P100, buun `build_sm60_0920`, arms concurrent on GPUs {0,1} / {2,3},
`-sm tensor -c 65536 -ctk f16 -ctv f16 -np 1`, `reasoning_effort: medium`.**
Corpus `families_v4.json` (40 items: 9 gate, 31 scored). 4 reps per arm. Raw:
`raw_hemmingway_A_stock_q5km.jsonl`, `raw_hemmingway_B_hemm_q5km.jsonl`.
Analysis: `tools/argus_reps_compare.py` (self-checked against `RESULT_NOISE_FLOOR.md`).

## Headline

**The two models disagree with each other no more than each disagrees with itself.**

| in-run discordance, all rep-pairs | within stock | within Hemmingway | **between** |
|---|---:|---:|---:|
| noise-floor void rule | 11.2 % (20/178) | 11.6 % (20/172) | **10.7 % (50/469)** |
| judge void rule | 14.5 % (27/186) | 15.8 % (29/183) | **13.8 % (68/492)** |

That is the null result measured **inside one run, under identical conditions**, rather than
against an external single-sample floor. Between-arm disagreement sits at or below the
within-arm disagreement, which is what "no model difference" looks like.

| per-item pass rate, paired over 31 items | stock | Hemmingway | diff (H - S) | 95 % CI | p |
|---|---:|---:|---:|---|---:|
| **all 4 reps, noise-floor rule (primary)** | 76.9 % | 76.5 % | **-0.5 pp** | **[-5.9, +4.8]** | 0.84 |
| all 4 reps, judge rule | 75.0 % | 74.0 % | -1.1 pp | [-7.0, +4.8] | 0.71 |
| reps 1, 3, 4 (rep 2 excluded) | 76.9 % | 77.8 % | +1.1 pp | [-4.8, +7.0] | 0.71 |

Bootstrap CIs agree with the t intervals to within a point. Five items favour each arm, 21 tie.

**Answer to the question the run was built for: at 95 % confidence, a prose fine-tune moves agentic
judgement on this corpus by less than about 6-7 points in either direction, and the best estimate
is zero.** That bound is tighter than the 10-point resolution the rep-sizing analysis targeted,
because per-item rates over 4 reps average the sampling noise down and stable items tie exactly.

## The act/ask balance did not move either

The corpus was built to separate *acting on too little* from *asking about everything*, so a flat
total could hide opposite shifts. It does not:

| non-gate, reps 1-4 | expected | stock | Hemmingway |
|---|---|---|---|
| 15 action items (60 item-reps) | act | CORRECT **58**, WRONG-INACTION 1, WRONG-ACTION 1 | CORRECT **58**, WRONG-INACTION 2 |
| 14 ambiguous items (56 item-reps) | ask | CLARIFIED **30**, **WRONG-ACTION 26** | CLARIFIED **28**, **WRONG-ACTION 26**, INFRA 1, NO-ATTEMPT 1 |
| 2 answer-only items (8 item-reps) | answer | CORRECT 5, SUSPECT 2, NO-ATTEMPT 1 | identical |

**Both models act on exactly 26 of 56 ambiguous requests where they should have asked.** The
fine-tune changed neither the over-action rate nor anything else visible.

### Where the instrument's signal actually lives

Action items sit at ceiling (58/60 for both). **Nearly all discriminating variance is in the 14
ambiguous items**, where Qwen3.8-27B over-acts about 46 % of the time. Two consequences:

- The real finding about the base model is that over-action rate, not the pass rate.
- **Corpus effort should go to ask-items.** The 15 action items are doing almost no work for
  comparisons between competent 27Bs; they matter as gates and as a floor for weaker models.

## The in-run noise floor re-measures `RESULT_NOISE_FLOOR`

That receipt put the floor at **10.3 % from 29 pairs** and flagged its own weakness: *"3 discordant
pairs is itself a noisy estimate of noise."* Four reps per arm yield ~175 within-arm pairs each:
**11.2 % and 11.6 %.** The published figure held up.

**But its void rule disagrees with the judge, and that is worth knowing.** Reconstructing it from
raw showed it voided `NO-ATTEMPT` along with `INFRA` / `TOOL-FAIL` / `SUSPECT`. `driver.judge()`
calls `NO-ATTEMPT` *"a real failure -- the tool was there and unused."* Under the judge's own
semantics the same run gives **4/31 = 12.9 %**, not 10.3 %, and voiding also biased both arm rates
upward (both dropped items were one arm's failures: 77.4 % becomes 82.8 %). Both rules are reported
throughout here; the conclusion is identical under either.

That analysis was done inline and never saved, which is why it had to be reverse-engineered.
`tools/argus_reps_compare.py` now exists, prints both void rules, and states in its docstring that
it reproduces the published floor cell for cell.

## Rep 2

Same-index rep discordance was 6.7 %, **24.1 %**, 3.4 %, 6.7 %. Rep 2 is Hemmingway's low draw
(67.7 % vs 80.6 / 71.0 / 74.2 %). At 31 items a single rep's rate has a standard deviation of about
8 points, so this is under one sd, and it is not a progressive slide.

Rep 2 was also **slower in both arms** (median 102 s vs 82-91 s for stock, 95 s vs 73-79 s for
Hemmingway), coinciding with heavy model loading on the desktop, where the driver and agent run.
That plausibly slowed the agent side; it should not change what `.194` samples. **Excluding rep 2
entirely does not change the conclusion** (third row of the table above). The same-index pairing
is also the weaker estimator; the all-pairs in-run floor is what the headline uses.

## Configuration, and what "as shipped" means here

| | stock | Hemmingway |
|---|---|---|
| file | bartowski `Qwen3.8-27B-Q5_K_M` | bartowski `Altworld_Hemmingway-1-Q5_K_M` |
| bytes | 20,923,877,088 | 20,923,877,440 |
| tensors / blocks | 866 / 65 | 866 / 65 |
| effective sampling (`/props`) | temp 1.0, top_k 20, top_p 0.95, **min_p 0.05**, presence 0 | identical |

The files are 352 bytes apart and structurally identical, so **the fine-tune is the only variable.**
Sampling was held constant, and it is also each vendor's own recommendation: Hemmingway's
`generation_config.json` gives temp 1.0 / top_k 20 / top_p 0.95, the same as Qwen3.8's.

**The one deviation: `min_p` 0.05** (llama.cpp's default, inherited because neither GGUF embeds it).
Qwen3.8's card specifies 0.0; Hemmingway's is silent. Shared by both arms, so the comparison is
matched (`AFM-42` audit), but **the absolute pass rates are off Qwen3.8's card** and must not be set
beside a vendor-sampled run.

## Caveats

- **4 reps, not 5.** Rep 5 was lost when a redundant pattern kill during unrelated work took down
  both arms' drivers mid-rep (A had 20/40, B 31/40). Reps 1-4 are complete, paired, and duplicate-
  free; rep 5 is excluded entirely because a partial rep is the first-processed items, not a random
  subset.
- One corpus (31 scored items, 9 families), one quant (Q5_K_M), one harness (Hermes via ACP), one
  effort level (`medium`, which per `[[qwen38-effort-is-a-prompt-edit]]` injects nothing).
- "Agentic judgement" here means **act-vs-ask under referent, scope, time, and premise ambiguity
  with a fake Google workspace.** It says nothing about coding, long-horizon tasks, or tool-call
  formatting, and nothing about whether Hemmingway is a better *writer*, which is what it is for.

## Predictions

The run was launched autonomously; the session summary recorded the decision rule but no
confidence-scored prediction table was written before it, so none is claimed here. The standing
rule was: nothing smaller than a 10-point effect may be claimed. **This result claims an upper bound
of about 6-7 points, not a difference, which is inside that rule.**
