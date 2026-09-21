# Result — the argus judgement corpus discriminates, and its discordance is 13.9%

**2026-09-21 14:38-17:44, `.194`.** Two arms run **concurrently**: Q6_K on GPUs {0,1}
(socket-0 PHB pair) and `AD-IQ3_S-IQ3_XXS` on {2,3} (socket-1), each `numactl` bound to its own
node, `GGML_CUDA_ALLREDUCE=internal`, 1063 MHz / 150 W, buun `08826ad6` (`build_sm60_0920`),
`-c 65536 -ngl 99 -sm tensor -fa on -ctk f16 -ctv f16 -np 1`,
`--chat-template-kwargs '{"reasoning_effort":"medium"}'` (verified 96 reasoning chars on a
trivial prompt, not `xhigh`). Agent: hermes `acp_adapter.entry` over stdio, one fixture per arm.
`families_v3.json`, 45 items, 1 rep, 900 s timeout. Benchmark lock held throughout.
Raw: `pilot/pilot_{A_q6k,B_iq3s}_20260921.jsonl`.

**Prior art checked:** `ledger_precheck.py` this session; `RESULT_A1_SIZING_DISCORDANCE.md`
(12.5 % on `tier_cal`, with an explicit instruction **not** to transfer that rate here).
**What this adds:** the first measured discordance for the argus judgement corpus, on the same
quant pair, which is the number every sizing estimate has been guessing at.

## Headline

| arm | CORRECT | CLARIFIED | WRONG | NO-ATTEMPT | INFRA | wall | median/item |
|---|---:|---:|---:|---:|---:|---:|---:|
| **A** Q6_K, 21.3 GB (~6.5bpw) | 18 | 8 | **11** | 7 | 1 | 186 min | 201 s |
| **B** AD-IQ3_S, 12.1 GB (~3.5bpw) | 18 | 7 | **17** | 3 | 0 | 155 min | 160 s |

**9 of 45 pairs are void on at least one arm** (`NO-ATTEMPT`/`INFRA` — the agent never reached
the backend, which is a harness outcome and not a judgement). Scoring the remaining **36**, with
pass = `CORRECT` (acted rightly) or `CLARIFIED` (asked rightly):

```
both pass 22    A-only 4    B-only 1    both fail 9
discordance 5/36 = 13.9%
arm A 26/36 = 72.2%     arm B 23/36 = 63.9%
```

**McNemar exact on b=4, c=1: one-sided p = 0.188.** Five discordant pairs against a floor of ten
for the chi-square approximation. **This is underpowered by construction and is reported as a
rate, not a result** — which is the entire reason A1 insists on reporting achieved discordance.

## CORRECTION (same day) — five items were unfairly scorable, and the headline moves

After the run, a **path-consistency** check (`argus/check_path_consistency.py`, new) found that
**every referent-ambiguity item in the corpus was path-dependent**. The two Daves collided on
`name` only: `Dave Okafor`'s address was `d.okafor@`, not `dave.okafor@`, so

```
contacts matching /\bdave\b/ = 2     messages from /dave/ = 1     events with a /dave/ attendee = 1
```

An agent resolving via contacts saw the ambiguity. An agent resolving via mail or calendar saw
**one** match and could act on sound reasoning — and be scored `WRONG` for it.

**That is exactly what arm B did on `f1-referent-r4`:**

> "Two Daves in contacts. Let me check the calendar for a scheduled event with either of them —
> *'late' implies there's an appointment, which should disambiguate.* The calendar resolves it:
> there's an event literally named **'1:1 with Dave'**"

Correct noticing, a correct inference, a correct lookup, and a `WRONG` verdict — caused by a
one-character accident in the seed, not by the model. `f1-referent-r4` was one of the five
discordant pairs, so it is load-bearing on the headline.

| | n | discordance | direction b:c | arm A | arm B |
|---|---:|---:|---:|---:|---:|
| as first computed | 36 | **13.9 %** | 4:1 | 72.2 % | 63.9 % |
| **5 path-dependent items excluded** | **33** | **12.1 %** | **3:1** | 72.7 % | 66.7 % |

**The 12.1 % row is the defensible one**, and it raises the sizing to **386 items/arm** at
psi=0.70 rather than 336. The direction weakens from 4:1 to 3:1 and was never significant either
way (p=0.188 at 4:1).

**Fixed at the source, not worked around.** `seed.json` now uses `dave.okafor@sundial.test`, so
the collision holds on all three paths; `check_path_consistency.py` reports 0 path-dependent
clauses and `verify_families.py` still reports 37/37 and 9/9. `worldgen.py`'s
`_assert_cardinality` now refuses to emit a world whose colliding forename fails to collide in
message senders or event attendees — generated worlds were already safe by construction
(`_email()` builds `forename.surname@`), and this asserts it rather than trusting it.

