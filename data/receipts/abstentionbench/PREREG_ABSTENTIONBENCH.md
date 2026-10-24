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

## Addendum 1 -- a reference-free judge and a blinded adjudication (registered 2026-10-24, after the gate, before any norefs verdict or adjudication label)

**Observed so far (Arm 1, Llama 3.1 8B Instruct Q8_0, 2,004 items, 0 errors):** gate G passes (mean |dF1| 0.069,
Spearman 0.922 over the 18 unsplit datasets). J1-J3 hold: exact and blind differ on 204 items (0.102), 198 of them
toward the label, mean F1 exact minus blind 0.119.

**What J2/J3 do and do not show.** The flips are symmetric (100 should-answer items moved to "not an abstention", 98
should-abstain items to "abstention"), which is what a label-following judge produces. Because F1 here is agreement
with the label, J3 follows almost mechanically from J2. Neither says which judge is RIGHT; the prompt itself calls the
label noisy, and it could be correcting a noisy blind judge. That is what this addendum tests.

**Finding while reading the items after the gate (no verdicts involved): blind is not blind.** On 12 of the 21
datasets (ALCUNA, BBQ, BB/Disambiguate, BB/Known unknowns, KUQ, MediQ, MoralChoice, QASPER, SelfAware, SituatedQA/Geo,
SQuAD 2.0, UMWP; 1,146 items) an empty reference list marks exactly the should-abstain items, and the prompt tells the
judge to "mostly rely on the [QUESTION] and [REFERENCE ANSWERS] to determine the label". So 0.119 is a lower bound
on what the answer key does to the verdicts there. (The datasets are computed mechanically in `analyze_abench.py`.)

**Deviation 1 (operational).** Attempt 1 was killed at 411 subject rows by systemd-oomd (2026-10-23 22:32): the
server's default 8 GiB host-RAM prompt cache filled even with `cache_prompt: false`, on a desktop already deep in
swap. Rerun from row 1 with `--cache-ram 0`, launched with `systemd-run` outside the session's cgroup. The 411 rows
were discarded, not merged (kept locally in `raw/attempt1_oom/`). Outputs should be unaffected; the cache only stores
states and no request asked for reuse.

### Arm 1c: norefs judge

Same server, same stored responses, Meta's prompt with the label AND the references removed (exact edits in
`judge_abench.py --variant norefs`; the run aborts if either is still named).

| # | prediction |
|---|---|
| N1 | mean F1 over datasets: blind minus norefs >= 0.03 (the reference cue carries label information the judge uses) |
| N2 | blind minus norefs is larger on the 12 ref-leaky datasets than on the other 9 |

### Blinded adjudication: which judge is right where they disagree

- **Frame:** items where the exact, blind and norefs verdicts are not unanimous. 40 per label stratum
  (should-abstain, should-answer), at most 4 per dataset per stratum, plus 10 unanimous controls per stratum (at most 2
  per dataset); seed 20261024; drawn once by `adjudicate.py sample`.
- **Adjudicator:** Claude Opus 5.5 (the model running this session), shown only the question and the model's answer (over
  3,000 characters: first 1,800 + last 1,000), in shuffled order, with no label, references, verdicts or dataset name.
  It decides by Meta's own definition of abstention (the norefs prompt text) and may mark an item unclear. Labels are
  written to `raw/LLAMA8.adj_labels.jsonl` before the key is opened. It is a stronger model than the judge, not a human;
  that is a stated limit.

| # | prediction |
|---|---|
| A1 | on disagreement items, the norefs verdict agrees with the adjudicator at least as often as the exact verdict |
| A2 | on unanimous controls, the adjudicator agrees with the unanimous verdict on >= 0.9 of items |

**Decision rule for later arms (registered now):** the primary judge is norefs, unless exact's agreement with the
adjudicator on disagreement items exceeds norefs' by >= 0.10 (a label-aware judge pulls every arm toward the key, which
compresses differences between arms). Exact is always reported second, for comparability with Meta's tables. If more
than 20 % of the sample is marked unclear, norefs is primary and the adjudication is reported as inconclusive.

**Public repo:** `raw/` stays local (item text; GPQA's terms forbid publishing its examples). Committed: scripts,
aggregates, and a per-item verdict table with no question or answer text.

## Addendum 2 -- Qwen3.8-27B with thinking off vs on (registered 2026-10-24, before any 27B answer on a benchmark item)

**Prior art checked:** `ledger_precheck.py "thinking reasoning abstention refusal 27B"` -> on the M1 instrument, thinking on
lifted Bolt's refusal of invented items 0.16 -> 0.52 (`quant-abstention/RESULT_BOLT_THINK.md`), moved Flint's 0.45 -> 0.39
(n.s.), and Beam's reasoning effort bought nothing. Meta's README states: "reasoning fine-tuning hurts abstention,
resulting in reasoning models that respond over-confidently and rarely abstain." That claim compares fine-tuned reasoning
models with their instruct bases. **What this adds:** the other intervention, thinking switched on and off inside ONE
hybrid model on the same weights, on Meta's benchmark, judged by the instrument Addendum 1 selected.

**Subject:** Qwen3.8-27B Q6_K as served daily on .73 (buun `510cbbbfa`, VBR KV, MTP draft 3, `-np 2`), reached through
the wake proxy (one stream, so Hermes keeps the other slot; requests marked `x-apollo-guest`). Not seed-reproducible in
general (VBR np 2 is bistable); sampling is at T 0.8 anyway.

| arm | how |
|---|---|
| Q27OFF | chat endpoint, `enable_thinking: false`, max_tokens 4,000 (Meta's non-reasoning settings) |
| Q27ON | Meta's reasoning protocol (`VLLMReasoningChatModelBase`): reasoning up to 4,000 tokens, stopped at `</think>` or cut and closed; then the answer up to 4,000 tokens. `reasoning_effort: "medium"`, the only value verified (via `/apply-template`, 2026-10-24) to add no system text; `xhigh`/`high` inject "validate key assumptions..." |

Both: T 0.8, top_p 0.95, no system prompt, `cache_prompt: false`. **Deviation from Meta, stated now:** no `Final Answer: `
prefix on Q27ON's judged text, so the judge sees the same kind of input from both arms. Plumbing checked on two
non-benchmark questions only (`run_q27_pairs.py`).

**Order and stopping rule:** each item runs OFF then ON back to back, items in a seeded random order (20261024), so both
arms share server state and a stopped run leaves a random sample. Stop at all 2,004 pairs or 2026-10-26 12:00 EDT,
whichever comes first. Analysis uses completed pairs only (both arms answered, both verdicts parse). Estimated ~50 h at
~21 tok/s.

**Judges:** norefs (primary, per Addendum 1's rule) and exact (second): Llama 3.1 8B Instruct Q8_0 on the 9070, the same
build and flags. **Analysis:** `compare_arms.py`, paired bootstrap over items within datasets (10,000 resamples).

| # | prediction |
|---|---|
| R1 | Meta's direction applied to the toggle: under norefs, thinking ON lowers pooled recall (abstention on should-abstain items) by >= 0.05, CI excluding 0. Our own Bolt result points the other way. |
| R2 | the key-reading judge compresses the arm difference: \|ON - OFF mean F1\| under exact < under norefs |
| R3 | median reasoning tokens are higher on should-abstain items than on should-answer items (Bolt: refusals thought ~4x longer) |

Reported regardless: forced reasoning cuts by label, Q27OFF rows carrying any reasoning (more than 1 % invalidates that
arm), errors, and per-dataset F1 for both arms. `raw/` stays local as before.
