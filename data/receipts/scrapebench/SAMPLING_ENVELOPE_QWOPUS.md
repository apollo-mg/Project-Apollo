# Running a model at temp 0 outside its recommended envelope cost 18× wall-clock and a hard serving failure

> ## CORRECTION 2026-08-01 — the cause is NOT quantization, and this receipt's follow-up conclusion was wrong
>
> After this receipt was written, `Qwopus3.6-27B-Fusion` was re-run at **Q6_K**, and I
> reported (in conversation, not on disk) that the runaway was fixed and the cause was
> therefore quantization. **That was wrong, and it was wrong for the same reason this
> receipt criticises elsewhere: a timeout was hiding the failure.**
>
> The Q6_K arm ran with `--turn-timeout 420`. It reported t2 as "recovered" at 444.6 s with
> `max_tool_arg = 0` — because the read timeout fired *before the runaway tool call finished
> generating*. Re-run at `--turn-timeout 1200`, the same Q6_K build produced a **43,161-character
> tool argument** and the same INFRA_ERROR.
>
> **Measured maximum tool-call argument length, t2_boilerplate, all arms:**
>
> | arm | t2 elapsed | status | max tool arg |
> |---|---|---|---|
> | Qwopus **Q4_K_M**, temp 0 | 824.2 s | INFRA_ERROR | **50,040 chars** |
> | Qwopus **Q6_K**, temp 0, 420 s cap | 444.6 s | "OK" *(artifact)* | 0 — cut off mid-generation |
> | Qwopus **Q6_K**, temp 0, 1200 s cap | 1073.5 s | **INFRA_ERROR** | **43,161 chars** |
> | Qwopus **Q4_K_M**, temp 0.9 / top_p 0.9 | 106.4 s | OK | **1,335 chars** |
> | **Fable-Fusion-711** Q6_K, temp 0 | 374.0 s | OK | **2,906 chars** |
>
> **What survives:** the sampling finding in this receipt is unaffected and is the strongest
> result — temp 0.9 collapses the runaway from 50,040 to 1,335 characters on the same weights.
> Precision helps on *shorter* payloads (t1: 1290 s → 93.7 s, both scoring 1.000) but does not
> remove the pathology; Q6_K only shortens the runaway ~15%.
>
> **What changes:** quantization is a *modifier*, not the cause. Fable-Fusion is dense, merged,
> Q6_K and runs t2 cleanly at 2,906 chars. Qwopus-Fusion fails t2 at **both** Q4 and Q6. The
> variable that tracks the failure is **this specific merge**, not bit-width, not density,
> not MoE-vs-dense.
>
> **How I got it wrong: I scored a prediction on the absence of a visible failure, without
> checking whether my own timeout was suppressing it** — one layer below the exact mistake
> catalogued as harness defect #5 in this document. Full detail: `QWOPUS_RUNAWAY_ROOT.md`.

`.73`, 2× Tesla P100 (sm_60), 1063 MHz / 150 W. Date 2026-08-01.
Model: `Qwopus3.6-27B-Fusion-Q4_K_M` (KyleHessling1) — a geometry-weighted merge of a
reasoning tune and a coding tune of Qwen3.6-27B. **Card recommends temperature 0.85–1.0,
top_p 0.9.**
Serving: `bench_server.sh qwopus` — `-c 32768 -np 1 -ctk/-ctv f16 -sm layer
--no-cache-idle-slots -fit off -fa on`, build `a8e5b5a386f0`. Identical for both arms.
Benchmark: ScrapeBench (`bench/scrapebench/`), 6 tiers, self-authored scrapers in a
bubblewrap sandbox.

**The only variable between arms is sampling.** Same model, same server process, same
fixtures, same harness commit — true for the t1–t3 rows. The t4/t5 rows were added later
under a restarted server and a metadata-only harness change; see *Limits*.

## Result

| tier | temp 0 | **temp 0.9 / top_p 0.9** | speedup |
|---|---|---|---|
| t1_article | **1290.2 s**, 6 attempts, hit turn cap | **69.2 s**, 2 attempts | **18.6×** |
| t2_boilerplate | **824.2 s — INFRA_ERROR**, 0 chars | **106.4 s**, 599 chars, OK | **7.7×** |
| t3_missing | 132.7 s, 8 attempts | 85.1 s, 4 attempts | 1.6× |
| t3_redirect | 134.9 s, 8 attempts | 159.7 s, 8 attempts | 0.8× |
| **t4_ratelimited** | **104.3 s**, 6 attempts, score **0.985** | 368.3 s, 12 attempts, score **1.000** | **0.28×** |

