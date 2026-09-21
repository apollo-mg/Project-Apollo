# Result -- advisor consultation collapses 15x as the context window fills, and it is not task length

**2026-09-21.** Mark observed from the outside: *"your model uses the Advisor less and less as
context window fills. Right after compacting, you use it frequently."* Measured against the
session transcript rather than agreed with.

**Source:** `~/.claude/projects/-mnt-TG-2TB-Projects-Apollo/9457b3f4-...jsonl`, 400 MB,
2026-07-25 to 2026-09-21. **Model held fixed at `claude-opus-5`** (the file also contains
`claude-opus-4-8` and `claude-fable-5` turns, excluded). 2,508 tasks, 16,227 tool-calling turns,
116 advisor calls.

**Unit of analysis is the TASK** -- one user prompt to the next -- not the turn. Per-turn rates
invert the picture, because low-context tasks are long (median 20 tool turns) and high-context
tasks are short (median 3), so a per-turn denominator hides the effect it is meant to show.
**Context is measured at task START** (`input_tokens + cache_read + cache_creation` on the first
assistant message of the task).

## The effect

| context at task start | tasks | contained an advisor call | median tool turns |
|---|---:|---:|---:|
| 0-100k | 77 | **59.7 %** | 20 |
| 100k-200k | 199 | 10.6 % | 7 |
| 200k-300k | 348 | 2.9 % | 5 |
| 300k-500k | 833 | **0.2 %** | 4 |
| 500k-800k | 777 | 0.1 % | 3 |
| 800k-1200k | 274 | 0.4 % | 3 |

Monotone from 0-100k to 500k-800k, and the top bucket is at the noise floor.

## It is not task length -- the control

Task length is the obvious confound: short reactive tasks legitimately need no advisor, and the
tool's own guidance says so. Holding length fixed and varying only context:

| task length | ctx < 250k | ctx >= 250k | ratio | Fisher |
|---|---:|---:|---:|---:|
| 1-2 turns | 1/84 = 1.2 % | 0/771 = 0.0 % | -- | -- |
| 3-5 turns | 0/91 = 0.0 % | 1/665 = 0.2 % | -- | -- |
| 6-10 turns | 9/93 = 9.7 % | 2/406 = 0.5 % | 19x | p = 7.7e-06 |
| **11+ turns** | **62/163 = 38.0 %** | **6/235 = 2.6 %** | **14.9x** | **p = 2.7e-21** |

**Among long tasks -- precisely where the guidance says to consult at least once before
committing to an approach and once before declaring done -- the rate falls from 38 % to 2.6 %
purely as a function of context.** Short tasks show no effect in either direction because they
are at the floor already.

## It is not the date, either

The decline holds **within 35 of 37 individual days** (the other two are zero on both sides).
Same day, same project, same kind of work, split at 250k:

```
2026-09-11    4/7  = 57.1%   (<250k)     2/46 = 4.3%   (>=250k)
2026-09-14    1/10 = 10.0%               0/154 = 0.0%
2026-09-20    1/7  = 14.3%               0/48  = 0.0%
2026-09-21    3/5  = 60.0%               0/32  = 0.0%
```

A within-day split rules out the explanation that early-context tasks come from different days
doing different work.

## Why this matters here

The advisor caught **three** substantive errors in this session alone: that psi is the
alternative hypothesis rather than something to estimate from the pilot; that the grounding floor
must be verdict-dependent (the union version failed *correct* agents); and that two probe prompts
tested a capability the matched-pair design never uses. All three arrived at 215k-436k context --
inside the range where the measured rate is ~0-3 % per task.

So the consultations that did happen at high context were high-value, and the aggregate says they
are ~15x rarer than the same work gets at low context. **This is a drift in a behaviour that the
day's record shows is load-bearing.**

## What this does NOT establish

- **Mechanism is unknown.** Rate, not cause. Whether this is attention dilution, the tool
  definition sitting far from the working set, or something about how the instruction is weighted
  against accumulated context is not addressed.
- **Not necessarily a defect in full.** Some decline is correct: later tasks in a window skew
  toward execution and monitoring. The length-matched control bounds how much of it that can
  explain, but does not reduce it to zero -- an 11-turn task at 600k may still be qualitatively
  more execution-heavy than an 11-turn task at 80k, and this cannot rule that out.
- **One user, one project, one transcript.** The work here is unusually tool-heavy and
  Bash-dominated; the mix is not representative of general use.
- **Compaction is a boundary, not a reset of the measurement.** Context at task start is used
  directly, so a post-compaction task simply appears in a low bucket. No claim is made about
  compaction itself.
- **No intervention tested.** Whether prompting for it, or a periodic reminder, restores the rate
  is unmeasured.
