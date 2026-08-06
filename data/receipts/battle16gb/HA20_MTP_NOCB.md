# The `-cb` off recipe does NOT transfer to the agent loop

RX 9070 XT, `llama_cpp_turboquant @ c26cbdffc`, `Qwen3.6-35B-A3B-UD-IQ2_M`, stevibe's HA-20
runner unmodified. Date 2026-07-30. Predictions in `PREDICTIONS_ha20_mtp_nocb.md`.

Single variable vs the original leg: **`-cb` removed**. Same model, same
`-c 65536 -b 1024 -ub 512 -ctk f16 -ctv f16 -fa on -np 1 -ngl 99 --cache-ram 0 --jinja`,
same asymmetric K (base 1, MTP 3), same 300 s / 240 s token-matched timeouts.

## Headline

`MTP_CACHEPROMPT_FALSIFICATION.md` showed `-cb` off makes the single-prompt probe **perfectly
deterministic** (6/6 byte-identical). **That determinism does not carry into HA-20.**

| | verdict-unstable scenarios |
|---|---|
| original leg (`-cb` on) | **7 / 20 (35 %)** |
| **this leg (`-cb` off)** | **4 / 20 (20 %)** |

Improved, not fixed. And the improvement cannot be credited to `-cb` yet — see the missing
control below.

## Results

```
scen    base           mtp_r1         mtp_r2         mtp_r3         flag
HA-04   FAIL/35        FAIL/35        NOVERDICT      FAIL/35        VERDICT-UNSTABLE
HA-05   PARTIAL/90     FAIL/50        NOVERDICT      PASS/100       VERDICT-UNSTABLE
HA-12   PASS/100       FAIL/20        PASS/100       PASS/100       VERDICT-UNSTABLE
HA-19   PASS/100       PASS/100       PARTIAL/80     PARTIAL/80     VERDICT-UNSTABLE
HA-16   FAIL/30        FAIL/15        FAIL/30        FAIL/15        score-varies
(15 others identical across all three reps)
```

- fully identical across 3 reps: **15/20**
- verdict-stable but score varies: **1** (HA-16, 15/30/15)
- base 13 PASS · MTP reps 12 / 12 / 13 PASS
- final draft acceptance **0.80** (vs 0.622 on the prose probe — structured output drafts better,
  consistent with `MTP_STRUCTURED_OUTPUT.md`)

**HA-05 produced three different outcomes** (FAIL/50, no-verdict, PASS/100) — maximum instability.

## Prediction scoring — 4 of 5 falsified

| id | claim | conf | outcome |
|---|---|---|---|
| P-H1 | MTP reps agree on ≥18/20 | 0.70 | **FALSIFIED** — 16/20 |
| P-H2 | perfect 20/20 agreement | 0.45 | **FALSIFIED** |
| P-H3 | residual variation includes HA-07 or HA-08 | 0.60 | **FALSIFIED** — both were rock stable |
| P-H4 | MTP majority within 1 of base | 0.70 | **CONFIRMED** — 12 vs 13 |
| P-H5 | zero runaways, or runaways in all 3 reps | 0.55 | **FALSIFIED** — 2 runaways, rep 2 only |

P-H3 was wrong in an instructive way. I predicted the residual instability would land on the
timeout-prone scenarios (HA-07, HA-08, which hit the ceiling in the original run) and be a
*clock artifact*. Instead those two were perfectly stable, and the runaways hit **HA-04 and
HA-05**, which base completes in 41 s and 42 s. Whatever is happening is not scenarios sitting
near the time limit.

## Two structural problems that make the 20 % unattributable

**1. There is no base K=3 control — and there never was.** Base ran K=1 here and in the original
leg, on the documented grounds that base is byte-deterministic. But that determinism was
established by the *paired probe*: one request, fresh server. It has never been demonstrated
across a 20-scenario multi-turn agent sequence. **We cannot attribute the residual 4/20 to MTP
without knowing base's rep-to-rep stability under the same conditions.**

Prior evidence says the harness itself contributes: HA-04 was already measured **bistable at
temperature 0** on `.73` (35/100/100/35) with a different model — and HA-04 is one of the four
unstable scenarios here.

**2. The MTP arm runs all three reps against ONE server process.** Confirmed from the log —
a single `mtp server healthy pid=3550242`, then reps 1-3 inside it. The paired probe **restarted
the server for every rep**. So the two experiments do not measure the same thing:

| | paired probe | HA-20 leg |
|---|---|---|
| server | fresh per rep | **one process, all 3 reps** |
| requests | 1 | hundreds, multi-turn |
| prompt cache | controlled | reused across scenarios |

The server log shows that machinery actively churning:

```
W slot update_slots: forcing full prompt re-processing due to lack of cache data
W slot update_slots: erased invalidated context checkpoint (pos_min=2724 … size=68.188 MiB)
  … five consecutive checkpoint erasures on one task …
```

Rep 2 also shows a ~10-minute degraded window — HA-04 and HA-05 both burning the full 240 s,
then HA-06 taking **158 s against 24 s and 21 s in the other two reps** — followed by clean
recovery from HA-07 onward. That is the signature of accumulated server state, not of
per-request numerical divergence.

**So the residual instability is plausibly about long-lived slot/cache state across a long
request sequence, which is a different phenomenon from the logit-level nondeterminism the probe
measures.** `-cb` off fixes the latter and evidently does little for the former.

## What this does to the recipe

`MTP_CACHEPROMPT_FALSIFICATION.md`'s recipe stands **for its actual scope**: single-prompt,
fresh-server, reproducible generation. That is exactly the setting benchmarks and eval harnesses
run in, so it is not a small claim.

**It must not be advertised as "MTP is safe for agent workloads."** This run is direct evidence
against that reading. Anyone re-running HA-20 with `-cb` off will still see ~20 % of scenarios
move between reps.

## Next test — the control that should have come first

**Base, K=3, `-cb` off, same single-server design.** ~30 minutes (the MTP arm's three reps took
27). Three outcomes:

- base ≈ 0/20 unstable → the residual 4/20 **is** MTP, and the recipe genuinely does not transfer
- base ≈ 4/20 unstable → the instability is **the harness and server state, not MTP at all**, and
  a large part of `MTP_HA20_AND_MARGIN.md`'s original 35 % needs re-attribution too
- base somewhere between → partial contribution, quantifiable

Given HA-04's known bistability at temp 0 on other hardware, the middle outcome is live. This
control gates any further claim about MTP and agent workloads.

## Provenance

- `~/projects/HermesAgent-20/run_ha20_mtp_nocb.sh` (sed-derived from `run_ha20_mtp_ab.sh`;
  `diff` shows only `OUT`, `PORT`, and the removal of `-cb`)
- `~/projects/HermesAgent-20/ha20_mtp_ab_nocb/` — 80 scenario logs, `arm.log`, `server_*.log`
- Original leg retained at `~/projects/HermesAgent-20/ha20_mtp_ab/`
- Smoke test passed on both arms (`tool_calls True`) — no silent template rejection
