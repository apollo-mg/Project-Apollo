# FALSIFIED: MTP is deterministic at temp 0. The instability was MTP × prompt-caching.

RX 9070 XT (gfx1201), `llama_cpp_turboquant @ c26cbdffc`, `Qwen3.6-35B-A3B-UD-IQ2_M`.
Date 2026-07-30. Predictions logged before the run in `PREDICTIONS_mtp_cacheprompt.md`.

**This overturns the headline of `MTP_DETERMINISM.md` and forces re-attribution in
`MTP_STRUCTURED_OUTPUT.md` and `MTP_HA20_AND_MARGIN.md`.**

## The result

Single variable changed from the original run: `"cache_prompt": false` added to the probe body.
Serving flags, prompt, temperature 0, `max_tokens 1200`, and the 2-draws × 3-alternating-restarts
design are byte-identical (`diff` of the two scripts shows only `OUT`, `PROBE`, `PORT`).

| arm | `cache_prompt` default (true) — original | **`cache_prompt: false` — this run** |
|---|---|---|
| base | 1 distinct / 6 draws | **1 distinct / 6 draws** |
| **MTP** | **4 distinct / 6 draws** | **1 distinct / 6 draws** |

Hashes recomputed directly from the raw response bodies, independent of the script's own analysis:

```
base_r1_d1..base_r3_d2   f43730ef53883d95   4864 chars   (x6)
mtp_r1_d1 ..mtp_r3_d2    ce6f4cce8990c174   4832 chars   (x6)
```

Config fidelity confirmed against the original run: base 79.44–79.74 t/s (orig 79.5–79.9),
MTP 98.23–98.38 t/s (orig 98.3–99.5), draft acceptance 0.62172 on all three MTP reps
(orig 0.607–0.624).

**MTP is fully deterministic at temperature 0 once prompt caching is off.** It produces a
*different* output from base (`ce6f4c` vs `f43730`) — deterministically. That difference is
exactly what ggerganov describes: different kernels for different batch sizes. Expected, benign,
reproducible.

Telling detail: `ce6f4cce8990c174` is not a new output. It appeared **3 of 6 times in the
original cache-on run**. It is the model's true greedy continuation; the other three hashes in
that run (`f3d8ae`, `14ec99`, `79c548`) were cache-induced deviations from it.

## Prediction scoring — I was badly wrong

| id | claim | conf | outcome |
|---|---|---|---|
| P-C1 | base stays 6/6 identical | 0.95 | **CONFIRMED** |
| P-C2 | MTP first-draws differ across restarts (≥2 distinct) | **0.93** | **FALSIFIED** — 1 distinct |
| P-C3 | MTP within-instance unstable in ≥2 of 3 | 0.70 | **FALSIFIED** — 0 of 3 |
| P-C4 | MTP ≥2 distinct across all 6 draws | **0.93** | **FALSIFIED** — 1 distinct |
| P-C5 | MTP fully deterministic | **0.05** | **CONFIRMED** |

Two predictions at 0.93 falsified, and the 0.05 outcome is what happened. That is not bad luck;
it is a reasoning error with a specific, identifiable cause.

**The error.** I argued that draw 1 of a fresh instance was a clean control — "full prefill,
no cache exists yet, nothing about caching can explain it" — and on that basis called the
cold-start result *airtight, no confound* while flagging only the within-instance half as
suspect. That was wrong. `cache_prompt: true` evidently changes the prompt-processing path
**even when the cache is empty**, so draw 1 was never the clean control I claimed. I had
correctly identified a confound and then incorrectly reasoned about its scope, which is worse
than missing it — I gave a contaminated result a clean bill of health and raised confidence on it.

## What this does to our other MTP receipts

**`MTP_DETERMINISM.md` — headline is wrong as written.** "MTP breaks determinism at temperature 0"
must become "MTP is deterministic at temperature 0; MTP *with prompt caching enabled* is not."

**`MTP_HA20_AND_MARGIN.md` — attribution changes, finding survives.** stevibe's HA-20 runner was
used unmodified and does not set `cache_prompt`, so it ran with the default (true). The 35 %
scenario instability is therefore **MTP × caching**, not MTP alone. Needs re-running with caching
disabled to separate them. *Operationally this matters less than it sounds*: real agent harnesses
use prompt caching by default — it is the whole point of a multi-turn agent loop — so the
practical warning stands. The mechanism attribution is what changes.

**`MTP_STRUCTURED_OUTPUT.md` — same caveat.** Same runner, same default.

**The flip-margin measurement (0.03125, 99.25th percentile) is unaffected** — it measured how
close near-ties are in this model's logit distribution, which is a property of the model, not of
the probe.

## RESOLVED — it takes BOTH continuous batching and prompt caching

