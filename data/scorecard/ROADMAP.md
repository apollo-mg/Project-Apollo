# Abstend roadmap

Independent, receipts-first scorecards for the models people actually run: the specific file, quant and server
settings, not the lab's full-precision API. The scorecard is the dyno sheet, not the brochure.

## Milestone 1: the pipeline (new model in, scorecard out within a day)

- One command takes a model file (and its serving recipe) and runs the standard gamut: M1 (knowledge and honesty),
  the AbstentionBench subset with the norefs judge, and speed on the target host.
- Every run is preregistered by the pipeline itself: the recipe, file hash, host, clocks and instrument versions are
  written and committed before the first answer.
- Results land in `data/scorecard/` through `build_scorecard.py`, and the card page re-renders.
- Hard parts already solved this year, which the pipeline must keep enforcing: thinking off by the template switch,
  explicit sampling and penalties (no server defaults), `cache_prompt: false`, KV flags stated, hashes verified,
  memory-capped units, per-item flush, and kernel interference counted.

## Versioning rule (how data stays comparable while the tests evolve)

- An instrument version is frozen once published (`M1-v1`, `AbstentionBench-fast/norefs`). Any change to items,
  prompts, grader or judge makes a new version. Numbers are never compared across versions.
- When a version changes, an **anchor panel** is re-run on both versions: a fixed handful of reference setups (Qwen3.8-27B
  Q8_0, Beam, Super VL, Flint, Llama 3.1 8B). That calibrates the shift without re-running the whole catalog.
- Every result row already carries instrument, version, config, host and receipt, so the database is compatible by
  construction.
- Errors found in a published instrument are fixed in the next version and noted on the old one; old numbers stay
  as they were, labelled.

## Stated up front, not in fine print

- Which hosts are byte-deterministic at temperature 0 and which are not (Pascal kernels, VBR with parallel slots).
- What each instrument cannot see: M1 is cold recall without tools; AbstentionBench is judged by an 8B model.
- That the corpus is not a gold standard yet, and will change as testing finds its errors.
