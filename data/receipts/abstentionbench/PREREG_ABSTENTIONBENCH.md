# PREREG -- Meta's AbstentionBench on our hardware: reproduction gate, and does its judge peek at the answer key?

**Registered 2026-10-23, before any model has answered a question.** Code: `export_fast_subset.py`, `run_abench.py`,
`judge_abench.py`, `analyze_abench.py` (committed with this file).

**Prior art checked:** `ledger_precheck.py "AbstentionBench"` -> nothing; our own instrument is
`quant-abstention/` (M1: 240 Wikidata items). **What this adds:** a second, external abstention instrument (Kirichenko
et al., FAIR, NeurIPS 2025; 20 datasets; CC BY-NC 4.0), first run on local quantized deployments, and a test of its
judge.

## Instrument (as Meta runs it, plumbing swapped)

- **Data:** the paper's fast subset, exported with Meta's own dataset classes and configs (`facebookresearch/
  AbstentionBench` `e291841`, `data/fast-subset-indices.json`): 21 datasets, **2,004 items** (870 should-abstain), FreshQA
  excluded (manual Google Sheets export). GPQA (80), MMLU History (78), BB/Known unknowns (46) are full, as in Meta's run.
- **Subject:** the question as the only user message, no system prompt, temperature 0.8, top_p 0.95, max_tokens 4000
  (Meta's `configs/model/*.yaml`); llama-server (OpenAI API), per-item seed; `cache_prompt` false.
- **Judge:** Meta's `LLM_JUDGE_ABSTENTION_COCONOT_STYLE_PROMPT` imported verbatim; Llama 3.1 8B Instruct as Meta uses,
  here bartowski `Meta-Llama-3.1-8B-Instruct-Q8_0.gguf` (sha256 `9da71c45...`, verified; Meta ran bf16 on vLLM); chat
  format, temperature 0, top_p 0.95, max_tokens 100; verdict = reply stripped and lowercased if "yes"/"no", else None.
  The judge sees the final answer only (reasoning excluded), as `USE_RESPONSE_WITH_REASONING = False`.
- **Metric:** precision / recall / F1 with abstention as the positive class, per dataset (sklearn semantics, as
  `analysis/tables.py`); None verdicts dropped and counted.

## Arm 1: reproduction gate (Llama 3.1 8B Instruct as subject)

Subject = the same Q8_0 file, on the RX 9070 XT (upstream llama.cpp HIP build), `-c 32768 -np 1`, F16 KV.
**G (gate):** on the 18 datasets Meta reports unsplit (CoCoNot and KUQ are published only by sub-category, too thin
at 100 items), our exact-judge F1 vs Meta's published `Llama 3.1 8B Instruct` rows: **mean |F1 diff| <= 0.10 and
Spearman rho >= 0.6.** Sampling at T=0.8 on 100-item sets and Meta's larger evaluation sets make exact agreement
impossible; failing the gate means our pipeline does not reproduce theirs, and no new-model arm is reported until
the cause is found.

## Judge leakage (registered here because it was found reading the code, before any run)

Meta's judge prompt shows the judge the **ground-truth abstention label** next to the model's answer ("you can check
them for reference but they can be noisy"). A second pass judges every response with the **blind** prompt: the same
text with the `[GROUND TRUTH ABSTENTION LABEL]: {abstention_label}` line and its two mentions removed (exact edits in
`judge_abench.py`).

| # | prediction |
|---|---|
| J1 | exact and blind verdicts differ on >= 5 % of items |
| J2 | most flips move the exact verdict toward the label (the judge follows the answer key) |
| J3 | mean F1 over datasets is higher with the exact judge than the blind one by >= 0.03 |

## Later arms

New-model arms (the .73 Qwen3.8-27B with thinking off vs on, quant pairs) are registered in an addendum after the gate
result, with the judge variant chosen here.
