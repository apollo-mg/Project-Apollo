# What this corpus can and cannot claim

Written **2026-09-02**, before running the honest (stateful) version, because the result is easy
to state wrongly once it exists.

## The only claim the instrument supports

> **Given the same sequence of evidence that was available to Claude, does model X reach the same
> diagnosis, and where does its path diverge?**

That is a **path-comparison against one reference trace**, not a measure of diagnostic ability.

## Four reasons it is not "can model X do sysadmin work"

**1. The evidence set is bounded by what Claude thought to run.** Every file in `state/` exists
because Claude executed that command on the live machine. A model that wants evidence Claude never
collected gets `not captured`. It is confined to one explorer's path and cannot out-investigate it.
On SYS-01 this was not hypothetical: 10 of 25 commands fell off the edge of the capture and the
run was voided.

**2. The scoring rubric was written by the same author as the trace.** The golds are decidable
from machine state, which protects against grading on *style* — but the choice of *which* golds
matter is Claude's. A model that diagnosed the same fault by a route Claude did not consider can
score badly while being right.

**3. Asymmetric failure.** The model can lose points for evidence it wanted and could not get. It
can never gain points for evidence Claude failed to gather. The instrument is biased toward the
reference trace by construction.

**4. Claude is not a ceiling, and did not pass cleanly.** On SYS-02 Claude **fell into trap T1**
and applied the compiler's wrong suggestion. Recovery came from a *second observation* — the error
moving 444 -> 445 — not from superior reasoning. Any framing that reads "the model failed where
Claude succeeded" is false: Claude failed too and was corrected by the environment.

## What a divergence actually means

| observed | supported reading | NOT supported |
|---|---|---|
| model takes Claude's wrong turn, then self-corrects on the 445 signal | it uses disconfirming evidence when given it | "it is a good sysadmin" |
| model takes the wrong turn and never recovers | it did not use the disconfirming evidence that was present | "it is worse than Claude" — Claude needed the same signal |
| model never takes the wrong turn | it checked the premise unprompted, which Claude did not | "it is better than Claude" — one item, one trace |
| model asks for uncaptured evidence | **our capture is incomplete** | anything about the model |

## Why the stateful harness mattered

The first harness served a fixed snapshot, so `dkms build` returned the line-444 error forever.
The signal that rescued Claude **could not occur**. The item measured only "did you check the
kernel headers unprompted" and was structurally blind to self-correction.

`replay_stateful.py` now models edits: an agent that applies the compiler's suggestion and rebuilds
sees line **445**, from a real captured build of that exact intermediate source. Three states, three
genuine `make.log`s, nothing synthesised.

**Only with that in place is the path comparison honest**, because only then does the model have
access to the same disconfirming evidence Claude had.

## Reporting rule

Any result from this corpus is reported as **"diverged from / matched the reference trace at step
N"**, with the reference trace shown alongside. Never as a score in isolation, and never as a
capability claim about the model.
