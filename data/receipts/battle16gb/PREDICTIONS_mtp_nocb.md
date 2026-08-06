# Predictions — MTP paired probe, caching ON, continuous batching OFF

Logged 2026-07-30 **before** the run. Tests the mechanism hypothesis left open by
`MTP_CACHEPROMPT_FALSIFICATION.md`.

## Design

**Single variable vs the ORIGINAL run:** drop `-cb` from the server flags. The probe is the
original `detprobe.json` (no `cache_prompt` key, so the server default of **true** applies).
Everything else byte-identical: `-c 65536 -b 1024 -ub 512 -ctk f16 -ctv f16 -fa on -np 1
-ngl 99 --cache-ram 0 --jinja`, temp 0, `max_tokens 1200`, 2 draws × 3 alternating restarts.

New output dir `mtp_paired_nocb/`; the two prior runs are untouched.

## The three-cell design this completes

| cell | `cache_prompt` | `-cb` | MTP result |
|---|---|---|---|
| original | true (default) | on | **4 distinct / 6** |
| no-cache | **false** | on | **1 distinct / 6** |
| **this run** | true (default) | **off** | ? |

## Predictions

| id | claim | confidence |
|---|---|---|
| **P-B1** | Base stays 6/6 byte-identical. | **0.95** |
| **P-B2** | MTP becomes deterministic (1 distinct / 6) — i.e. `-cb` was the source. | **0.30** |
| **P-B3** | MTP still shows ≥2 distinct outputs — i.e. `-cb` is *not* the source, and the cache path itself is. | **0.65** |
| **P-B4** | If MTP is unstable, `ce6f4cce8990c174` is the modal hash (it was 3/6 in the original run and 6/6 with caching off — it is the true greedy continuation). | **0.60** |

## Why I am predicting AGAINST my own hypothesis

I proposed continuous batching as the best candidate. Stating the weakness plainly before the
run, because I just miscalibrated badly in the other direction:

**With `-np 1` and strictly sequential requests, `-cb` may be inert.** Continuous batching exists
to interleave prefill of new requests with decode of in-flight ones. There is only ever one
sequence here and the probe issues draws one at a time, so there is likely nothing to interleave.
If that is right, removing `-cb` changes nothing and P-B2 fails.

That makes this test worth running as **elimination** rather than confirmation. A P-B2 failure
does not leave us stuck — it localises the nondeterminism to the `cache_prompt` code path itself
(prompt chunking / prefix-matching / slot state), which is a much narrower place to look than
"somewhere in speculative decoding."

I am deliberately not inflating P-B2 to make my own hypothesis look good. After scoring two 0.93
predictions as falsified an hour ago, the calibration correction goes *toward* humility about
mechanisms I have not yet tested.

## Scoring — RUN COMPLETE 2026-07-30

**P-B1 CONFIRMED · P-B2 (0.30) CONFIRMED · P-B3 (0.65) FALSIFIED · P-B4 n/a.**

MTP went **fully deterministic** with `-cb` off and caching left ON — 1 distinct output across 6
draws, byte-identical to the `cache_prompt:false` cell. **Instability requires both flags.**

My stated reason for doubting my own hypothesis — "`-cb` may be inert at `-np 1`" — was wrong.

Full result, the three-cell table, the deployment recipe, and the calibration note:
**`MTP_CACHEPROMPT_FALSIFICATION.md`**.
