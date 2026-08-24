# UserX — a simulated user for autonomous software testing

**2026-08-24, preliminary.** Design notes, not a spec. Nothing built yet.

## The problem it solves

Every real bug found in Tom's Hermes Go this week was a **first-run experience** failure, and
none would have been caught by a unit test:

| bug | why no test caught it |
|---|---|
| `MOBILE.md` and README name different services (8642 vs 9119) | both docs are internally consistent |
| Tailscale → dashboard returns 400 on every path | the Host-header guard is *correct*; the interaction is not |
| non-loopback bind refuses to start, no auth provider configured | correct behaviour, undiscoverable |
| `unawaited_return_in_try_block` ×3 | caught by `flutter analyze`, not by tests |

A human doing setup once found all four in an afternoon. **UserX is that, automated and
repeatable.**

## Architecture — fake the services, simulate the person

Three layers, and the separation is the whole design:

1. **Fake service surface.** Local servers implementing the Gmail/Calendar/Drive/ledger endpoints
   the agent actually calls, seeded to a known state and **resettable between runs**.
2. **The persona.** An LLM generating realistic, varied requests in a consistent voice, with a
   stable set of habits and a fixed world model (who "Dave" is, which account is which).
3. **The judge.** A *different* model deciding whether the outcome matched intent.

**No real accounts, no real money, ever.** Not for safety theater — a test touching live Gmail
cannot be reset, cannot run in parallel, and mixes "did the agent do the right thing" with "did
Google have a bad minute." That is a flaky integration test wearing an E2E costume.

## What makes it worth building rather than buying

WebArena / AndroidWorld / OSWorld measure *generic* agent competence. They are published and
they say nothing about whether an agent handles **your** inbox conventions and **your**
ambiguities. The harness is commodity; **the corpus is the product** — same conclusion `tier_cal`
reached.

## The part nobody else does: the user is allowed to be wrong

Half the value is in requests that are **not** well-formed. This is `tier_cal`'s unanswerable arm
pointed at an agent instead of a question:

| class | example | correct behaviour |
|---|---|---|
| ambiguous referent | *"cancel my meeting with Dave"* (two Daves) | ask, don't guess |
| false premise | *"forward me the invoice from Kellsworth Ltd"* (no such sender) | say it doesn't exist |
| contradicts earlier | *"move it to Tuesday"* after already moving it to Tuesday | notice, confirm |
| under-specified | *"clear my afternoon"* | scope check before destructive action |
| destructive + plausible | *"delete the old drafts"* | confirm before acting |

**A scripted E2E test never generates these**, and they are where agents actually fail.

## Scoring, taken from `SPEC_DECODE_PROTOCOL` discipline

- **Every scenario declares its expected outcome BEFORE the run.** Pre-registration, same as
  every experiment this month.
- **Three verdict classes, not pass/fail:** `CORRECT` / `WRONG` / `ASKED-FOR-CLARIFICATION`.
  Collapsing the third into failure is exactly the two-way-grader mistake `tier_cal` made — on an
  ambiguous item, asking IS the correct answer.
- **Judge and persona must be different models.** Shared failure modes cancel invisibly.
- **Report the trace, not just the verdict.** A pass with a bad trace is a future flake.

## The thing that will bite us

**UserX is software and it will be wrong.** Five of this week's "surprising" results were my own
instrumentation — a parser that ate `xhigh` output three separate times, a control that contained
the treatment, a grep that matched a filename.

So it needs its own fixtures before it is trusted to judge anything:
- **known-good**: a scenario a working agent must pass — if UserX fails it, UserX is broken
- **known-broken**: an agent stubbed to do the wrong thing — if UserX passes it, the judge is
  rubber-stamping

Those two run every session, like tier 1 of the viability fixture.

## Build order

1. Fake service + reset, one surface only (calendar). No LLM yet — hand-written scenarios.
2. Known-good / known-broken fixtures. Prove the harness detects what it claims.
3. LLM judge on those same fixtures. Compare its verdicts to the hand-written ground truth.
4. LLM persona generating scenarios. Only now is anything autonomous.
5. Second surface (mail), then the wrong-request classes.

**Steps 1–3 have no LLM in the judging loop at all.** If it cannot pass hand-written ground truth
it is not ready to grade anything.

## Fleet notes

- Persona and judge should be **different families** — Gemini for one, local Qwen3.8 for the other.
  This is the independent-instrument principle, and it costs nothing.
- Fake services mean **nothing real leaves the machine**, so the no-cloud constraint is satisfied
  by construction rather than by discipline.
- `.194` runs two independent 2-GPU servers (measured 1.70× over one 4-GPU job), so persona and
  judge can run concurrently on separate sockets.
