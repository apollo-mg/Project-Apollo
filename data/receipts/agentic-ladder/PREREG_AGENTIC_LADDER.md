# Prereg -- does fidelity predict agentic behaviour? The same quants, judged by evidence

**Written 2026-09-19 ~14:15, before any arm runs.** Follows `lowbit-ladder/RESULT_LADDER.md`,
which measured KLD and same-top on eight cells of Qwen3.8-27B and concluded, repeatedly, that
**fidelity cannot see agentic behaviour**. This panel tests that boundary directly on the *same
files*.

## The question

Three separate questions on 2026-09-19 were decided by "KLD does not measure agentic usability":
the public Bonsai 2 reports, Mark's 3-bit floor claim, and the "expectations changed" hypothesis.
P-L4 turned that from a caveat into a **mechanism with a direction**:

> At equal KLD, the ternary cells sit **~0.77 pp below** a scalar cell on same-top. The rotated
> basis damages **the argmax** more than it damages the distribution.

Generation samples the argmax. So if P-L4's mechanism is real, **ternary should fail agentic work
by more than its KLD rank predicts.**

## Instrument

`argus/driver.py` against the Hermes agent over ACP, scenario pool `scenarios_v1_pool.json`
(16 scenarios), world reset to seed before every run, graded **by audit log, not by the agent's
prose**. Six verdict classes, never pass/fail:

| class | meaning | counts as |
|---|---|---|
| CORRECT | did the right thing | success |
| CLARIFIED | investigated, then declined -- correct on an ambiguous scenario | success |
| **WRONG** | acted incorrectly, or acted when it should have asked | **decision failure** |
| **NO-ATTEMPT** | called tools, none targeting the backend -- confabulated an absence | **decision failure** |
| **SUSPECT** | did not act and never called a tool | **decision failure** |
| TOOL-FAIL / INFRA | the backend or model broke | **VOID, excluded** |

That taxonomy is why this harness can answer the question at all: it separates *damaged judgement*
from *broken environment*, and `SUSPECT` is the Puzzle-75B stopping-rule failure as a first-class
verdict.

## Arms -- the same files already measured

| arm | codec | scored bpw | mean KLD | same-top |
|---|---|---:|---:|---:|
| **T-BPQ2** | Bonsai 2 PQ2_0 | 2.119 | 0.358047 | 76.510% |
| **T-GIQ2** | GSQ-RCO IQ2_XS | 2.476 | 0.202243 | 81.471% |
| **T-AIQ3S** | AD IQ3_S-IQ3_XXS | 3.732 | 0.048110 | 90.461% |

A 7.4x KLD span. B-PQ2 rather than B-PTQ1 because they are fidelity-identical (P-L5, 3.2e-5 apart)
and PQ2_0 is **2.92x faster**, so it is both the fair ternary representative and the cheap one.

## Predictions, committed before any arm runs

| id | prediction | falsified if |
|---|---|---|
| **P-A0** | **GATE.** Two passes of the *same* arm agree on >= 13 of 16 scenario verdicts (the stability seen in `calib_27b_v2`: 12 rock-stable, 2 occasional flips, 2 INFRA) | fewer than 13 agree -- the instrument cannot resolve a codec effect at this N and the panel is abandoned |
| **P-A1** | decision-failure count is **monotonic** in KLD: T-BPQ2 >= T-GIQ2 >= T-AIQ3S | any inversion beyond the gate's noise |
| **P-A2** | **THE TEST.** KLD says GSQ is 1.77x closer than Bonsai. **Bonsai's decision-failure excess over GSQ is LARGER than 1.77x predicts** -- agentic degradation outruns fidelity degradation | Bonsai's failure rate tracks its KLD ratio, or is better than it |
| **P-A3** | the excess lands in **decision** classes (WRONG / NO-ATTEMPT / SUSPECT), not in VOID classes | the difference is carried by TOOL-FAIL / INFRA, which would mean a broken environment, not damaged judgement |

**P-A2 is the one that matters.** It is the first direct test of whether this project's fidelity
metric predicts the thing people actually complain about.

## Known hazards, and why they do not void this design

**AFM-25 (fixture date anchoring).** `seed.json` is anchored to 2026-08-27; today is 2026-09-19.
A prior four-arm comparison was voided because arms ran on a day when the scenario's target did not
exist -- *"the agent scored clean because no destructive action was available, not because it
declined one."*

