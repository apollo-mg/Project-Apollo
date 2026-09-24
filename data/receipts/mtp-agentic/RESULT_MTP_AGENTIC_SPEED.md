# With the prompt cache on, MTP finishes agent tasks 17 % faster, and its outcome effect REVERSED sign between two runs

**2026-09-24**, RX 9070 XT, buun `38ada0e1b`, `Qwen3.8-27B-UD-IQ3_XXS`, argus `families_v4.json` (40 items), MTP off/on
x seeds 1-3, **prompt cache ON**, `argus/run_mtp_agentic.sh cache`. Prereg `PREREG_MTP_AGENTIC_SPEED.md` (`2fa0504`).
Scorer `analyze_mtp_speed.py`. Raw: `raw_cache/`. 240 rows, **0 timeouts, 0 infra voids**.

## Primary (registered): end-to-end time per task

| | |
|---|---:|
| geo-mean time ratio MTP / off | **0.834** (95 % CI 0.765-0.909) |
| sign-flip p (MC 1e6) | 0.0001 |
| items where MTP was faster | 32 / 40 |

**MTP completes agent tasks ~17 % faster.** Prediction was [0.60, 0.85] at 0.60 confidence. **Held**, at the
conservative end. For comparison, the cache-off run gave 0.947.

**Why only 17 % when decode got faster** (server logs, all three seed pairs):
- With the cache on, **decode is ~90 % of server time**.
- MTP decodes agent turns at **39-40 t/s vs 27.7 t/s (1.43x)**, well below the ~2x measured on a code prompt.
  Agent turns are prose plus tool JSON, with lower draft acceptance.
- Server decode time fell to 0.67x. The rest of each task (tool execution, harness, prefill) is not accelerated.

## Secondary (registered as descriptive): expected time to success

Total seconds / passes: **0.651x** (bootstrap 95 % CI 0.517-0.799). That is 86.0 s per success off vs 56.0 s on.
It combines the speed gain with this run's higher MTP pass rate (below).

## The outcome effect reversed

The same item-level test as `RESULT_MTP_AGENTIC.md` (judge rule), run here **descriptively** (outcomes were not
the registered test of this prereg):

| run | pass off | pass MTP | mean d | 95 % CI | p | items better / worse | outcome flips better : worse |
|---|---:|---:|---:|---|---:|---|---|
| cache OFF (09-23) | 75.0 % | 69.2 % | **-5.8 pp** | [-12.2, +0.5] | 0.12 | 2 / 7 | 4 : 11 |
| **cache ON (09-24)** | 69.2 % | 78.3 % | **+9.2 pp** | [+2.8, +15.5] | **0.0098** | 10 / 1 | **14 : 3** |

MTP led in **every** seed of the cache-on run (27 vs 30, 29 vs 32, 27 vs 32).

**Reading:**
- A 40-item x 3-seed run can produce a nominally significant MTP effect in *either* direction, depending on
  serving conditions.
- Pooled over both runs, outcome flips go **18 better : 14 worse** under MTP. There is no consistent direction.
- The yesterday receipt's "leaning harm" does not replicate. The deployment-relevant reading is now:
  1. **MTP changes agent trajectories almost every time** (path-only changes: 102/120 and 100/120 runs).
  2. **It does not shift outcomes in a stable direction.**
  3. **It is ~17 % faster end-to-end** with the cache on.
- **Keep MTP on for agents on this model.** The earlier caution stands only for unattended, irreversible actions,
  where *any* trajectory change deserves a verifier regardless of direction.

**What differs between the two runs, so the reversal is not attributed to the cache alone:**
- Prompt cache on/off. With the cache on, MTP output is bistable (INDEX: cache x speculation).
- **The agent's calendar.** Both runs told the agent `UTC-12` via `HERMES_TIMEZONE` (the flaw corrected in
  `RESULT_MTP_AGENTIC.md`). The cache-off run showed it **Wednesday**, the cache-on run **Thursday**; the fake world is
  anchored to Thursday 09-24. The OFF arm's pass rate moved 75.0 -> 69.2 % between runs and MTP's 69.2 -> 78.3 %.
  Both arms moved, so absolute rates are not comparable across runs, only within each.
- It was a different day and a different server process.

## What this adds

The first end-to-end timing of MTP on multi-turn agent tasks under realistic serving. It also shows that the
single-run outcome signal is unstable enough to flip sign. That changes how any "speculation hurts/helps agents"
claim from one run should be read, including ours.

## Not established

- One model, card, harness and corpus.
- Both runs carry the UTC-12 calendar flaw.
- Why the direction reversed (cache, calendar, or chance) is not separable here.
- The v5 corpus (83 items, now validating) with the timezone fixed is the instrument that could.
