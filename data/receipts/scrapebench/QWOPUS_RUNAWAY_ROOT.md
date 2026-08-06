# Qwopus-Fusion generates unbounded tool-call arguments — at Q4 and Q6 alike

`.73`, 2× Tesla P100 (sm_60), 1063 MHz / 150 W. Date 2026-08-01.
ScrapeBench (`bench/scrapebench/`), tier `t2_boilerplate`, temp 0, pinned serving config
(`-c 32768 -np 1 -ctk/-ctv f16 -sm layer --no-cache-idle-slots -fit off -fa on`).
Predictions: `PREDICTIONS_qwopus_q6k.md`, `PREDICTIONS_merge_vs_dense.md`.

## The measurement that settles it

Maximum tool-call argument emitted on `t2_boilerplate` — the tier requiring the longest
code payload — read from raw transcripts, not from scores:

| model / arm | t2 elapsed | status | **max tool arg** |
|---|---|---|---|
| Qwopus-Fusion **Q4_K_M**, temp 0 | 824.2 s | INFRA_ERROR | **50,040 chars** |
| Qwopus-Fusion **Q6_K**, temp 0, 1200 s cap | 1073.5 s | INFRA_ERROR | **43,161 chars** |
| Qwopus-Fusion **Q4_K_M**, temp 0.9 / top_p 0.9 | 106.4 s | OK | **1,335 chars** |
| **Fable-Fusion-711** Q6_K, temp 0 | 374.0 s | OK | **2,906 chars** |
| Genesis V5 (35B-A3B MoE) Q4, temp 0 | 61.0 s | OK | small |

llama-server rejects the runaway with:

```
Failed to parse tool call arguments as JSON: parse error at line 1, column 50041:
syntax error while parsing value - invalid string: missing closing quote
```

The model emits a `write_file` call whose `content` argument never terminates; `max_tokens`
truncates it mid-string and the server 500s. Raising 4096 → 8192 only let the runaway grow
before truncating.

## Four hypotheses, three eliminated

| candidate | test | verdict |
|---|---|---|
| **Density** (dense more fragile than MoE) | Fable-Fusion: dense, temp 0 | **ELIMINATED** — clean, mean 0.996 |
| **Merging** (merged models decalibrated) | Fable-Fusion: merged, temp 0 | **ELIMINATED** — clean |
| **Envelope violation alone** | V5 and Fable both run outside recommended sampling | **ELIMINATED** — both clean |
| **Quantization** (Q4 degeneracy) | same merge at Q6_K, temp 0 | **ELIMINATED as cause** — still 43,161 chars |

**What remains: this specific merge.** Fable-Fusion-711 is also a dense 27B Qwen3.6 merge at
Q6_K and completes the same tier at 2,906 characters. Qwopus-Fusion fails at both precisions.

## Quantization and sampling are modifiers, not causes

- **Precision helps on shorter payloads and not on long ones.** `t1_article` went
  1290.2 s (Q4) → 93.7 s (Q6), both scoring 1.000. But t2's runaway only shrank ~15%
  (50,040 → 43,161). Whatever precision fixes, it is not the unbounded-generation mode.
- **Sampling is the strong intervention.** temp 0.9 / top_p 0.9 on the *same Q4 weights*
  collapsed the argument from 50,040 to 1,335 characters and turned an INFRA_ERROR into a
  clean pass. Greedy decoding locks this merge into repetition inside long code payloads.

Same family as the Laguna and Puzzle stopping-rule findings — **failure to stop, not failure
to answer** — expressed inside tool-call arguments rather than prose.

## Prediction scoring

| id | claim | conf | outcome |
|---|---|---|---|
| P-Q1 | Q6_K shows no runaway | 0.70 | **FALSIFIED** — 43,161 chars, INFRA_ERROR |
| P-Q2 | t1 completes <200 s | 0.70 | **CONFIRMED** — 93.7 s |
| P-Q3 | t2 returns a scored answer | 0.72 | **FALSIFIED** |
| P-Q5 | if P-Q1 holds, cause is quantization | — | **not triggered** |
| P-M1 | Fable (dense+merged) runs away | 0.55 | **FALSIFIED** — clean, 0.996 |
| P-M2 | q36 does not run away | 0.75 | not yet run |
| P-M3 | qcoder does not run away | 0.70 | not yet run |

