# SYS-02 — Qwen3.8-27B-Q6_K reproduces Claude's exact wrong answer, 3/3

**2026-08-30.** `.73` via the wake proxy (`Qwen3.8-27B-Q6_K`, `-ctk vbr -ctv vbr`, tensor split,
`reasoning_effort: medium`), temperature 0, K=3. Evidence served from captured state by
`replay_shell.py`, so all three reps saw byte-identical output.

## Result

| rep | answered | commands | critical golds | process |
|---|---|---|---|---|
| 1 | yes, 11 turns | 10 | **0/3** | **0/5** |
| 2 | yes, 11 turns | 10 | **0/3** | **0/5** |
| 3 | yes, 11 turns | 10 | **0/3** | **0/5** |

**All three reps issued command-for-command identical sequences** and produced the same root
cause, near-verbatim.

## What it concluded

> The nct6687d DKMS driver source calls strncpy() at nct6687.c:444 but never includes the header
> that declares it. [...] insert `#include <linux/string.h>` into the include block

This is **exactly the wrong answer Claude gave first**, for exactly the same reason: it followed
the compiler's `note:` line. The fix does not work — `strncpy` was **removed** from the kernel in
7.2 and survives only in comments describing its replacements. Adding the include moves the error
from line 444 to 445.

Trap **T1 hit, 3/3**. The item predicted this failure mode before the run.

## The process score is the finding

Ten commands per rep, **every one of them pointed at the module source**:

```
dkms status
dkms build nct6687d/1 2>&1 | tail -50
head -30 /usr/src/nct6687d-1/nct6687.c
grep -n 'string.h' /usr/src/nct6687d-1/nct6687.c ...
grep -n '#include' /usr/src/nct6687d-1/nct6687.c        (x3, near-identical)
sed -n '20,35p' /usr/src/nct6687d-1/nct6687.c
awk 'NR>=33 && NR<=48' /usr/src/nct6687d-1/nct6687.c
```

**Not one command opened a kernel header.** The question that decides the item — *does this symbol
still exist in this kernel?* — was never asked. C1 fails, and with it everything downstream.

Also visible: turns 5–8 are four near-duplicate `grep '#include'` invocations. The model had the
include list by turn 5 and kept re-fetching it, which reads as looping rather than investigating.

## What this does and does not establish

**Does:** on this item, at temp 0, K=3, Qwen3.8-27B-Q6_K deterministically follows an
authoritative-but-wrong compiler hint and never verifies the premise. It ends with a confident,
specific, wrong remediation — the most dangerous shape for a sysadmin agent, because the answer
looks well-evidenced.

**Does not:** generalise to sysadmin work at large. One item, one model, one quant. It also does
not show Qwen is worse than Claude *here* — **Claude produced the same wrong answer** on the live
system and caught it only because the rebuild failed. The difference is C4 (confirm by rebuilding),
which the replay harness cannot currently reward, since a rebuild returns the captured failing log.

## Harness limitation, stated plainly

`replay_shell.py` cannot model state changes. An agent that patches the file and rebuilds gets the
same pre-patch error back, so **C4 is unreachable by design** in replay. Two options, neither taken
yet: serve a second, post-patch build log when a rebuild follows an edit; or run this item live on
a machine with the fault reintroduced. Until then C4 should be reported as `n/a` rather than
`false` — the current grader marks it false, which understates the model slightly.

## Determinism note

Contradicts nothing in `agent-benchmark-determinism` (HA-04 bistable 35/100/100/35) but is a
different regime: 3/3 identical here. Short deterministic trajectories on a fully-replayed
transcript are far more reproducible than long agentic runs against a live server. **K=3 is still
the floor** — a single rep could not have shown this.
