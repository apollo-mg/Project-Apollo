# VOID — measured the harness, not the models

These runs are kept as evidence of instrument defects, not as results about any model.

| run | what actually happened |
|---|---|
| `sys02_27b_rep1` | 11 identical `sed -n '444p' ... \| wc -c` turns. The harness returned the whole 1700-line file for every command, so the model asked a precise question and got the same irrelevant blob each time. At temperature 0 there is no escape. **Not degenerate looping** — induced by the instrument. |
| `sys02_flashnext_rep1` | died at `max_tokens=2048` (reasoning model, no content emitted) then HTTP 400 on context overflow at `-c 8192`. |
| `sys02_flashnext_rep1b` | reached the correct recovery path (edit -> rebuild -> saw 444->445 -> checked kernel headers) **while every source inspection returned an unfiltered file**. Never finished: turn 19 was still prefilling ~17k tokens at 34 tok/s. |

Superseded by `replay_exec.py`, which executes read-only text commands against the captured
files instead of serving whole files.

## v3 (executing harness, pre-string.h fix) — also void

`replay_exec.py` executed commands correctly against the module source, but
`/usr/lib/modules/.../include/linux/string.h` still pointed at **pre-filtered grep output**, so
`cat`/`grep -c` on the kernel header returned 5 result lines pretending to be a 588-line file.
Two of Flash-Next's 8 turns were also `refused` because `ls` was not whitelisted.

Flash-Next answered wrong (missing-include, never rebuilt). The 27B was mid-run when the harness
changed. Both superseded by v4, which serves the real 588-line header and supports `ls`.

## v4 — void: two parser defects, found only in transcripts

- **`ls` returned a stock listing for any dkms-ish path.** Flash-Next descended
  `.../nct6687d/nct6687d/nct6687d/` into a directory tree that did not exist, losing **11 of 25
  turns**. Now returns ENOENT for uncaptured paths.
- **Pipelines were split on `|` without respecting quotes**, so `grep -n 'a\|b'` was refused as
  unsafe. The 27B lost **8 of 25 turns (32%)** and kept simplifying its patterns to route around
  the bug. Now split on unquoted `|` only.

Both invisible in the scores — both runs simply read as "hit the turn limit without answering".
The calibration gate PASSED on this broken harness because the reference trace used neither
alternation nor a bad `ls`. Those cases are now harvested into the gate.
