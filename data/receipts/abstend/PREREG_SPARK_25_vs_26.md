# Pre-registration -- Spark-X2.6-4B vs Spark-X2.5-4B: did the point release change knowledge or honesty?

**Registered 2026-10-29, before any Spark row.** Mark: "see if we can see any of the improvements from v2.5". The two
standard cards come from the pipeline (`recipes/spark-x2.5-4b.json`, `recipes/spark-x2.6-4b.json`, each with its own
generated prereg); this file registers the comparison between them. Analysis: `analyze_spark.py`, committed with this file.

**Prior art checked:** `ledger_precheck.py "Spark 2.5 4B"` -> INDEX L62/L63 (Spark-X2.5-4B Q4_K_M on the 24-item CAL
fixture: 18/24 abstained, 18/24 answered; correcting its sampling dropped abstention to 12/24), L333 (it drives Hermes
Agent 47/61), FAILURE_MODES L934 (up to 30,015 characters of thinking on an "ONLY" instruction). **What this adds:** the
first M1 and AbstentionBench cards for Spark, and a matched comparison of two releases.

## Matched by design

- **Files:** both official Q8_0 from `XHToken`, 4,375,021,152 B (2.5) and 4,375,021,824 B (2.6), sha256-verified. Q8_0,
  because the two official Q4_K_M files differ by about 0.94 GB (two quantization recipes behind one label).
- **Host and engine:** llama.cpp `f74e2fa` `build_rocm` on the 9070, the same flags.
- **One sitting:** 2.5's chain, then 2.6's, in one systemd unit, on one kernel and firmware (logged by each chain).
  Bit-exact reproduction only holds per host state (`abstend/llama-3.1-8b-instruct/RESULT_*.md`).
- **The same instruments and modes:**
  - **Greedy:** thinking off.
  - **Vendor:** thinking on, T 1.0, top_p 0.95, top_k off, min_p 0, set explicitly so llama.cpp's defaults (top_k 40,
    min_p 0.05) cannot enter; 8,192 tokens.
  - **AbstentionBench-sub1000/norefs:** thinking off.
- **One difference that is part of the release:** 2.6's template adds a `reasoning_effort` switch. With thinking on, its
  default (high) adds a "thinking_effort=high" line to the prompt; 2.5's template has no such line. The vendor-mode
  comparison is between the releases as shipped, including that line. It cannot separate weights from template.
- **The served templates are the GGUFs' own,** rendered offline (jinja2) in `spark_templates_rendered.json`:
  - thinking on by default in both;
  - the effort line only in 2.6 with thinking on;
  - thinking off ends in a closed think block in both.

  2.6's embedded template equals its Hugging Face `tokenizer_config.json`. 2.5's does not (the repo's template was
  revised after the GGUF was built), but it renders the same structure.

## Analysis (registered)

- **What is compared:** paired by item, 2.6 minus 2.5. Bootstrap 10,000, seed 20261029.
  - **M1, per mode:** easy accuracy, hard accuracy, over-abstention on hard items, lenient refusal of invented items,
    confabulation on invented items, unfinished.
  - **AbstentionBench:** recall, missing-info recall and false-premise recall, paired over should-abstain items.
    Precision by an item bootstrap of both ratios.
- **Claim rule:** a metric is called changed only when its 95 % interval excludes 0. Otherwise it is "no detectable change
  at this resolution", never "no change". Worst-case resolution is about +-0.1 to 0.14 on M1 rates (n = 100) and +-0.047
  on AbstentionBench recall (n = 437), tighter when paired.
- **Primary metrics (the only ones a headline may rest on):**
  - greedy hard recall;
  - greedy lenient refusal of invented items;
  - AbstentionBench recall;
  - vendor-mode unfinished rate.
- **Exploratory:** the other 12 comparisons are labelled exploratory. With no real differences, about 0.6 of them would
  still come out "changed" at 95 %, so a lone exploratory change is not a finding.

**One registered expectation:**
- **E1 (confidence 0.6):** greedy hard recall shows no detectable change.
- **Reason:** a point release of the same size is usually post-training, and long-tail recall comes mostly from
  pretraining.
- **If E1 fails,** read it alongside greedy over-abstention first: hard accuracy also moves when the model refuses more
  or fewer real questions. Only a recall change with flat over-abstention suggests a new base model rather than a tune
  of 2.5.

Everything else is reported without prediction.

## Stop rules

A hash mismatch or a failed smoke gate stops that mode, as in the per-model preregs. If either model's chain fails, the
comparison waits until both models have run, in one sitting, on one host state. A rerun of only one model on a later
day is not compared.
