# Leading result — the latch tracks the GPU power cap, not the software

**Date:** 2026-09-10. **Status:** strongest hypothesis so far, **not yet confirmed** (n=8, p=0.071).
**Disclosed by Mark 2026-09-10 ~11:15:** he lowered the RX 9070 XT power cap in LACT from
**374 W to 330 W** ("about factory levels") after noticing transient draws **above 375 W** in his
own telemetry, wondering whether marginal power was causing numerical errors too small to fault
the driver. He flagged it himself as an unlogged mid-experiment change.

**`/etc/lact/config.yaml` mtime: `2026-09-09 22:55:55`.** That timestamp splits the ledger.

## The ledger, split on the cap change

| run | start | outcome | cap |
|---|---|---|---|
| bitdepth_iq3xxs_v5 | 13:49 | **LATCH** (task 16) | 374 W |
| cacheab_ctrl | 18:41 | **LATCH** (task 2) | 374 W |
| cacheab_treat | 20:43 | **LATCH** (task 8) | 374 W |
| noproxy_ctl | 22:15 | clean | 374 W |
| proxy_repeat | 22:31 | **LATCH** (task 2) | 374 W |
| *cap 374 W → 330 W at 22:55:55* | | | |
| decoupled_run | 23:57 | clean | 330 W |
| pd2_novbrcache | 00:32 | clean | 330 W |
| pd2_control | 00:48 | clean | 330 W |

**374 W: 4/5 latched. 330 W: 0/3 latched.** One-tailed Fisher exact **p = 0.071**.

### The single-variable pair

| run | drain mode | server flags | cap | outcome |
|---|---|---|---|---|
| `proxy_repeat` | inline | stock | **374 W** | **LATCH at task 2** |
| `pd2_control` | inline | stock | **330 W** | **clean 20/20** |

Identical harness, identical proxy mode, identical server flags. Only the power cap differs.

## What this explains that nothing else did

- **The "time ordering"** noted in last night's retraction (every latch before 22:31, every run
  after 23:57 clean) was never about time. It was the 22:55:55 cap change.
- **Why "backpressure isolated" looked true then failed its control.** `decoupled_run` was the
  first run after the cap change. The drain mode was never the variable.
- **Why P-D3 failed at 85%.** The positive control ran at 330 W.
- **Stochastic trigger** — transient power excursions are random.
- **Never in the first ~4 generations** — sustained load is needed before spikes occur.
- **Latching, cleared only by restart** — a corrupted KV block persists until the cache is rebuilt.
- **Degenerate output specifically** — silent compute corruption in attention/KV produces garbage
  tokens, not a crash. Consistent with `/` repetition and with Mark's original intuition.

## What it does NOT establish

- **n = 8, p = 0.071.** Not significant at 0.05.
- **Power cap is still confounded with time** — every 330 W run is also later.
- No mechanism traced. "Marginal power → silent numerical error → corrupt KV" is plausible and
  matches the symptom, but nothing has been instrumented at the hardware level.
- **Today's telemetry, at the 330 W cap, still records 335 W peaks and 85 °C junction.** So
  transients above cap have not been eliminated, only reduced.

## Consequence for the ongoing experiment

`latch-interleaved` (3 KV types × 3 reps) is running **entirely at 330 W**. If power is the cause
it will return 9 clean runs and say nothing about VBR. That is still useful — it would make the
330 W denominator 0/12 against 4/5 at 374 W (p ≈ 0.005) — but it does not test the KV question
it was designed for.

## Consequence for the Discord claim

"Pretty sure it's specific to your fork" now looks **unlikely to be true**. If the cause is power
delivery on this specific card, the fork is incidental — it is simply the only build these runs
used. **This should be corrected to buun before he spends time on it.**

## Confirmatory test (needs Mark's decision)

Restore the cap to 374 W and re-run the identical configuration, interleaved with 330 W runs,
3 reps each, VBR, no proxy, telemetry logged throughout. Latches returning at 374 W and staying
absent at 330 W would settle it.

**This deliberately runs the card at a setting suspected of producing silent computation errors.**
374 W is within the card's own `power1_cap_max` and is where it ran for months, so this is not
exotic — but it is intentionally provoking a fault, and it is Mark's call, not mine.
