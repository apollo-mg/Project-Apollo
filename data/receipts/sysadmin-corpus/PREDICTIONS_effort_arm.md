# Pre-registered — does `reasoning_effort: xhigh` rescue SYS-02?

Registered **2026-08-30**, after the medium arm (0/3 critical, 3/3 reps) and **before** any xhigh
run completed.

## Why this arm exists

The medium arm was not a like-for-like comparison with Claude. Per AFM-23, Qwen3.8's
`reasoning_effort` is consumed by the chat template and **injects literal system text**:

- `medium` -> injects **nothing** (what the 3 medium reps ran with)
- `xhigh` -> injects *"...validate key assumptions, consider plausible alternatives..."*

SYS-02's entire failure was **not validating a key assumption** — that `strncpy` still exists.
So the xhigh string is nearly a direct instruction to do the thing the model failed to do. This
is a confound in the medium result and must be measured, not argued about.

## Predictions

| # | prediction | confidence |
|---|---|---|
| P1 | xhigh opens **at least one kernel header** (C1 passes) | **0.45** |
| P2 | xhigh reaches G1 (`strncpy` removed, not merely un-included) | **0.30** |
| P3 | xhigh names `strscpy` (G3) | **0.25** |
| P4 | xhigh still ends with the `#include <string.h>` fix | **0.60** |
| P5 | xhigh runs materially longer (more commands or more tokens/turn) | 0.85 |

## Reasoning

**P1 at 0.45, above P2/P3.** "Validate key assumptions" plausibly buys one extra verification step
— but the model has to decide *which* assumption to validate, and the compiler has already framed
the problem as a missing include. Checking that the header exists is a different move from
checking that the *symbol* exists.

**P4 at 0.60, higher than P2.** The trap is strong precisely because the misleading evidence is
authoritative. A generic "think harder" instruction does not tell you to distrust the compiler.

**These are not confident predictions.** Genuinely uncertain, which is the reason to run it.

## Falsifiers

- If xhigh scores identically to medium, the confound is real but **inert on this item**, and the
  medium result stands as reported.
- If xhigh passes C1 and reaches G1, then **the medium result measured a prompt setting, not the
  model**, and every SYS-02 number must be labelled with its effort arm.
- If xhigh does more work and still lands on the wrong fix, that is the strongest possible result
  for the item: the trap survives an explicit instruction to validate assumptions.

## What is NOT being claimed either way

K=1 on the xhigh arm to start. Per `agent-benchmark-determinism`, one run is an existence proof.
The medium arm was 3/3 identical, so a single divergent xhigh run would be informative — but a
single *matching* run needs K=3 before it means anything.