**I scored P-Q1 CONFIRMED before this run and was wrong.** The first Q6_K arm used
`--turn-timeout 420`; it reported t2 "recovered" at 444.6 s with `max_tool_arg = 0` because
the read timeout fired *before the runaway finished generating*. I read the absence of a
visible failure as absence of the failure — without checking whether my own timeout was
suppressing it. The corrected run (1200 s cap) exposes it.

That is the sixth harness fault in this campaign to present as a model property, and the
first one I propagated into a stated conclusion before catching it.

## Every timeout is a hidden capability threshold

Six defects across two independently-authored harnesses, all the same shape:

| # | defect | presented as |
|---|---|---|
| 1 | HermesBench bare `fetch()`, 300 s undici default | model INFRA_ERROR |
| 2 | ScrapeBench turn cap → `output=""` → score 0 | three V5 tiers "failing" while succeeding |
| 3 | `max_tokens` 4096 truncating tool-call JSON | KAT t2 capability gap |
| 4 | t5 scored from prose, not transcript | V5 under-scored 0.75 vs 1.000 |
| 5 | bare `httpx timeout=N` hanging 35 min on a finished socket | model "hung" |
| 6 | `--turn-timeout 420` hiding a runaway entirely | **quantization "fixed" the bug** |

**A benchmark timeout does not measure the model; it measures whether the model fits inside
an arbitrary budget — and it fails silently in the direction of the tester's expectations.**
Defect 6 is the sharpest case: the timeout produced the *tidier* answer ("it was just the
quant"), which is exactly the direction a tester is least likely to question.

## Worth reporting to the author

Kyle Hessling (`KyleHessling1/Qwopus3.6-27B-Fusion-GGUF`) would want to know:

- At **temp 0**, the fusion emits unbounded `write_file` arguments (>40k chars) on tasks
  requiring a long code payload, at **both Q4_K_M and Q6_K**, causing hard HTTP 500s.
- At the card's **recommended temp 0.85–1.0 / top_p 0.9** the same task completes normally.
  The recommendation is load-bearing, not stylistic — worth stating on the card in those terms.
- A sibling merge (Fable-Fusion-711, dense 27B Qwen3.6, Q6_K) does not exhibit this, so it
  is not inherent to merging Qwen3.6-27B.

Not yet checked: whether `Qwopus3.6-27B-Coder-heretic` (a **parent** of the fusion) shows the
same behaviour. That is the test that would tell him whether the merge introduced it or
inherited it, and it is queued.

## Limits

- **K=1 on the corrected Q6_K t2 run.** The three K=3 reps that preceded it were all
  invalidated by defect 6 (byte-identical `15223b63a4a5`, 441–445 s, `attempts=0` — all
  timeout artifacts). Those three *do* establish that this model is deterministic at temp 0
  on this stack, which is worth having independently.
- One tier. t2 is the only tier demanding a long code payload; whether the runaway generalises
  to other long-generation tasks is untested.
- ScrapeBench is new (built 2026-07-31) and has now been corrected six times. Treat absolute
  scores as provisional; the argument-length measurements are direct and robust.

## Provenance

- `results/qwopus_full01/` (Q4 temp 0), `results/qwopus_rec01/` (Q4 temp 0.9),
  `results/qwopus6_t0/` (Q6 420 s cap), `results/qwopus6_t2_fixed/` (Q6 1200 s cap),
  `results/qwopus6_t2_k{1,2,3}/` (invalidated reps), `results/fable_t0/`, `results/v5_full02/`
- `~/bench-stack/server_qwopus.log`, `server_qwopus6.log` on `.73` — the column-50041 errors
- Serving sidecars: `~/bench-stack/serving_config_qwopus{,6}.json`
