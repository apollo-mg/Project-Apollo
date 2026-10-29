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

**Progress.**
- 2026-10-28, step one done: recipes (`recipes/*.json`, `hosts.json`) and `abstend.py` (validate, derive run
  arguments, prereg, launch guard).
  - Acceptance test passed: Nanbeige rebuilt from its recipe gives a byte-identical `scorecard.csv`, and its derived
    run headers match the stored ones field by field.
  - Runaway decision implemented as conditional `*_finished` metrics beside the frozen ones.
- 2026-10-28, step two done: `abstend.py chain` generates host chains (9070 local, .194 over ssh), with a smoke gate
  and a per-run defaults audit.
  - Pipeline run 1 (Phi-4-mini on the 9070) reproduced the hand run `IDK_BPHI` bit for bit on all 240 items, and
    measured `--neutral-penalties` as a no-op (`data/receipts/abstend/phi-4-mini/`).
  - The smoke gate is an echo now: Phi-4-mini says 17*19 = 341.
- Next:
  1. AbstentionBench in the chain: DONE 10-28 (run 2, Llama 3.1 8B). Every stage worked, but bit-exact reproduction
     of the 10-23 run FAILED after the 10-27 system update (kernel and firmware); today's runs replay exactly and the
     card metrics moved < 0.03. Chains now log kernel, firmware and driver.
  2. Speed on the shared harness, added to the chain.
  3. A RESULT writer: the card is automatic, but the receipt prose is still written by hand.
  4. A first .194 run from a generated chain (the Nanbeige render matches the hand chain, but has not run).

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

## Before Qwen 4 (plan agreed 2026-10-28)

Focus where the damage is immediate and irreversible: agents. Knowledge-domain hazards (bio above all) are out of
scope for this compute and this lab.

1. **Pipeline ready for release day.** A Qwen 4 scorecard (M1, AbstentionBench subset, speed per host) within 48 hours
   of the weights appearing. Everyone will publish speed; few will publish honesty.
2. **Agentic instrument v0.** A sandboxed shell with outbound network blocked but logged (DNS and connect attempts),
   preregistered task sets: (a) security-flavoured tasks, as a cheap screen for unprompted egress (a screen, not a rate:
   one-in-100,000 behaviours are beyond this scale); (b) agentic abstention, meaning stop, ask or hand off when
   information is missing instead of acting on an assumption (the 27B's "fill in the missing setup" finding, with an
   irreversible action at stake).
3. **Two public write-ups** (fact sheets from the receipts; Mark writes the prose): the AbstentionBench judge reading the
   answer key (after checking how Meta validated its judge), and thinking that notices missing information then hides it.
4. **Outreach with something in hand.** Each write-up goes to the people it concerns (Meta's AbstentionBench authors,
   Strata's maintainer, eval teams such as Cohere's), as findings and questions, never as claims of safety.

## Pipeline decisions (Mark, 2026-10-28)

- **AbstentionBench as an anchor:** a stratified subset on release day, kept running alongside our own private dataset
  even once that exists. Running a well-known outside benchmark next to ours shows good faith and anchors our numbers.
- **Two modes per model:** greedy (thinking off where the template allows) AND the vendor's recommended sampling (thinking
  on where the model has it). Runaways and other sampling-induced failures are reported as a separate reliability
  metric, never counted against capability.
- **Hosts:** the 9070 for small models and the judge, .194 for big models, .73 only when nothing else fits.
- **Engines are part of the artifact.** The primary card uses a pinned reference engine (upstream llama.cpp). An engine
  conformance track (see below) covers the engines people actually run, starting with spill engines such as Strata.

## Engine conformance track (proposed)

For each popular engine, a small fixed panel on one or two reference models: (a) numerics, meaning greedy text identity
or KLD against the reference engine, with the path-noise control; (b) a defaults audit, meaning what the server silently
adds (sampling, penalties, templates, thinking switches); (c) speed on the shared harness; (d) an M1 subset, to see
whether honesty moves on that engine. Prior art: the Pascal FAST_FP16 KV bug (an engine bug that changed quality) and
Strata's hidden presence penalty (2026-10-27).