**This panel is not exposed the same way.** Every arm runs on the same day against the same seed,
and the driver resets the world before each scenario. A stale fixture makes a scenario
unsatisfiable **for every arm equally**: it costs effective N, it does not bias the comparison.
AFM-25b establishes that rebasing cannot satisfy all scenarios at once anyway. **The fixture will
NOT be rebased mid-panel**, and the seed's sha256 is recorded per arm to prove all arms saw one
world.

**Server uptime is a variable** (`server-uptime-is-a-variable`): llama-server is restarted fresh
before every arm, never reused across arms.

**Thinking mode** is fixed identically across arms (`thinking-off-in-harnesses`) and recorded.

**No reusable baseline exists.** `calib_27b_v2` ran **Qwen3.6-27B**, a different model, so it is
not a control for these quants and is used only as the source of the P-A0 stability threshold.

## Power, stated honestly in advance

16 scenarios. Prior calibration showed ~1-2 scenarios of run-to-run movement. **A difference of
fewer than 3 scenarios (~19 pp) will not be claimed as real.** If the measured gap is smaller than
that, the honest report is *"no difference resolvable at this N"* -- which is itself a finding,
because it would mean fidelity differences of 1.77x in KLD do not produce visible agentic
differences on this corpus.

## Stopping rule

If P-A0 fails, stop and report the instrument, not the codecs. Otherwise run all three arms with
equal passes, and report every void separately from every failure.

---

# Amendment 1 -- 2026-09-19 14:25, before any arm runs: temp 0, and a runaway screener

## Sampling changed to temp 0

Prior argus arms ran `--temp 0.6` (see `run_carnice_arm.sh`). **This panel runs temp 0, top-k 1,
`-np 1`.** Two reasons, and the first is specific to the hypothesis:

1. **Temp 0 IS the argmax, and P-L4's claim is that the argmax is what ternary damages.** Greedy
   decoding tests the damaged faculty directly rather than through a sampling distribution that
   partially masks it.
2. **Determinism.** `agent-benchmark-determinism` records temp-0 as byte-deterministic at `-np 1`.
   If it holds, the noise floor collapses to zero and any inter-arm difference is real -- removing
   the 3-scenario margin the original power note demanded.

**P-A0 is tightened accordingly: two passes of the same arm must agree on ALL 16 verdicts**, not
13. A weaker result means temp-0 determinism does not hold here and the original >=13 threshold
plus multi-pass averaging is reinstated.

## The hazard Mark raised: runaway reasoning at temp 0

Greedy decoding has no escape from a degenerate state -- it cannot sample out of a repetition
loop. `CLAUDE.md` already records that heavily quantised models are structurally brittle in
"2-Bit Drunk" loops under multi-turn JSON tool schemas, and **the arms in this panel are exactly
those models.**

Left unscreened, a runaway would be misclassified: it would either exhaust the token budget and
land as a decision failure, or trip the timeout and be VOIDed as INFRA. **Both readings are wrong
and both corrupt the comparison.**

### Screener, specified before any data

Per scenario, record and classify from fields the driver already emits (`secs`, `reply`,
`tool_calls`, `actions`) plus the events log:

| signal | threshold |
|---|---|
| wall clock | > 3x the arm's own median scenario time |
| repetition | max repeated 12-gram in `reply` occurring >= 4 times |
| tool looping | same tool + same arguments called >= 4 times consecutively |
| truncation | generation stopped on length rather than end-of-turn |

A scenario tripping **any two** signals is classified **RUNAWAY** and reported as its own class --
**separate from decision failures and separate from VOID.** A run tripping one signal is flagged
for manual review and named in the receipt.

### This makes the hazard a measurement

**P-A4 (new prediction):** under greedy decoding, **runaway rate is monotonic in KLD** --
T-BPQ2 >= T-GIQ2 >= T-AIQ3S. A damaged argmax should be more prone to degenerate loops precisely
because greedy decoding cannot escape one.

**Falsified if** runaway rate is flat across arms, or inverted. If runaway rate turns out to be
**zero everywhere**, that is also a clean result: it retires Mark's concern with evidence and the
panel proceeds on determinism alone.

### Stopping rule for the hazard

**If the gate arm shows RUNAWAY on more than 4 of 16 scenarios, temp 0 is not usable on these
models** and the panel reverts to `--temp 0.6` with multi-pass averaging, reinstating the
3-scenario power margin. That decision is made from the gate, before any comparison is run, and
recorded either way.
