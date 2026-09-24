# Pre-registration — Hemmingway-1 vs stock Qwen3.8-27B on technical writing (swap decision for .73)

**2026-09-24, written before any generation.** `.194`, 4x P100, buun `build_sm60_0920` (`08826ad6e`),
`~/start_arm.sh` flags (`-c 65536 -sm tensor -fa on -ctk f16 -ctv f16 -np 1 --jinja`,
`reasoning_effort: medium`). Tasks: `tasks.json` (built by `build_tasks.py` from real repo material; the
sources are frozen into the JSON). Runner: `run_techwriting.py`.

## Question

Mark is considering replacing the daily driver on `.73` (stock Qwen3.8-27B Q6_K) with Altworld's
Hemmingway-1, which people praise for how it writes. Its card claims "the best everyday messages". Is it
at least as good at **technical** writing? That is the daily use here: receipts, issues, docs and
summaries. And does it keep writing faithful diary entries, since the ledger's diary writer runs on
`.73`'s model?

**Prior art checked:** `ledger_precheck.py "Hemmingway writing tune technical writing verbosity"` ->
- `argus-v2/RESULT_HEMMINGWAY_VS_STOCK.md`: agentic judgement unchanged, and replies 23 % terser.
- `RESULT_HEMMINGWAY_BREVITY.md`: the terseness is intrinsic, not prompt compliance.
- AFM-42: GGUFs embed sampling defaults, so sampling is pinned per request here.

**What this adds:** technical-writing quality and faithfulness, which was never measured, and the
production diary task.

## Arms

| id | file | role |
|---|---|---|
| `S5` | bartowski `Qwen3.8-27B-Q5_K_M.gguf` (20,923,877,088 B) | stock, matched quant |
| `H5` | bartowski `Altworld_Hemmingway-1-Q5_K_M.gguf` (20,923,877,440 B) | the tune, matched quant (352 B apart) |
| `S6` | `Qwen3.8-27B-Q6_K.gguf` (22,884,408,288 B) | stock at the daily driver's quant: **mechanical metrics only** |

`S5` vs `H5` isolates the tune. `S6` vs `S5` shows how much the quant moves the mechanical metrics. If
that is small, the matched result transfers to the actual Q6 swap. (bartowski also publishes a
Hemmingway Q6_K; it is not downloaded because `.194` has ~28 GB free.)

**Identical per request:** temperature 0.6, top_p 0.95, top_k 20, min_p 0, presence 0 (Qwen card; the
Hemmingway card gives none), `max_tokens` 8000, fixed seed per task, thinking on at medium effort, one
sample per task per arm. **Gate G1:** `/props` `chat_template` of `S5` and `H5` compared before
generating. A difference is recorded, and the templates are not swapped (as shipped).

## Tasks (23)

- 4 **summaries** of real receipts, for a blog audience;
- 4 **bug reports** from fact lists;
- 4 **docs** of real functions from this repo;
- 4 **explain** a concept (no source), each with pre-written key-fact and misconception regexes;
- 4 **clarity** rewrites of real failure-mode entries;
- 3 **ledger** entries: real 300-event windows from this session, run through `tools/ledger_build.PROMPT`
  unmodified. `L1-incident` is the window that produced the 09-23 invented cause.

## Metrics (mechanical, fixed now)

- **Invented numbers** (summary, bug, clarity tasks): numeric tokens in the answer that are absent from
  the source.
  - Normalization: thousands separators removed, trailing `%`/`x` stripped.
  - Ignored: list ordinals at line start (`1.`, `2)`), single digits 0-9 on their own, and 4-digit years
    2000-2099.
  - Derived numbers (computed ratios etc.) **count as invented** and are listed for inspection.
- **Invented identifiers** (bug, docs tasks): backticked tokens absent from the source.
- **Explain tasks:** key-fact regex hits (higher is better) and misconception regex hits (lower is better).
- **Ledger tasks:**
  - `tools/ledger_build.annotate_unverified` tag count against that window's events (lower is better);
  - `ledger_validate.classify` must pass;
  - headings must be level 3 or lower.
- **Termination:** empty content or `finish_reason: length` is its own bucket, never scored as a quality
  loss or gain.
- Length (words) and reasoning length, descriptive.

## Mark's blind rating (S5 vs H5, the 20 writing tasks)

A page shows each task's two answers as A/B, with the side randomized per task. The mapping stays local
and is not in the page or its data until rating is done. Per task: **prefer A / B / tie**, plus **"which
do you think is Hemmingway?"** The length leak is expected (H5 is ~23 % terser). Preference is reported:
- overall;
- split by whether the guess was right;
- against length difference.

If the guesses beat chance, the result is labelled an unblinded preference.

## Decision rule (all four for "swap")

1. **Preference:** H5 wins more decided tasks than S5 (ties excluded). Exact sign test reported; ~15/20
   needed for p < .05, so "wins more" is the operative bar, not significance.
2. **Faithfulness:** H5 invented numbers + identifiers ≤ S5's + 2 (summed over tasks).
3. **Explain:** H5 key facts ≥ S5 - 2, and misconceptions ≤ S5.
4. **Diary:** H5 unverified tags ≤ S5 across the 3 ledger tasks, and classify passes on all 3.

Otherwise the report says which condition failed, and the recommendation is "keep stock". Mark decides.

**Prediction:** preference favours H5 (0.55); faithfulness non-inferior (0.65); diary non-inferior (0.6).

**Publication note (before generation):** the 3 ledger windows contain Mark's chat, including pasted
third-party Discord posts. `tasks_private.json` (full, local, gitignored) is what the models see. The
public `tasks.json` carries the 20 writing tasks in full, and only a sha256 and size for each ledger task.
Ledger outputs go to gitignored `raw/*_ledger.jsonl`; only their scores are published.
