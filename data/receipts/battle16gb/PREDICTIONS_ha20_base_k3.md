# Predictions — HA-20 BASE K=3 control, `-cb` off

Logged 2026-07-30 **before** the run. This is the control that `MTP_HA20_AND_MARGIN.md` and
`HA20_MTP_NOCB.md` both needed and never had.

## The question

Both HA-20 legs ran **base at K=1**, justified by "base is byte-deterministic." That determinism
was established by the *paired probe*: one request, fresh server. It has **never** been
demonstrated across a 20-scenario multi-turn agent sequence against a long-lived server.

So when MTP shows 4/20 (this leg) or 7/20 (original) scenarios moving between reps, we have no
idea how much of that is MTP and how much is the harness plus accumulated server state.

## Design

Mirrors the MTP arm **exactly**, so the two are comparable:

- base, **K=3**, all three reps against **one server process** (same as the MTP arm)
- `-cb` off, caching left on, `-np 1`, everything else identical to `run_ha20_mtp_nocb.sh`
- **300 s/scenario** — base's own token-matched budget (23.7k tokens at 79.5 t/s), matching both
  prior base arms. Token-matched, not wall-matched, is the established convention here.

Output `ha20_base_k3_nocb/`; prior runs untouched.

## Predictions

| id | claim | confidence |
|---|---|---|
| **P-BC1** | base shows **≤1** verdict-unstable scenario | **0.60** |
| **P-BC2** | base shows **0** — fully reproducible across 3 reps | **0.40** |
| **P-BC3** | base shows **≥3** unstable, i.e. comparable to MTP's 4/20 → the instability is the harness, not MTP | **0.25** |
| **P-BC4** | base produces **zero** no-verdict runaways (MTP rep 2 had two) | **0.70** |
| **P-BC5** | if base has any unstable scenario, **HA-04** is among them | **0.40** |

## Reasoning, and where it could break

**For base being stable:** with `-cb` off, per-request numerics are deterministic (6/6 in the
probe). Scenario order is fixed, the runner spawns a fresh node process per scenario, and
different scenarios share little prompt prefix, so cross-scenario cache coupling should be weak.
Within a scenario, turn N+1 reuses turn N's cache — deterministic if turn N was.

**For base being unstable:** HA-04 was already measured **bistable at temp 0** on `.73`
(35/100/100/35). That is direct evidence the harness can vary without MTP. Caveat: `.73` is a
different node with 15 GB RAM plus swap, so memory pressure is a live alternative explanation
there — it may not generalise to the control plane.

**The cascade risk that applies to both arms:** a single perturbation (a timeout truncating a
scenario mid-way) leaves the server's KV state different from the other reps, which can change
everything after it. MTP rep 2 showed exactly this — two 240 s timeouts, then HA-06 at 158 s
against 21–24 s elsewhere, then recovery. If base ever trips that cascade it will look far
less stable than its per-request numerics suggest.

## How to read the outcome

| base result | conclusion |
|---|---|
| 0–1 unstable | the residual 4/20 **is** MTP; the `-cb` recipe genuinely fails to transfer |
| ~4 unstable | instability is **harness + server state, not MTP** — and the original 35 % needs re-attribution too |
| 2–3 unstable | partial contribution; quantifiable, and both prior legs need caveating |

**Calibration note:** I have been wrong on 6 of the last 10 predictions, in both directions.
These numbers are deliberately not clustered near certainty.

## Scoring

Score honestly on completion; append to `HA20_MTP_NOCB.md` and correct
`MTP_HA20_AND_MARGIN.md`.
