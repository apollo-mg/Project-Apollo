# The control: HA-20 is nondeterministic at temp 0 WITHOUT MTP. The 35 % was never MTP's.

RX 9070 XT, `llama_cpp_turboquant @ c26cbdffc`, `Qwen3.6-35B-A3B-UD-IQ2_M`, stevibe's HA-20
runner unmodified, `-cb` off. Date 2026-07-30. Predictions in `PREDICTIONS_ha20_base_k3.md`.

Base, **K=3**, all three reps against one long-lived server — mirroring the MTP arm exactly.

## Headline

| arm | verdict-unstable scenarios | PASS per rep |
|---|---|---|
| **base (no MTP at all)** | **5 / 20 (25 %)** | 12 / 14 / 12 |
| MTP, `-cb` off | 4 / 20 (20 %) | 12 / 12 / 13 |
| MTP, `-cb` on (original) | 7 / 20 (35 %) | — |

**Base is *more* unstable than MTP.** Speculative decoding is not the source of HA-20's
rep-to-rep variation. The harness plus long-lived server state is.

## Results

```
scen    base_r1       base_r2       base_r3       flag
HA-04   FAIL/35       PASS/100      NOVERDICT     VERDICT-UNSTABLE
HA-05   PASS/100      PASS/100      NOVERDICT     VERDICT-UNSTABLE
HA-12   FAIL/20       PASS/100      PASS/100      VERDICT-UNSTABLE
HA-16   NOVERDICT     FAIL/30       FAIL/30       VERDICT-UNSTABLE
HA-17   NOVERDICT     FAIL/20       FAIL/20       VERDICT-UNSTABLE
(15 others identical across all three reps)
```

**The same scenarios break in both arms.** Base unstable: HA-04, 05, 12, 16, 17. MTP unstable:
HA-04, 05, 12, 19 (plus HA-16 varying by score). **HA-04, HA-05 and HA-12 are unstable in both**,
and HA-16 is shaky in both. That shared fingerprint is what you expect from harness/state
nondeterminism, and not what you would expect if speculative decoding were driving it.

Base also produced **four no-verdict runaways** (HA-04 r3, HA-05 r3, HA-16 r1, HA-17 r1) — two
more than the MTP arm's two. Runaways are not an MTP phenomenon either.

## Prediction scoring — the 0.25 branch won again

| id | claim | conf | outcome |
|---|---|---|---|
| P-BC1 | base ≤1 unstable | 0.60 | **FALSIFIED** — 5 |
| P-BC2 | base 0 unstable | 0.40 | **FALSIFIED** |
| P-BC3 | base ≥3 unstable → harness, not MTP | **0.25** | **CONFIRMED** |
| P-BC4 | zero no-verdict runaways | 0.70 | **FALSIFIED** — 4 |
| P-BC5 | HA-04 among unstable | 0.40 | **CONFIRMED** |

Third run in a row where the low-confidence branch was the right one. The consistent error is
**over-trusting single-prompt determinism as a predictor of agent-loop reproducibility.** They are
different regimes and I keep reasoning from the first to the second.

This also confirms, on different hardware, the prior note that HA-04 is bistable at temperature 0
on `.73` (35/100/100/35). That was not a `.73` memory-pressure artifact. It generalises.

## Retractions

**1. `MTP_HA20_AND_MARGIN.md`'s central claim is withdrawn.** It reported "35 % scenario
instability" under MTP against a base K=1 reference and treated it as an MTP effect. With a
proper base K=3 control, base runs at 25 % under the same conditions. **35 % vs 25 % at n=20 is
well inside noise.** The correct statement is: *HA-20 does not reproduce at temperature 0 on this
stack, with or without MTP.* Everything downstream of that attribution — the "downward tilt,"
the runaway-generation framing — goes with it.

**2. `HA20_THREE_WAY.md`'s score comparison cannot support its ranking.** That receipt is
**K=1 everywhere** (it says so, and flags a 15 % flip floor). The measured base flip rate here is
**25 %**, i.e. roughly ±2–3 scenarios of noise on a 20-scenario board. Gemma **14**, Bonsai
**15**, Ornith **14** are therefore **statistically indistinguishable**. The receipt's other
content — architecture, measured KV cost/token, decode rates, the trajectory-length analysis —
is unaffected; those are direct measurements, not K=1 verdict counts.

**This matters for the Battle-for-16GB article.** "Bonsai edges out Gemma on agent tasks" is not
a supportable claim from this data. What *is* supportable: all three land in the same band, and
10 of 20 scenarios never fail for anyone.

**3. "base 14/20" was one draw, not a score.** Base K=3 here gives 12/14/12. The 14 quoted
throughout the campaign sits at the top of its own distribution.

## Open inconsistency to resolve

`mtp_structured.sh` **does** set `cache_prompt:false` (line 56 onward, with a comment explaining
why), so `MTP_STRUCTURED_OUTPUT.md` is not confounded by prompt caching. But it reported
within-arm variation — "prose 3 variants / 6 draws" — which sits badly against our cell-2 result
(`cache_prompt:false`, `-cb` on → **1 distinct / 6**). Both cannot be right about the same
regime. Candidate explanations: much longer generations (up to 4000 tokens vs 1200), different
prompts, or draws spanning instances in a way the paired design controls and that script does
not. **Flagged, not resolved.** Do not cite that receipt's determinism numbers until it is
re-checked.

## What survives, and it is not nothing

- **MTP is deterministic at temperature 0** for single-prompt generation with either `-cb` off or
  `cache_prompt:false` (`MTP_CACHEPROMPT_FALSIFICATION.md`) — 6/6 byte-identical, two independent
  levers converging on the same output. That is a clean, useful, deployable result.
- **MTP is not implicated in agent-loop instability.** This control is what licenses that
  statement, and it is a *better* outcome for MTP than anything we had before.
- The flip margin (0.03125, 99.25th percentile) is a property of the model's logit distribution
  and stands.
- Upstream's mechanism (`different kernels for different batch sizes`) is unaffected.

## The real open question, restated

HA-20 does not reproduce at temp 0 on a long-lived server, in either arm. Whether that is the
runner, the scenario fixtures, tool-execution timing, or accumulated slot/cache state is
**unknown and untested**. The cheapest discriminating next step is a **server restart between
reps** — if instability collapses, it is server state; if it persists, it is the harness.

## Provenance

- `~/projects/HermesAgent-20/run_ha20_base_k3.sh` (derived from `run_ha20_mtp_nocb.sh`; arm block
  replaced with base K=3, `OUT`/`PORT` changed — server flags byte-identical)
- `~/projects/HermesAgent-20/ha20_base_k3_nocb/` — 60 scenario logs, `arm.log`, `server_base.log`
- MTP comparison arm: `HA20_MTP_NOCB.md`, `~/projects/HermesAgent-20/ha20_mtp_ab_nocb/`
- Smoke test passed (`tool_calls True`)
