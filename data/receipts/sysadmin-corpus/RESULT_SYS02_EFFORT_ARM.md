# SYS-02, `reasoning_effort` arm — xhigh asks the right question and still fails to answer

**2026-08-30.** `Qwen3.8-27B-Q6_K` on `.73`, temp 0. Predictions registered in
`PREDICTIONS_effort_arm.md` before the run. **This arm is contaminated — see below.**

## Why the arm exists

The medium result was not like-for-like with Claude. Per AFM-23, Qwen3.8's `reasoning_effort` is
consumed by the chat template and **injects literal system text**: `medium` injects **nothing**;
`xhigh` injects *"validate key assumptions, consider plausible alternatives"* — nearly a direct
instruction to do the thing SYS-02 measures.

## Result

| arm | K | answered | commands | distinct | repeats | kernel header opened |
|---|---|---|---|---|---|---|
| `medium` | 3 | **yes** (11 turns) | 10 | 8 | 2 | **never, 0/3** |
| `xhigh` | 1 | **NO — hit 25-turn limit** | 19 | 15 | 4 | **yes (see contamination)** |

## Prediction scoring

| # | predicted | conf | actual |
|---|---|---|---|
| P1 | opens a kernel header (C1) | 0.45 | **yes** — but see contamination | 
| P2 | reaches G1 (strncpy removed) | 0.30 | **no** — never concluded |
| P3 | names `strscpy` | 0.25 | **no** |
| P4 | still ends on the `#include` fix | 0.60 | **n/a** — no answer at all |
| P5 | materially longer | 0.85 | **yes** — 19 vs 10 commands, hit the limit |

**The outcome I did not predict: xhigh is *worse*.** Medium answered — wrongly, but decisively.
xhigh burned 25 turns and produced nothing. My prediction set had no entry for "fails to answer",
which is a gap in how I framed the arm, not a surprise about the model.

## The interesting part: it asked exactly the right question

At turn 13 the xhigh arm ran, unprompted:

```
grep -rn 'strncpy' /lib/modules/$(uname -r)/build/include/linux/string.h
```

That **is** C1 — the decisive check neither of the medium reps ever attempted, and the one whose
answer settles the item. It received the five comment-only matches. **It then failed to act on
them**, spending its remaining turns re-reading line 444 of the module source six times
(`sed -n '444p'` x4 plus variants) before running out.

So the injected *"validate key assumptions"* text did change behaviour — it produced the right
verification step — but the model could not convert the evidence into a conclusion. Getting the
decisive fact and not using it is a different, arguably more interesting failure than never
looking.

## CONTAMINATION — disclosed, and it cuts against my own result

One turn *earlier*, the model asked about the **module source**:

```
grep -n 'strncpy' /var/lib/dkms/nct6687d/1/nct6687.c
```

and `replay_shell.py` **mis-routed it to the kernel header file**, because the route pattern
matched any command containing both `strncpy` and `string.h` without requiring a kernel path. The
model was handed the decisive evidence one turn before it asked for it.

Audited across all four runs: **1 mis-route, in this arm only. The three medium reps are clean**
(0 mis-routes each), so the medium result stands as reported.

Router fixed to require a kernel path, with a regression test in both directions: a module-source
query now returns the module source, and a genuine kernel query still returns the header.

**Consequence:** P1 cannot be scored honestly from this run. The model did issue its own correct
kernel query at turn 13 — but it had already seen the answer at turn 12, so "did xhigh
independently think to check the kernel" is **unanswered**. The arm must be re-run on the fixed
harness before any claim is made.

A harness that answers a question the agent did not ask is the same defect class this corpus
exists to measure. Recording it as such.

## Standing conclusions

1. **The medium result is unaffected** and stands: 0/3 critical, 0/5 process, 3/3 identical.
2. **`reasoning_effort` must be a reported arm on every result**, exactly like clock state
   (AFM-23). It is now an explicit `--effort` flag rather than a buried default.
3. **The comparison against Claude was never like-for-like** and still is not: Claude ran at xhigh
   with a different tool surface, on a live machine, and got the same wrong answer as Qwen-medium.
4. **Re-run required**: xhigh at K=3 on the fixed harness, before anything is claimed about effort.
