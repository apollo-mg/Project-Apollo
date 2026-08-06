# Genesis V5 vs V6 on HermesBench — indistinguishable, and the "V6 wins" reading is dead

`.73` dual Tesla P100 (sm_60), 1063 MHz / 150 W. Date 2026-07-31.
Benchmark `am423/hermes-bench-tool-call` @ `10bf4c6`, hermes-agent `07e97d2f5`,
`--all --toolsets all --timeout-overhead 300`, temperature 0.
Serving config pinned by `~/bench-stack/bench_server.sh` — `-c 32768 -np 1 -ctk/-ctv f16
-sm layer --no-cache-idle-slots -fit off -fa on`, build `a8e5b5a386f0`.
Predictions: `PREDICTIONS_v5_replicate.md` (logged pre-run).

Model files: `Hermes3.6-35B-A3B-Uncensored-Genesis-V{5,6}-APEX.gguf`. The harness records the
label `Hermes3.6-35B-A3B-Genesis-V5-APEX`, which omits `Uncensored` — the GGUF path in each
run's sidecar is authoritative.

## Headline

| run | model | config | total | adjusted |
|---|---|---|---|---|
| `hermes01` | V5 | `-sm tensor` (unpinned) | 55/61 | 55/58 |
| `v5_det02` | V5 | pinned | 55/61 | 55/58 |
| **`v5_det03`** | **V5** | **pinned** | **57/61** | **57/58** |
| `v6_det01` | V6 | pinned | 56/61 | 56/58 |

**The V5 replicate scored 57 — higher than V6's 56.** The pre-registered rule resolved on its
third branch: not only did `humaneval_9` pass again, a *different* task moved.

## Why "V6 > V5" was never a result

Before this run the evidence was V6 56 vs V5 55, one draw each. That margin was a single task,
and V5 had already put a *different* task in that slot on each of its two runs. The
pre-registration called that the shape of a noise channel and set the rule in advance.

Task-level, every disagreement across all four runs:

| task | V5 old-cfg | V5 pinned #1 | **V5 pinned #2** | V6 pinned |
|---|---|---|---|---|
| `t08_execute_code/t04_datascience` | INFRA_ERROR | PASS | PASS | PASS |
| `t09_web_lookup/t01_search` | FAIL | INFRA_ERROR | FAIL | FAIL |
| `t09_web_lookup/t03_no_result` | INFRA_ERROR | FAIL | FAIL | FAIL |
| `t10_memory_facts/t03_avoid_dup` | FAIL | FAIL | **PASS** | FAIL |
| `t13_humaneval_micro/humaneval_9` | PASS | **FAIL** | PASS | PASS |

**Five tasks have moved, and four of them moved within V5 alone.** Two V5 runs under a
byte-identical serving config disagree on `humaneval_9` and `t10_memory_facts/t03_avoid_dup`.
The only variable between `v5_det02` and `v5_det03` is the draw.

**The instrument's own within-model jitter is ±2 tasks. The between-model difference is 1.**
The benchmark cannot resolve V5 from V6 at this K, in either direction.

## Prediction scoring

| id | claim | conf | outcome |
|---|---|---|---|
| P-V1 | replicate total in 54–56 | 0.80 | **FALSIFIED** — 57 |
| P-V2 | the 5 common non-PASSes recur exactly | 0.85 | **FALSIFIED** — `t03_avoid_dup` passed |
| P-V3 | `humaneval_9` passes | 0.60 | **CONFIRMED** |
| P-V4 | ≥1 non-`humaneval_9` task differs from `v5_det02` | 0.55 | **CONFIRMED** — `t03_avoid_dup` |
| P-V5 | V5 and V6 statistically indistinguishable | 0.75 | **CONFIRMED** |
| P-V6 | zero INFRA_ERRORs | 0.55 | **CONFIRMED** |

4 of 6. Both falsifications are the same error: **I under-modelled the variance I was running
the experiment to measure.** P-V1's range was built from two draws that happened to agree at
55, and P-V2 assumed the "common" set was stable because it had been stable twice.

P-V4 confirming is the substantive result — it is direct evidence the sixth slot is a noise
channel rather than a model property, which is what the whole design was for.

## Two failures are real, one class is invalid

**Invalid (3 tasks, excluded from the denominator):** `t09_web_lookup/*`. The `web` toolset is
never loaded on this host — `~/.hermes/config.yaml` sets `backend: firecrawl, use_gateway:
true`, and the search provider wants `BRAVE_SEARCH_API_KEY`. Both are external paid services,
so this is not fixable under the local-first constraint and should not be counted. **Report
/58, never /61.**

**Legitimate:** `t10_memory_facts`. The `memory` toolset *is* loaded; the model has it, and
answers correctly from context instead of calling it. Genuine tool-selection behaviour — and
now known to be intermittent, since `t03_avoid_dup` passed on one V5 draw of three.

Every FAIL carries `score=1.0` and `exit=0`: correct output, failed on the tool-usage
criterion.

## What can and cannot be said publicly

**Supported:** "V5 and V6 both score 55–57 of 58 on HermesBench on 2×P100 under a pinned
deterministic serving config. Run-to-run variance at temperature 0 is ±2 tasks, larger than
any difference between the two models. This benchmark does not separate them."

**Not supported:** any ranking. Not "V6 edges V5" (the earlier reading), and not "V5 beats V6"
(this run) — the same evidence that kills the first kills the second.

**Also not supported by any of this:** that the models are behaviourally equivalent.
`hermesagent20/SUMMARY.md` established that score is a lossy hash of output — across 36 groups
with ≥2 draws, 33 had matching scores hiding different completions and **zero** were ever
byte-identical. PASS/PASS does not mean "same behaviour." A real V5-vs-V6 claim needs the
byte-diff instrument, not more suites.

## Cost note for anyone repeating this

Three full 61-task runs (~2.0–2.8 h each) to establish a null. The single V5 replicate was the
whole experiment; the earlier plan of six suites (~17 h) would have bought the same answer.
When the suspected effect is 1 task and the instrument's jitter is unmeasured, **measure the
jitter first** — one same-config replicate, not more arms.

## Provenance

- `v5_det03/` (+ `hermes01/`, `v5_det02/`, `v6_det01/`, `v5_det01_INVALID_timeout90/`)
- `v5_det03.log`, `run_v5_det03.sh` — the driver aborts unless `.73`'s sidecar reports v5
- Serving sidecars on `.73`: `~/bench-stack/serving_config_v{5,6}.json`
- Cache-isolation control: `~/bench-stack/flush_isolation_v5.json` — cold/flushed/dirty all
  `da1a09a7996a` ×3, so between-task cache state is not a variable here
- Wall clock: `v5_det03` 12:43:43 → 14:38:56 EDT (1 h 55 m), zero INFRA_ERRORs
