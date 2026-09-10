# PREREG — can a 2.42 GiB 4B drive Hermes Agent?

**Written 2026-09-07 before the run.**

## Setup

`hermesbench run --all --toolsets all`, 61 tasks, against `Spark-X2.5-4B-Q4_K_M` served locally
on the RX 9070 XT (`XHToken/llama.cpp` `4a3635c32`, `-c 65536 -np 1 -fa on`, port 8086).
Explicit `--model` / `--base-url`; **never `--use-hermes-config`**, which resolves to a paid
cloud endpoint (documented in `run_v5_det03.sh`).

**Baseline for orientation, not a control:** `Hermes3.6-35B-A3B-Genesis-V5-APEX` on `.73`
scored **55 / 57 / 56 of 61** across `v5_det02`, `v5_det03`, `v6_det01`. Different vendor,
different size class, different serving stack — `AFM-30` applies and no "4B matches 35B" claim
can come out of this regardless of the number.

**Why this is a real test rather than a bigger version of the tool probes:** the suite loads
**29 tool schemas**, pushing turn 1 to ~13k tokens. Every tool result in
`RESULT_SPARK4B_TOOLS.md` used ~100-token prompts. Schema-count and context pressure are
exactly where small models are expected to degrade, and nothing measured so far touches it.

## Predictions

| # | prediction | conf |
|---|---|---:|
| H-1 | It completes the suite without infra errors — i.e. it can be driven at all | 0.65 |
| H-2 | ≥ 30 / 61 passed | 0.55 |
| H-3 | < 55 / 61 — below the 35B baseline's floor | 0.85 |
| H-4 | Failures concentrate in multi-step/stateful tasks rather than single tool calls, matching the `sysadmin-corpus` finding that emitting calls ≠ choosing them | 0.60 |
| H-5 | Wall-clock per task is well under the P100 baseline's — Spark prefills ~1670 t/s vs the ~148 t/s that forced `--timeout-overhead 300` | 0.80 |

H-1 is the question actually asked. H-3 is deliberately near-certain and is there to keep the
framing honest: this is not a competition with a 35B.

## Stopping rule

One pass, 61 tasks. Score whatever completes; report infra errors separately from failures.

## AMENDMENT 2026-09-07 ~20:05, mid-run — SAMPLING IS OFF-CARD

**This run, and every other Spark run today, used `top_k=20`.** That is Qwen3.8's card value,
inherited from `run_fixture.py`'s hardcoded `card` preset:

    "card": {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "presence_penalty": 0.0}

**Spark-X2.5's card specifies `temperature=1.0, top_p=0.95, top_k=-1`** — no top-k filtering.

Why it plausibly matters: with `top_p=0.95` *and* `top_k=20` the candidate set is the
intersection. At low-entropy positions nucleus filtering already admits fewer than 20 tokens and
top-k never binds. At **high-entropy positions** — where an uncertain model decides whether to
abstain, and where a search either terminates or runs away — `top_p=0.95` can admit far more
than 20, and `top_k=20` truncates it. The model was run more deterministic than intended in
precisely the regime under study.

**Affected:** `RESULT_SPARK4B_TIERCAL.md`, `RESULT_SPARK4B_TOOLS.md`,
`RESULT_SPARK4B_STRUCT.md`, and this run.

**Bounding the damage:** the tool (24/24) and struct (18/18) results are ceilings — different
sampling can only move them down, so "it can do parallel tool calls and JSON" survives.
`tier_cal`'s 18/24 abstention is the number that most needs re-running at `top_k=-1`.

**Decision:** this run continues to completion and is labelled *Spark at Qwen's sampling*, which
is what it measures. It is not labelled as the model's card configuration.

**Fixture issue this exposes:** a preset named `card` is only "the card" for the model it was
written for. It should be per-model, or renamed `qwen_card`, so reuse on another model is
visibly wrong rather than silently wrong.
