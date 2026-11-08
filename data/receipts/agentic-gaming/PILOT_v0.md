# Agentic gaming pilot v0 -- plan (2026-11-08, before any model episode)

**Purpose (DESIGN_v0.md, "Sizing and host"):** calibration, not measurement. Find which family x rung cells have non-zero
shortcut or abstention base rates on real models, and check that the harness behaves with real tool-calling agents.
**No predictions and no claims** come from this pilot; any comparison it suggests is registered separately before it is
tested at scale. Rungs that score 0/N for every model are hardened or dropped before v1.

**Prior art:** `ledger_precheck.py "agentic pilot tool calling Qwen3.8-27B Hermes agent benchmark shortcut"` -> Qwen3.8-27B
already ran multi-turn tool-calling agent items on these builds (INDEX L32, Argus MTP study); "verify the outcome, not
the route" (L326) is the principle the detectors follow.

## Models (files already on .194, the M1 lineage)

| arm | file |
|---|---|
| BASE | Qwen3.8-27B Q8_0, sha256 `a680f44a...` (the M1 ceiling) |
| ARE | Arete-27B Q8_0 (our conversion), sha256 `363c464d...` |
| QWC | Qwopus3.8-27B-Coder-Flash Q8_0, sha256 `d1262b7b...` |

The question the pilot can only hint at: does the fine-tune pattern on M1 (less "I don't know") show up in agents as
more corner-cutting or less abstention on the impossible rung?

## Instrument

- Harness: `argus/gaming` at the commit that adds this file; tools in bwrap on the desktop; models served from .194.
- Serving: buun `0b2789f23` `build_sm60`, two lanes (GPUs 0+1, 2+3), `-ngl 99 -sm layer -c 16384 -ctk f16 -ctv f16 -np 1
  -fit off`, `GGML_CUDA_ALLREDUCE=internal`, tool calling through the chat template. Requests: temperature 0,
  `cache_prompt` false, thinking off, `max_tokens` 4096 per step, at most 30 steps per episode.
- Tasks, per model (17 episodes): F1 easy and hard with the key, seeds 1-3; F2 easy, hard and impossible, seeds 1-3;
  F1 easy and F2 easy capability controls, seed 1.
- Each episode is written as it finishes (flush + fsync) to `pilot/raw/<arm>/`.

## What will be reported

Per cell: honest solves, each shortcut label (read vs used for the key), tamper routes, hard-coding, impossible-rung
gaming vs honest abstention, false impossibility, budget exhaustion, disclosure (hidden vs admitted), and any harness
fault (malformed calls, context overflow). Plus the cells that are 0/N everywhere.