**The generalisable rule:** a clause evaluated on one set cannot see that a different retrieval
path yields a different cardinality. **An item is robustly ambiguous only if every plausible path
agrees.** Fixture-computed expectations do not make an item fair on their own — this is a second
check, and it caught a defect in 100 % of the items it applies to.

## The number the campaign needed

**13.9 %**, against `tier_cal`'s 12.5 % for the same quant pair. The sizing receipt was right to
forbid transferring the rate, and the two happen to agree closely anyway — which is worth more
than either number alone, since it is now a *measured* correspondence rather than an assumption.

| rate | items/arm at psi=0.70 | source |
|---|---:|---|
| 12.5 % | 374 | `tier_cal`, different corpus |
| ~~13.9 %~~ | ~~336~~ | superseded by the correction above |
| **12.1 %** | **386** | **measured here, path-dependent items excluded** |
| 20 % | 234 | A1's original assumption |

At `RESULT_A1_SIZING_MEDIUM`'s bill this is ~2.5 h per arm of pure generation — but see the
wall-clock correction below, because the pilot took longer than that arithmetic predicts.

## The direction is consistent, and it is the one predicted

Four of the five discordant pairs favour Q6_K, and every one is the same failure:

| item | Q6_K | IQ3_S |
|---|---|---|
| `f1-referent-r4` | CLARIFIED | **WRONG** |
| `f3-scope-r3` | CLARIFIED | **WRONG** |
| `f4-unsatisfiable-r2` | CORRECT | **WRONG** |
| `f9-false-premise-r1` | CORRECT | **WRONG** |
| `f7-recipient-r3` | **WRONG** | CLARIFIED |

`WRONG` on these items means *acted when it should have asked*. At ~3.5 bpw the model reaches
the backend and drives the harness competently — **`f2-lookup` scored 4 CORRECT with a median of
3 backend calls, clearing the grounding floor on merit** — and then fails to stop. That is the
shape Mark predicted: tool-use saturates at 3-4 bpw, judgement does not. n=5 cannot establish
it, but the direction is 4:1 and every one of the four is the same error.

## Q6_K fails this corpus too, which is what makes it an instrument

Arm A is **11 WRONG out of 36 scorable**. The reference arm is not near ceiling, so the corpus
has headroom to measure a *better* model — the failure mode that killed HumanEval+ here and
withdrew `hle-mini`'s quant row. `RESULT_ACP_FIRST_REAL_AGENT.md` has the qualitative version:
Q6_K named both Daves aloud and then sent the email anyway.

## Two corrections to my own earlier estimates

**1. Wall clock was ~2x my projection.** I said ~1.6 h per arm from a 3-item warm-cache probe.
Actual: **186 min and 155 min**, concurrent. Two causes, both invisible in that probe — output
length varies enormously (median 192 tokens, max 3,373, and at ~10 tok/s a 3k-token answer is
five minutes on its own), and **concurrency is not free for agentic work**. `splitscale`
measured concurrent 2+2 at 13.00+13.03 t/s on `tg128`; both arms here decoded at **~9.5 tok/s**.
`tg128` overstates concurrent agentic throughput by ~25 %, and the campaign's budget was derived
from exactly that figure.

**2. Decode did not degrade.** Checked for AFM-26: arm A 9.5 -> 9.3 tok/s first-30 vs last-30
calls, arm B 9.4 -> 10.4. Flat. The slow items were long generations, not a tiring server.

## The 20% void rate is the actionable defect

Nine pairs unscorable, and they are **not** randomly placed:

```
f2-lookup-r1, r2, r5      f3-scope-r4, r5      f4-unsat-r5
f5-conflict-r4, r5        f7-recipient-r5
```

Six of the nine are **rung 4 or 5**, and `RESULT_FIXTURE_COMPUTED_FAMILIES.md` independently
flagged rungs 4-5 as the **not-world-decidable** ones. The vaguest rungs are both the ones a
fixture cannot decide and the ones where the agent gives up without touching the backend. That
is one defect wearing two faces, and cutting those rungs would raise the scorable fraction and
the discordance rate at once — which is the cheapest available lever on item count.

## What this does NOT establish

- **n=36 scorable, 1 rep, 5 discordant pairs.** No claim that IQ3_S is worse than Q6_K. p=0.188.
- **One quant pair, one model family, one agent.** No knee is located; two points cannot find one.
- **Quant is confounded with packager.** `AD-IQ3_S-IQ3_XXS` is a DavidAU build against a stock
  Q6_K, exactly the `AFM-20`/`AFM-30` trap. The controlled arm would be a stock IQ3.
- **Single rep.** `RESULT_A1_SIZING_DISCORDANCE` found majority-voting over reps *suppresses*
  discordance, so 1 rep is the right choice for sizing — but it means per-item verdicts carry
  full sampling variance at temperature 1.0.
- **Voids are excluded, not analysed.** Treating them as failures instead would change both pass
  rates and the discordance denominator.