Third cell run 2026-07-30 (`PREDICTIONS_mtp_nocb.md`): original probe (`cache_prompt` default
**true**), single change — **`-cb` removed**.

| cell | `cache_prompt` | `-cb` | base | **MTP** |
|---|---|---|---|---|
| original | true | on | 1 distinct / 6 | **4 distinct / 6** |
| no-cache | **false** | on | 1 distinct / 6 | **1 distinct / 6** |
| **no-cb** | true | **off** | 1 distinct / 6 | **1 distinct / 6** |

**Disabling *either* flag fully restores determinism.** Instability requires the combination.

And both interventions land on the **same output, byte-identical**:

```
mtp_paired          mtp   distinct=4  [14ec998d, 79c54850, ce6f4cce, f3d8ae79]
mtp_paired_nocache  mtp   distinct=1  [ce6f4cce8990c174]
mtp_paired_nocb     mtp   distinct=1  [ce6f4cce8990c174]   <- identical text, 4832 chars
base (all three cells)    distinct=1  [f43730ef53883d95]   <- identical text, 4864 chars
```

`ce6f4cce8990c174` is the model's true MTP greedy continuation. It was already the modal hash in
the unstable run (3 of 6); the other three were perturbations of it. MTP's output is
deterministically *different* from base — which is exactly ggerganov's batch-size-kernel
explanation, and is benign.

Decode cost of `-cb` off, at `-np 1`: MTP 97.38–97.89 t/s vs 98.23–98.38 with it on (**~0.7 %**);
base 79.00–79.27 vs 79.44–79.74. Draft acceptance 0.62172 in every MTP rep across all cells.

### The recipe

**MTP's +23 % decode is available deterministically.** Two levers, and for agent work they are
not equivalent:

| lever | determinism | keeps prompt cache? | cost |
|---|---|---|---|
| **`-cb` off** | yes | **yes** | ~0.7 % decode at `-np 1`; more under real concurrency |
| `cache_prompt:false` | yes | **no** | loses all prefix reuse — brutal for multi-turn |

**For a single-user agent loop, `-cb` off is clearly the right lever**: multi-turn agents live on
prompt-cache prefix reuse, and giving that up to buy determinism is a bad trade when turning off
continuous batching buys the same thing for ~0.7 %. The caveat is concurrency — `-cb` off costs
much more when serving parallel requests, so this recipe is for `-np 1`-style single-session
serving, not a multi-user endpoint.

**This is the test to re-run HA-20 under**: `-cb` off, caching left on, which should recover both
determinism and the cache benefit.

### Mechanism

With `-cb`, prefill can be chunked and interleaved with decode; with `cache_prompt`, prefix
matching changes where those chunk boundaries fall. Together, batch composition becomes dependent
on scheduling rather than fixed by the request. Different batch composition selects different
kernels, and under IQ2_M the near-ties (flip margin 0.03125) are tight enough that the choice
changes the emitted token. Removing either flag makes batching deterministic again.

Stated as the best hypothesis consistent with a complete 2×2-minus-one design — not as something
read out of the scheduler source. The empirical claim (needs both flags) is solid; the
chunk-boundary story is inference.

## Prediction scoring, cell 3

| id | claim | conf | outcome |
|---|---|---|---|
| P-B1 | base stays 6/6 identical | 0.95 | **CONFIRMED** |
| P-B2 | MTP deterministic — `-cb` was the source | **0.30** | **CONFIRMED** |
| P-B3 | MTP still unstable — cache path is the source | 0.65 | **FALSIFIED** |
| P-B4 | modal hash `ce6f4cce…` if unstable | 0.60 | n/a — MTP was stable |

**Calibration note, two runs in a row wrong in opposite directions.** Cell 2: two predictions at
0.93 falsified (overconfident that MTP alone was nondeterministic). Cell 3: the hypothesis I
proposed, deliberately priced at 0.30, was right — I over-corrected toward humility after being
burned. My stated reason for doubting it ("with `-np 1` and sequential requests, `-cb` may be
inert") was empirically wrong: removing `-cb` changed the result decisively.

## Provenance

- `~/projects/HermesAgent-20/mtp_paired_nocache.sh` (sed-derived from `mtp_paired.sh`; only
  `OUT`, `PROBE`, `PORT` differ — verified by `diff`)
- Probe: `scratchpad/detprobe_nocache.json` — differs from `detprobe.json` by the single key
  `cache_prompt` (verified by key-set comparison)
- Outputs: `~/projects/HermesAgent-20/mtp_paired_nocache/*.json`, log `paired.log`
- Original run retained unmodified at `~/projects/HermesAgent-20/mtp_paired/`
- All 12 outputs `finish_reason: length` in both arms — both truncated at the same 1200-token
  budget, so the comparison is like-for-like
