# Predictions — MTP paired determinism re-run with `cache_prompt:false`

Logged 2026-07-30 **before** the run. Closes the confound identified in
`MTP_UPSTREAM_ROOT_CAUSE.md` §A: the original probe body never set `cache_prompt`, so draw 2 of
each instance hit a warm prompt cache and skipped prefill.

## Design

**Single variable.** Only `"cache_prompt": false` is added to the probe body. Everything else —
model, serving flags (`-c 65536 -b 1024 -ub 512 -ctk f16 -ctv f16 -cb -fa on -np 1 -ngl 99
--cache-ram 0 --jinja`), prompt, `temperature 0`, `max_tokens 1200`, 2 draws × 3 alternating
restarts per arm — is byte-identical to the original.

**No fixed seed added, deliberately.** It would be a second variable, and it is provably inert
here: the base arm produced **6/6 byte-identical** outputs across 3 restarts *without* a fixed
seed. If RNG were in play at temp 0, base would have varied too. This also means the objection
that killed upstream [#23302](https://github.com/ggml-org/llama.cpp/issues/23302) does not
apply to our design.

**New output directory** (`mtp_paired_nocache/`). The original `mtp_paired/` is evidence for the
first run and must not be clobbered.

## Predictions

| id | claim | confidence |
|---|---|---|
| **P-C1** | Base stays **6/6 byte-identical**. Removing cache reuse should not destabilise an already-stable arm. | **0.95** |
| **P-C2** | MTP first-draws still differ across the 3 restarts (**≥2 distinct**, most likely 3). Draw 1 was *already* cold in the original run — no cache existed yet — so this behaviour should be unchanged. | **0.93** |
| **P-C3** | MTP **within-instance** (draw 1 vs draw 2) is still UNSTABLE in **≥2 of 3** instances. This is the actual test. | **0.70** |
| **P-C4** | MTP shows **≥2 distinct outputs across all 6 draws**. | **0.93** |
| **P-C5** | MTP becomes **fully deterministic** (1 distinct output / 6). Would mean the entire instability was prompt-cache interaction. | **0.05** |

P-C4 and P-C5 are near-complements; the small gap is the chance the run fails to produce a
usable sample at all.

## Why P-C3 is only 0.70 when P-C2 is 0.93

They test different things. P-C2 is already established by data that no cache confound touches
(three fresh processes, three different first outputs). P-C3 is the claim under audit: with the
warm cache removed, draw 2 becomes an honest repeat of draw 1 on the same process. If MTP's
nondeterminism is driven purely by *inter-process* variation — allocator layout, kernel autotune
state, memory placement fixed at load — then within a single process it could well be stable, and
P-C3 fails. If it is driven by something that re-rolls per request, P-C3 holds.

**Either outcome is informative.** A P-C3 failure narrows the mechanism to load-time state and
means the within-instance half of our claim gets withdrawn — the cold-start half survives
untouched either way.

## Scoring — RUN COMPLETE 2026-07-30

**Result: P-C1 confirmed, P-C2 / P-C3 / P-C4 FALSIFIED, P-C5 (0.05) CONFIRMED.**

MTP was **fully deterministic** with `cache_prompt:false` — 1 distinct output across 6 draws,
where the cache-on run gave 4. Two predictions held at 0.93 were wrong.

Full result, scoring table, error analysis, and the consequences for the other MTP receipts:
**`MTP_CACHEPROMPT_FALSIFICATION.md`**.

The specific reasoning error: I claimed draw 1 of a fresh instance was a clean control because
no cache existed yet. `cache_prompt:true` changes the prompt-processing path even on an empty
cache, so it never was.
