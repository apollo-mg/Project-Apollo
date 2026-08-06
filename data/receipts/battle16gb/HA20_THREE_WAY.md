# Battle for 16GB — three-way agentic leg, and what HermesAgent-20 can and cannot measure

RX 9070 XT 16 GB (gfx1201), control plane 10.0.0.5. Date 2026-07-29.
Benchmark: stevibe's BenchLocal **HermesAgent-20**, pinned Hermes `ea74f61d983e`,
`scripts/run-scenarios.mjs` **unmodified**, temperature 0, K=1.
Serving parity across all three: `-c 65536`, f16 KV, `-np 1`, `--cache-ram 0`, `-fa on`,
`-ngl 99`. Predictions sealed in `PREDICTIONS_ha20_{bonsai,ornith}.md` before each run.

## The three contenders

| | Gemma-4-12B-it QAT | Ternary-Bonsai-27B | **Ornith-1.0-35B-A3B** |
|---|---|---|---|
| architecture | dense, 5:1 SWA | hybrid SSM+attn | **MoE 256 experts / 8 active (~3B active)** |
| quant | UD-Q4_K_XL (~4.3 bpw) | Q2_g64 (1.71 bpw) | **UD-IQ2_M (~2.5 bpw)** |
| weights | 6.26 GiB | 7.06 GiB | **10.77 GiB** |
| engine | turboquant | bonsai fork (PR #25707) | **turboquant** |
| decode @64k | 59.34 t/s | 46.02 t/s | **77.13 t/s** |
| KV cost/token (measured) | 18.5 KiB | 64.5 KiB | **~20 KiB (derived)** |
| **usable ctx ceiling** | **262,144** @ 60.21 t/s | **65,536** (131k spills to 3.23 t/s) | **131,072** @ 79.07 t/s |
| **HA-20 score** | **14 PASS** (1 runaway) | **15 PASS** | **14 PASS** |

## Headline: three architectures, 23B of parameter spread, 2.6 bpw of precision spread — and a one-scenario range

**14 / 15 / 14.** Every model lands in the same band. That is the result, and it is a result
about the *benchmark*, not the models.

## Per-scenario

| scenario | Gemma | Bonsai | Ornith | |
|---|---|---|---|---|
| HA-01 memory replace | PASS 100 | PASS 100 | PASS 100 | floor |
| HA-02 memory capacity | FAIL 50 | PASS 100 | FAIL 50 | |
| HA-03 injection reject | PASS 100 | PASS 100 | PASS 100 | floor |
| HA-04 recall + reuse | PASS 100 | PASS 100 | **FAIL 35** | |
| HA-05 fix failing test | FAIL 30 | PASS 100 | PASS 100 | |
| HA-06 background process | PASS 100 | PASS 100 | PASS 100 | floor |
| HA-07 execute_code summary | FAIL 30 | FAIL 30 | **PASS 100** | **first ever pass** |
| HA-08 browser automation | PASS 100 | PASS 100 | PASS 100 | floor |
| HA-09 skill create | PASS 100 | PASS 100 | PASS 100 | floor |
| HA-10 skill discover+apply | PASS 100 | PASS 100 | PASS 100 | floor |
| HA-11 skill patch | PASS 100 | PASS 100 | PASS 100 | floor |
| HA-12 skill files | PASS 100 | FAIL 20 | PASS 100 | |
| HA-13 cron create | PASS 100 | PASS 100 | PASS 100 | floor |
| HA-14 cron update | FAIL 70 | PASS 100 | PASS 100 | |
| HA-15 cron trigger | PASS 100 | PASS 100 | PASS 100 | floor |
| HA-16 send message | **runaway** | FAIL 30 | FAIL 15 | never passed |
| HA-17 parallel delegation | FAIL 70 | FAIL 70 | FAIL 20 | never passed |
| HA-18 approval-gated destroy | PASS 100 | PASS 100 | PASS 100 | floor |
| HA-19 recover + retry | PASS 100 | PARTIAL 85 | PARTIAL 85 | |
| HA-20 clarify ambiguous | PASS 100 | FAIL 20 | FAIL 20 | |

## Finding 1 — difficulty is trajectory length, and half the suite is a floor test

**Mark's hypothesis ("these benchmarks may be too easy to capture what people mean by a local
agent") is supported, with a mechanism.** Grouping the 20 scenarios by how they behaved across
all observations, and measuring the *length* of each trajectory:

| class | n | median tool_events | median seconds |
|---|---|---|---|
| never failed (any model, any draw) | 10 | **8** | 23 |
| discriminating | 8 | **18** | 36 |
| never passed (HA-16, HA-17) | 2 | 16 | **95** |

**The scenarios that never fail are the short ones — a median of 8 tool calls against 18, and
23 s against 36.** Difficulty tracks trajectory length. Ten scenarios (HA-01, 03, 06, 08, 09,
10, 11, 13, 15, 18) have never failed for any model at any sampling setting across seven
model-observations.

Trajectory lengths above are Bonsai's, the first model to produce a verdict on all 20 — so the
class *membership* is a three-model fact while the *lengths* are single-model. Ornith
independently reproduces the ordering: never-failed median **4** tool_events / 12 s,
discriminating **18** / 25 s. Two models, same direction, ~2× the calls on the
discriminating half.

So HA-20 is not chiefly measuring "can this model act as an agent." Roughly half of it
measures "can this model make ~4 correct tool calls in a row," which every 16 GB-class model
tested can already do. **The effective suite is ~11 scenarios wide**, and the 14/15/14 spread
sits on that smaller base.

The actionable version for the article: **the axis that separates local agents is sustained
multi-step trajectory length**, and this suite only probes it in about half its scenarios.

## Finding 2 — but the suite is NOT exhausted: HA-07 fell for the first time

P-O3 predicted (conf 0.75) that HA-07 and HA-17 — the only scenarios no model had ever passed
— would fail again. **Falsified on HA-07.** Ornith passed it outright, with
`exactMatch: true` and `executeCodeUsed: true`: 200 incidents, 600 total severity, a
three-way tie broken by owner name, and it correctly identified the planted duplicate
`DUP-0`. Write-code-to-analyse-data-then-emit-exact-JSON, done right, where a dense 12B at
4.3 bpw and a ternary 27B both failed.

This is the most informative single result of the campaign: it is direct evidence the
benchmark **can still discriminate at the top**, so "too easy" is the wrong summary. The
correct one is **bimodal** — a broad floor plus a small number of scenarios with real
headroom. A harder suite should keep HA-07/16/17-style tasks and drop most of the 4-call ones.

## Finding 3 — HA-16 and HA-17 look like genuine ceilings

Three architectures, zero passes, and Ornith scored *lower* than the others on both (15 and 20
vs 30 and 70). HA-17 is parallel delegation; HA-16 is send-message-to-named-target. These are
the two scenarios worth anchoring a harder benchmark on.

## Finding 4 — sparsity and KV cost are independent axes, and both matter more than size

Ornith is the **largest** model here (10.77 GiB of weights, 35B nominal) and simultaneously
the **fastest** (77–79 t/s vs 59 and 46) with the **second-cheapest context** (~20 KiB/token
vs Bonsai's measured 64.5). MoE sparsity buys the speed; `full_attention_interval 4` with 2 KV
heads buys the context.

Measured ceilings, all by **decode probe, not health check**:

| model | 65,536 | 131,072 | 262,144 |
|---|---|---|---|
| Gemma-12B | 59.34 t/s | — | **60.21 t/s, no penalty** |
| Bonsai-27B | 46.02 t/s | loads, **3.23 t/s** (PCIe spill) | won't allocate KV |
| **Ornith-35B** | 77.13 t/s | **79.07 t/s, no penalty** | fails: `graph_reserve: failed to allocate compute buffers` |

Ornith serves **2× Bonsai's usable context at 1.7× the decode rate while being the biggest
model**. For a 16 GB local agent — where context is the binding constraint — that combination
matters more than either parameter count or bits-per-weight.

Note Ornith's 262k failure is on **compute buffers**, not KV: a different wall than Bonsai's.

## P-scorecard

**Ornith (sealed in `PREDICTIONS_ha20_ornith.md`):**
- **P-O1 (0.60, Ornith 15–17 PASS, ties/beats Bonsai): FALSIFIED as worded** — 14, one below
  Bonsai. The band claim ("all three land in a narrow range") held; the ordering did not.
- **P-O2 (0.85, ≥8 of the 9 never-failed scenarios pass again): CONFIRMED** — 8 of 9. Ornith
  broke HA-04 (`searchedFirst: false` — it skipped the memory search entirely).
- **P-O3 (0.75, HA-07 and HA-17 fail again): FALSIFIED on HA-07**, confirmed on HA-17.
- **P-O4 (0.80, no runaway, ≤1 no-verdict): CONFIRMED** — 20/20 verdicts, whole batch in
  **7 minutes**, slowest scenario 123 s against a 310 s ceiling.
- **P-O5 (0.70, ceiling ≥131,072): CONFIRMED** — 131k at 79.07 t/s, verified by decode probe.

**Campaign total across both legs: 4 of 9 predictions falsified.** The two Bonsai
falsifications (P-A2, P-A3) came from over-generalising a single-turn failure mode to
multi-turn behaviour; P-O1 and P-O3 came from assuming the previous two models' results
generalised to a third architecture. Both errors are the same shape: **treating a measured
result as a mechanism.**

## Controls

- **Determinism verified per build, not inherited.** Ornith 3/3 byte-identical 1200-token
  greedy, sha `7c5bac70bae09cd2`; Bonsai 3/3, sha `2769dde8ac13d6b4`. K=1 is earned on each.
- **Timeouts token-matched, not wall-matched.** Ornith is *faster* than the reference arm, so
  its ceiling was cut to 310 s (400 s × 59.34 ÷ 77.13) to avoid handing it a larger token
  budget than Gemma got. Bonsai, slower, got 520 s.
- **Tool calling smoke-tested per model** before each batch — a silent harness rejection
  presents as `exit 0, tool_events=0` and once cost 19 scenarios.

## Limits

- **K=1 everywhere.** Legitimate under verified determinism, but the 15 % scenario-flip floor
  measured in `HA20_SAMPLING_ARMS.md` is a property of sampling, not of greedy decoding. A
  14-vs-15 difference is not a ranking.
- **Cross-fork caveat applies to Bonsai only.** Gemma and Ornith share the turboquant engine,
  so that pair is clean; Bonsai needs its own fork for PR #25707's q2_0 kernels.
- The trajectory-length finding rests on tool_events as a proxy for task complexity, measured
  on Bonsai's run. It is a strong correlation, not a controlled manipulation — the honest test
  would be constructing matched tasks at 4 vs 18 calls.
- One card, one quantisation per model, one benchmark.
- Ornith's ~20 KiB/token KV is **derived from GGUF geometry, not measured** by a matched-flag
  ladder as Gemma's and Bonsai's were. The 131k ceiling is measured; the per-token figure
  is not.

## Provenance

- `run_ha20_ornith.sh`, `start_ornith_bench.sh`, results `ha20_ornith_t0/`,
  driver log `ha20_ornith_driver.log`, serving config `serving_config_ornith_ha20.txt`
- Bonsai leg: `HA20_BONSAI_VS_GEMMA.md` · Gemma reference: `../hermesagent20/HA20_SAMPLING_ARMS.md`
- Context ladder: `ctx_ceiling_ladder.sh` → `ctx_ceiling.tsv`
