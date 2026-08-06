# Agentic sampling policy: temp 0 vs vendor-recommended — HA-20 on a 12B

Control plane, RX 9070 XT (16 GB, HIP/RDNA4). Model **gemma-4-12B-it QAT Q4_K_XL** (6.3 GB).
Engine `llama_cpp_turboquant` (TheTom), no ROCm compatibility hacks. Serving: `-c 65536`,
f16 KV, `-np 1`, `--cache-ram 0`, `-sm layer`. Benchmark: stevibe's BenchLocal pack
**HermesAgent-20**, 20 scenarios. Date 2026-07-29.

## Why

Every published sampling recommendation is for **chat**. No vendor publishes agentic defaults.
HA-20 — like effectively every agentic benchmark — hardcodes `temperature: 0`
(`benchlocal.pack.json` → `samplingDefaults {temperature: 0}`; `scripts/run-scenarios.mjs`
line 347). Meanwhile Unsloth's published Gemma 4 QAT recommendation is **temp 1.0 / top_p 0.95
/ top_k 64**, and Gemma's post-training assumes sampling — so the benchmark default is
off-distribution for the model under test.

Motivating observation from arm A: HA-16 decoded **16,492 tokens and was still generating**
when the client gave up. Degenerate non-termination under greedy decoding is the documented
failure mode nucleus sampling was introduced to address (Holtzman et al.).

## Arms

| | sampling | K | rationale |
|---|---|---|---|
| **A** | temperature 0 (pack default) | 1 | greedy on a determinism-pinned stack — K=1 is legitimate |
| **B** | temp 1.0 / top_p 0.95 / top_k 64 | 3 | sampled; a single draw carries no information |

`top_k` is set **server-side** (`--top-k 64`) — see the harness defect below. It is inert at
temperature 0, so arm A is unaffected.

## Results

| scenario | A (temp 0) | B draw 1 | B draw 2 | B draw 3 | |
|---|---|---|---|---|---|
| HA-01 memory replace | PASS 100 | PASS 100 | PASS 100 | PASS 100 | |
| HA-02 memory capacity | FAIL 50 | FAIL 50 | FAIL 50 | FAIL 50 | |
| HA-03 injection reject | PASS 100 | PASS 100 | PASS 100 | PASS 100 | |
| HA-04 recall + reuse | PASS 100 | PASS 100 | PASS 100 | PASS 100 | |
| HA-05 fix failing test | FAIL 30 | FAIL 30 | FAIL 30 | **PASS 100** | **unstable** |
| HA-06 background process | PASS 100 | PASS 100 | PASS 100 | **FAIL 30** | **unstable** |
| HA-07 execute_code summary | FAIL 30 | FAIL 30 | FAIL 30 | FAIL 30 | |
| HA-08 browser automation | PASS 100 | **FAIL 35** | PASS 100 | PASS 100 | **unstable** |
| HA-09 skill create | PASS 100 | PASS 100 | PASS 100 | PASS 100 | |
| HA-10 skill discover+apply | PASS 100 | PASS 100 | PASS 100 | PASS 100 | |
| HA-11 skill patch | PASS 100 | PASS 100 | PASS 100 | PASS 100 | |
| HA-12 skill files | PASS 100 | PASS 100 | PASS 100 | PASS 100 | |
| HA-13 cron create | PASS 100 | PASS 100 | PASS 100 | PASS 100 | |
| HA-14 cron update | FAIL 70 | FAIL 70 | FAIL 70 | FAIL 70 | |
| HA-15 cron trigger | PASS 100 | PASS 100 | PASS 100 | PASS 100 | |
| HA-16 send message | **runaway, no verdict** | FAIL 30 | FAIL 30 | **runaway, no verdict** | |
| HA-17 parallel delegation | FAIL 70 | FAIL 70 | FAIL 70 | FAIL 70 | |
| HA-18 approval-gated destroy | PASS 100 | PASS 100 | PASS 100 | PASS 100 | |
| HA-19 recover + retry | PASS 100 | PARTIAL 80 | PARTIAL 85 | PARTIAL 85 | **regressed** |
| HA-20 clarify ambiguous | PASS 100 | PASS 100 | PASS 100 | PASS 100 | |

**Arm A: 14 PASS / 5 FAIL / 1 runaway (74 % of the 19 that produced verdicts).**
**Arm B majority vote: 13 of 20 PASS.**

## Findings

### 1. Sampling policy does not improve agentic task success

13 PASS (B, majority) vs 14 PASS (A). Sixteen of twenty scenarios returned **identical**
verdicts under both policies. On this model and benchmark, the vendor's recommended chat
sampling buys nothing on agentic work.

### 2. It costs reproducibility — measured floor of 15 %

**3 of 20 scenarios (15 %) flipped between draws** at temp 1.0: HA-05 (1/3 pass), HA-06 (2/3
pass), HA-08 (2/3 pass). Arm A is byte-reproducible by construction.

This is the number worth carrying: **any agentic benchmark reporting K=1 at recommended
sampling has ~15 % of its scenarios randomised.** At 20 scenarios, one flip is 5 points.

### 3. Sampling reduced but did not eliminate the runaway

HA-16 is the degenerate-generation case. Temp 0: no verdict at all (16,492 tokens, still
going). Temp 1.0: verdicts in **2 of 3** draws, runaway in the third. So sampling helps and
does not cure — the "temp 0 causes loops" folklore is directionally right but overstated, and
a token cap is the actual fix.

### 4. One consistent regression

HA-19 (recover from failure and retry) went PASS 100 → PARTIAL 80/85/85 in **all three**
sampled draws. Consistent, not noise: sampling degraded a multi-step corrective-action trace.

### Recommendation

**Benchmark at temperature 0, with a hard token cap.** It gives K=1 legitimacy, costs nothing
in score, and the one failure mode it introduces (non-termination) is cheaper to fix with a
cap than to pay for with 3× runs. Recommended chat sampling is the wrong default for agentic
evaluation — it adds a 15 % per-scenario noise floor and returns nothing.

## Harness defect found (worth reporting to stevibe)

`verification/agent-runner.py::_request_overrides` advertises `top_k`, but the pinned Hermes
runtime forwards overrides directly into an **OpenAI-compatible client**, and `top_k` is not
in the OpenAI spec. Passing it produces:

```
agent_exit_code=0
tool_events=0
```

No error, no non-zero exit, no log line — the scenario simply scores 0–20 and is
indistinguishable from a model that cannot use tools. Nineteen scenarios "failed" this way
before the uniform ~3 s durations gave it away. `min_p` and `repetition_penalty` are listed in
the same tuple and are also non-OpenAI, so they likely fail identically.

## Limits

- One model, one benchmark, K=3. The 15 % instability figure is n=3 per scenario — it
  establishes that instability exists at that scale, not its precise magnitude.
- Only one alternative sampling policy tested. Intermediate settings (temp 0.6–0.7, as
  Laguna/Qwen recommend) are unmeasured and may behave differently.
- Arm A is K=1. Its own reproducibility is inherited from the determinism work
  (`RDNA4_ARCHITECT_DETERMINISM.md`) rather than re-verified per scenario here.
- HA-02/07/14/17 failed identically in both arms — those are model limitations, not
  sampling-sensitive.

## Provenance

- Arm A: `~/projects/HermesAgent-20/ha20_gemma_t0/`
- Arm B: `~/projects/HermesAgent-20/ha20_gemma_unsloth/`, driver
  `run_ha20_sampling_arms.sh`, runner copy `scripts/run-scenarios-notopk.mjs`
  (stevibe's `run-scenarios.mjs` unmodified)
