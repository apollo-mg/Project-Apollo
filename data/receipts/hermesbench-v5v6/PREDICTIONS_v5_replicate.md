# Predictions — HermesBench V5 replicate under the pinned config

Logged 2026-07-31 **before** the run. `.73` dual P100, 1063 MHz / 150 W.
Benchmark: `am423/hermes-bench-tool-call` @ `10bf4c6`, hermes-agent `07e97d2f5`,
`--all --toolsets all --timeout-overhead 300`, explicit `--model` + `--base-url`.

## Why this run and not six

The apparent V6 > V5 result is **56 vs 55 on one draw each**, and the whole margin is a
single task. Decomposed:

| run | model | cfg | non-PASS set |
|---|---|---|---|
| `hermes01` | V5 | `-sm tensor -ts 1,1` | 5 common + **t04_datascience** |
| `v5_det02` | V5 | pinned (`-sm layer -np 1`) | 5 common + **humaneval_9** |
| `v6_det01` | V6 | pinned | **5 common only** |

Five non-PASSes are common to all three: `t09_web_lookup/{t01_search, t02_extract,
t03_no_result}` (invalid on this host — the `web` toolset is never loaded) and
`t10_memory_facts/{t02_recall, t03_avoid_dup}` (legitimate tool-selection failures).

**V6's entire margin is the "sixth slot," and V5 has put a different task in that slot on
each of its two runs — passing the other one both times.** That is the shape of run-to-run
noise, not a model difference.

**The missing piece is not K, it is a same-config replicate.** `hermes01` and `v5_det02`
differ in split mode *and* draw, so the 4 differing tasks between them cannot be attributed.
One V5 run under the pinned config resolves it and produces the headline number that was
requested. Six full suites (~17 h) buy nothing this does not.

## Pre-registered decision rule (fixed before launch)

- **V5 replicate passes `humaneval_9` → 56 vs 56.** Toss-up confirmed. Publish both as
  indistinguishable on this instrument. **Stop.**
- **V5 replicate fails `humaneval_9` again** → escalate to **K=8 targeted on `humaneval_9`
  alone, both arms** (~1 h), not full suites.
- **A different sixth task fails instead** → strongest evidence yet that the sixth slot is
  a noise channel; report as such, no escalation.

## Predictions

| id | claim | confidence |
|---|---|---|
| **P-V1** | V5 replicate total lands in **54–56** | **0.80** |
| **P-V2** | The 5 common non-PASSes recur exactly | **0.85** |
| **P-V3** | `humaneval_9` **passes** this time | **0.60** |
| **P-V4** | ≥1 task differs from `v5_det02` that is not `humaneval_9` | **0.55** |
| **P-V5** | V5 and V6 end statistically indistinguishable | **0.75** |
| **P-V6** | Zero INFRA_ERRORs at `--timeout-overhead 300` | 0.55 |

**P-V3 at 0.60, not higher:** `hermes01` passed it and `v5_det02` failed it, so the only
direct evidence is 1-for-2. P-V4 at 0.55 because V5-vs-V5 across configs already moved 4
tasks; some of that is the config, some is jitter, and this run is the first clean read.

P-V6 is hedged despite the fix: `v5_det02` still took 1 INFRA_ERROR at 300 s overhead, and
`t09_extract` / `t08_pandas` have hit the raised ceiling before.

**P-V5 is the one to protect against motivated reading.** A 1-task margin on a 61-task
suite whose own per-run jitter is several tasks cannot support a ranking, and the temptation
will be to report "V6 edges V5" because that is the more publishable sentence.

## Known limits, stated before the data

- **3 of 61 tasks are invalid on this host** (`t09_web_lookup`, `web` toolset never loaded).
  The honest denominator is **58**, and it must be printed that way.
- Score is a **lossy hash of output** — `hermesagent20/SUMMARY.md` found 33 of 36 same-score
  groups hiding different completions, and zero groups ever byte-identical. PASS/PASS does
  not mean "same behaviour."
- The summaries label the model `Hermes3.6-35B-A3B-Genesis-V5-APEX`; the GGUF is
  `Hermes3.6-35B-A3B-Uncensored-Genesis-V5-APEX.gguf`. Fix the label before publishing.
