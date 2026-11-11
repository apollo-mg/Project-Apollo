# RESULT: the Qwen 4 kit reproduces a hand-run arm byte for byte through a generated chain

**What was tested (2026-11-11):** the Abstend pipeline after the release-day additions (`build_engine.sh`, split GGUFs
and disk staging, `scaffold`, `fetch`, the `sampled` mode and the fixed mode order; commits `36115218`..`da7400aa`).
Recipe `qwen3.5-9b-kite2e.json` and its generated prereg and `chain_194.sh` were committed before the run; launched
with the generated launch line; log `state.log`.

**Setup:** the hand-run sci-distill arm Q35B (Qwen3.5-9B, our Q8_0 conversion, sha256 `f904644b...`, llama.cpp
`67107ac34f` build_sm60, `-ngl 99 -c 16384 -ctk f16 -ctv f16 -np 1 -fit off --jinja --cache-ram 0`, one P100, greedy,
thinking off) replayed as Q35BK, staged through the NEW disk path (`engine.weights: disk`: checked at the store,
copied to `~/AI/Models/abstend` on .194, checked again there). The server loaded on GPU 0 alone with 9,017 MiB, as the
hand run did.

## Results

- **Greedy, the acceptance criterion: Q35BK vs Q35B, `abstend.py compare` -> 240 of 240 items; content 0 differ,
  finish 0, grade 0, P_abs 0 (tolerance 1e-6).** The pipeline adds explicit neutral penalties the hand run did not
  send; the chain's defaults audit found responses identical with and without them on this build, and the replay
  confirms it.
- **Sampled (bonus): Q35BKS vs Q35BS -> also 240 of 240; content 0 differ, finish 0, grade 0, P_abs 0.** The hand-run
  Q35BS ran as four shards at `-c 20480`; with fixed per-item seeds at `-np 1`, neither the context size nor the
  sharding changed a single sampled reply.
- The first IPMI call to .194's BMC failed ("Unable to establish IPMI v2 / RMCP+ session") and the power-on still
  went through (SSH up after 231 s); transient, noted for the observer agent's checks.

## What it covers and what it does not

Covered end to end: the launch guard on committed files, store-side hash check, disk staging on an ssh host,
single-GPU placement through `engine.env`, the defaults audit, smoke gates, the greedy and sampled modes in order, the
scorecard rebuild, the host power cycle. Not covered by this run: split GGUFs on a real host (covered by tests with a
rendered chain), `fetch` against huggingface.co (covered by tests with a local server; `scaffold` was run live on three
repos), `build_engine.sh` for sm60 (its gfx1201 path was run; the sm60 path is the configuration of the earlier
`ripple/build_67107ac_sm60.sh`).
