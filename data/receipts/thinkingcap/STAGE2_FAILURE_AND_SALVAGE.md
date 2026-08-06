# Stage 2 (ThinkingCap vs stock Qwen3.6-27B) — harness failure, and what survives

**Date:** 2026-07-27. Node `.194` (quad P100, sm_60). Recorded because the failure produced
a *number*, not a crash — the exact trap this project has named repeatedly.

## What the run reported

```
Qwen3.6-27B-Q8_0-STOCK-MTP   PASS=0   NO_ANSWER=164   pass@1 = 0.0%    elapsed 1677s
ThinkingCap-Qwen3.6-27B-...  PASS=157 WRONG=6         pass@1 = 95.7%   elapsed 28641s
```

Read naively that is a 95.7-point win for ThinkingCap. **It is not a result at all.**

## Root cause: PHASE 0 was both the equivalence check and the server launcher

All 164 stock traces contain `__ERR__ <urlopen error [Errno 111] Connection refused>`, and
`tcab_results_stock.json` has 164 entries with `bucket: None`. The stock server was never
listening. The 1677 s elapsed is 164 × ~10 s of connection failures.

The sequence in `~/hep/out/stage2.log`:

| when | what happened |
|---|---|
| 2026-07-26 07:02 | PHASE 0 ran, **started the server** (`started pid 2816592`), verified 5/5 greedy byte-identical, and concluded *"old non-MTP file is safely deletable"* |
| 07-26 07:11 | stock arm began — reusing the server PHASE 0 had left running (`"server already holding stock MTP; continuing"`). Interrupted after 71 samples |
| 07-26 18:45 | re-launch: **`ABORT: model not found: .../27B/Qwen3.6-27B-Q8_0.gguf`** — the non-MTP file had been deleted on PHASE 0's own advice |
| 07-27 11:01 | re-launch with PHASE 0 skipped. Went straight to `=== ARM: ...STOCK-MTP ===` with **no `started pid` line**. No server. 164 connection refusals |

**PHASE 0 was load-bearing for a reason unrelated to its purpose.** It was the equivalence
check *and* the thing that started the stock server; the stock arm had no launcher of its
own and inherited PHASE 0's process. Deleting the file PHASE 0 recommended deleting made
PHASE 0 abort, skipping it removed the server start, and the arm ran against a dead port
and reported a score. The ThinkingCap arm has its own explicit `started pid 2131783` line,
which is why it ran fine.

Both model files are present and intact (28 G each); disk on `.194` is at 95 % but was not
the cause.

## What survives: a matched 71-problem comparison

The interrupted 07-26 stock arm produced **71 real samples** before it died, and its
per-sample lines are still in `tcab_stock.log` — appended *above* the failed run's
all-NORESULT lines, which is why the file's head looks like a successful run. Comparing
ThinkingCap on exactly those problems (matched problems, not matched counts):

| arm | matched subset (HumanEval/0 … /70) |
|---|---|
| stock MTP | **69 / 71 = 97.2 %** |
| ThinkingCap | **70 / 71 = 98.6 %** |
| disagreements | **1** — `HumanEval/24` (stock 0.00, tc 1.00) |

**One problem.** McNemar on a single discordant pair is p = 1.0. At **K=1 and temperature
1.0** — the sampling these arms used — a one-problem difference is indistinguishable from a
single unlucky draw, which is precisely the lesson `HumanEval/47` taught on this same
benchmark.

**Caveat, stated so the number is not over-read:** HumanEval/0–70 is a contiguous prefix,
not a random subset, and it is *easier* than average — ThinkingCap scores 98.6 % on it
versus 95.7 % across all 164. So the stock 97.2 % cannot be extrapolated to the full set.
The matched comparison is valid only as what it is: on 71 identical problems, the two arms
differ by one.

## Status

**Stage 2 produced no usable evidence in either direction.** The 95.7 % ThinkingCap figure
is real and its 164 traces are sound, but it has **no control**. The salvaged 71-problem
overlap shows no detectable difference.

To close it: re-run the stock arm with an explicit server launcher rather than an inherited
one, K≥3 given the temp-1.0 sampling, and matched problem sets by construction. Do not
report 95.7 % against 0.0 % anywhere.