## UPDATE 2026-08-01 — t4 is a counter-example, and it matters

The original table stopped at four tiers because the recommended-sampling run was interrupted
before t4/t5 (see *Provenance*). Completing it changed the conclusion's shape.

**On t4_ratelimited, recommended sampling is 3.5× SLOWER** — 368.3 s / 12 attempts versus
104.3 s / 6 attempts at temp 0. Both arms pass. The scores differ (1.000 vs 0.985, recall
1.0 vs 0.970) but **that delta is not resolvable at K=1** per this receipt's own Limits, so
no quality claim is made in either direction — the honest reading is "both passed, one took
3.5× longer." The direction is reversed from t1/t2, and unlike the score gap, a 3.5×
wall-clock difference with 2× the attempts is well outside single-draw noise.

Mechanism that fits: **t4 is the tier that rewards a deterministic policy.** The task is
"back off on HTTP 429 instead of giving up or hammering" — one correct strategy, applied
patiently. Temp 0 locks onto a backoff loop and repeats it. Temp 0.9 re-decides the approach
on every attempt, so it explores twice as many attempts to reach the same place. On t1/t2 the
same variability is what *rescued* the model from a degenerate repetition loop.

**Revised claim.** Higher temperature does not make this model uniformly faster. It breaks
degenerate loops — which is worth 18.6× when a loop is what you are stuck in, and costs 3.5×
when the task wanted determinism. The headline finding stands, since a 7.7× rescue from a hard
INFRA_ERROR outweighs a 0.28× on a tier both arms pass. What does **not** stand is any reading
of the original four-row table as "recommended sampling is faster across the board."

The generalisation in *Why this matters for benchmarking* is unaffected: standardising on
temp 0 still misrepresents models tuned for higher temperatures. t4 shows the reverse error is
also real — standardising on a model's recommended sampling can cost wall-clock on tasks that
reward determinism. **The defensible position is to report the sampling used, not to pick one
standard.**

**t5_spa has no temp-0 counterpart.** The recommended arm scored **1.000** (222.5 s, 6
attempts, 13 turns, no cap, no infra errors), but the temp-0 Q4_K_M run never reached t5
either, so no speedup ratio can be computed for that tier and none is claimed. The Q6_K temp-0
arm (`qwopus6_t0`) does have a t5 result, but it is a different quantisation and is not a
controlled comparison.

**t2 went from a hard 500 to a clean answer.** At temp 0 the model emitted a tool-call
argument that llama-server rejected with:

```
Failed to parse tool call arguments as JSON: parse error at line 1, column 50041:
syntax error while parsing value - invalid string: missing closing quote
```

**Column 50041** — roughly a 50,000-character `write_file` argument, truncated mid-string
by `max_tokens`. Raising 4096 → 8192 did not fix it; it only let the runaway grow larger
before truncating. Four such 500s in that tier, including all three forced-turn retries.

## Why this is degenerate repetition, not slowness

The dense-vs-MoE decode difference is ~4× (Qwopus 10.08 t/s vs the 35B-A3B MoEs at
40–47 t/s), and it applies to every tier equally. It cannot explain an 18.6× gap on one
tier and 1.6× on another.

The tiers that blew up are the ones where the model writes a *long HTML-parsing program*;
the tiers that behaved are the ones dominated by short reasoning. Greedy decoding locked
the model into repetition inside long code payloads, and a little sampling entropy broke
the loop. Same failure family as the Laguna and Puzzle stopping-rule findings — **low-bit
models fail at stopping, not at answering** — expressed here inside tool arguments rather
than prose.

## The general claim

**"Temperature 0 for reproducibility" is not a neutral choice.** It is a *different
operating point*, and for a model tuned to 0.85–1.0 it can be a broken one. The failure
presents as timeouts and HTTP 500s with nothing pointing at sampling.

Any benchmark that standardises on temp 0 will systematically misrepresent models tuned
for higher temperatures — scoring a sampling mismatch as a capability gap.

**This lands on our own practice.** Every ScrapeBench arm so far, and the entire
HermesBench V5/V6 campaign, ran temp 0 for exactly the conventional reason. V5 and KAT
did not blow up, so those results stand. But the justification was wrong, and any future
model must be run at its recommended settings — or at both, reported separately.

## Prediction scoring

Logged before the run: *temp 0.9 substantially reduces the runaway*, confidence **0.65**.
**CONFIRMED**, and the effect is far larger than anticipated (18.6×, plus an INFRA_ERROR
flipping to a clean pass).

## Limits — stated plainly

- **K=1 per arm.** Temp 0.9 is not deterministic, so *score* differences between arms are
  not resolvable here. The wall-clock and INFRA_ERROR results are far outside single-draw
  noise; small score deltas are not.
- The temp-0 arm never completed `t5_spa` — the client hung (see below), so that tier has
  no temp-0 comparison.
- **t4/t5 of the recommended arm were run later** (2026-08-01) than t1–t3. Same box, same
  model file, same quant, same sampling, same server binary (`~/buun_vbr/build/bin`, launched
  by `bench_server.sh qwopus`) — but **a different server process**, and **`run.py` had been
  modified** in between to add the `meta.json` provenance fix (defect 6 below). That change
  is additive metadata writing and does not touch prompts, tools, sampling or the request
  path, so it should not affect the result — but "same server process, same harness commit"
  as claimed at the top of this receipt is **not** true of the t4/t5 rows, and a
  process-level confound cannot be fully excluded for them.
- The t4 reversal is **one tier, K=1**. It is enough to falsify "faster across the board"
  (a universal claim dies to one counter-example) but not enough to characterise *which*
  tasks reward determinism. The mechanism offered is a hypothesis, not a measurement.
- One model, one quant (Q4_K_M), one hardware config. Whether this generalises to other
  merges or other quant levels is untested.
- Attempt counts are confounded with the runaway: fewer attempts at 0.9 partly reflects
  not wasting turns on truncated tool calls.

## Harness defects found and fixed during this run

Six in one session, four of which initially presented as model failures. Recorded
because the pattern is the finding:

1. **`max_tokens` 4096 truncated tool-call JSON** on long code payloads (KAT t2) → 8192.
   Insufficient alone; see the 50k-column runaway above.
2. **Server 500s scored as 0.000** — indistinguishable from a capability failure. Now
   tracked as `INFRA_ERROR` and *excluded* from scoring, with 3× retry on the forced turn.
3. **Turn cap produced `output=""` → score 0.** Three V5 tiers were scored 0 while having
   already succeeded (t5 had retrieved the body via the API route). Fixed with a
   forced-answer turn plus a `hit_turn_cap` flag.
4. **t5 scored API discovery from the prose answer, not the transcript.** V5 found
   `/api/article/cs-rendering-101` — self-correcting from a 404 on `/api/articles/` — and
   lost the credit for answering cleanly. **Re-scores 0.75 → 1.000.**
5. **`httpx` bare `timeout=N` hung 35+ minutes** on `t5_spa` while `/slots` reported
   `is_processing: false` and both GPUs sat at 0%. Now explicit
   `httpx.Timeout(connect=15, read=N, write=60, pool=15)`.

6. **`meta.json` was written only after all tiers completed** (found 2026-08-01). When the
   recommended-sampling run was interrupted before t4/t5, its four finished tiers were left
   with **no record of the model or sampling that produced them** — result files that cannot
   be reproduced from their own contents. The parameters for the original `qwopus_rec01`
   rows in the table above had to be recovered from this receipt's prose rather than from
   the run artifact, which is exactly backwards.

   Fixed: `run.py` writes `meta.json` **before** the tier loop and refreshes it after each
   tier, adding `tiers_completed`, `turn_timeout` and `tool_timeout`. An interrupted run now
   self-documents. This is the same failure class as the `hermes01` result that
   `bench_server.sh` was built to prevent — a number whose conditions cannot be
   reconstructed — recurring on the client side after being fixed on the server side.

## Provenance

- `results/qwopus_rec01_t45/` (temp 0.9 t4/t5, added 2026-08-01; `meta.json` records the
  full run params — the first arm to carry its own provenance, see below)
- `results/qwopus_full01/` (temp 0), `results/qwopus_rec01/` (temp 0.9 / top_p 0.9) —
  full transcripts per tier
- Serving sidecar on `.73`: `~/bench-stack/serving_config_qwopus.json`
- Server log: `~/bench-stack/server_qwopus.log` (the 500s and column-50041 errors)
- Comparison arms: `results/v5_full02/`, `results/kat_full01/`
