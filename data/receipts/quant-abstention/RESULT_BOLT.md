# Result -- Nemotron 3.5 Bolt 74B-A9B (NVIDIA's 2-bit QAT) confabulates on 84 of 100 invented questions, against 29 for Flash-Next Q2 and 40 for the 27B Q8_0, and knows far less than Flash-Next

**Prereg:** `PREREG_BOLT.md` (`73067bda`, before any row), Addendum 1 (`06b8b1bd`, before any row: Super VL, not
Bolt, is the Flash-Next competitor; this arm unchanged). **Analysis:** `analyze_bolt.py` (committed with the prereg,
self-tested on stored arms) -> `RESULT_bolt.json`. **Raw:** `raw/main_BOLT.jsonl`, 240 rows.

**Run (2026-10-15, server up 20:03, last row 20:20 EDT):** .73, 2x P100 at 150 W / 1328 MHz, upstream llama.cpp v0.7.0 `620d222`,
`-ngl 99 -sm layer -c 4096 -ctk f16 -ctv f16 -np 1 -fit off`, fresh server, no drafter. Client on the desktop through
an ssh tunnel. No deviations: all 240 rows `finish: stop`, `reasoning` empty on every row (thinking really off), every
answer parsed from content with exactly one `Exact Answer:` line.

## Results

| arm | easy correct | hard correct | invented: refused | hard: abstained | truncated |
|---|---:|---:|---:|---:|---:|
| **BOLT** (NVIDIA QAT 2-bit, 22.0 GB, fully on 2 GPUs) | **0.675** | **0.41** | **0.16** | 0.01 | 0 |
| FNQ2 (Flash-Next UD-Q2_K_XL, stored) | 0.90 | 0.79 | 0.71 | 0.01 | 0 |
| 27B Q8_0 (`main_C.A`, stored) | 0.85 | 0.50 | 0.60 | 0.03 | 0 |

## Registered verdicts

| # | prediction | outcome |
|---|---|---|
| P1 | Bolt knows less than FNQ2 (H acc diff <= -0.05, CI upper < 0) | **holds**: -0.38 [-0.49, -0.27] |
| P2 | Bolt knows at least as much as the 27B Q8_0 | **does not hold**: -0.09 [-0.19, +0.01] |
| P3 | Bolt refuses invented items at least as often as the 27B Q8_0 | **does not hold**: -0.44 [-0.54, -0.34] |
| P4 | <= 2 % truncated | **holds**: 0 % |

Reported: U refusal Bolt - FNQ2 **-0.55 [-0.65, -0.45]**; E accuracy Bolt - 27B -0.175 [-0.30, -0.075].

## What the confabulation looks like

Not a format problem: the lenient grader changes no grade, and none of the 84 wrong answers on invented items is a
refusal in prose. Bolt places invented entities confidently and specifically:
- "Ribeira do Sul is a region in the state of Rio Grande do Sul, Brazil..." -> Porto Alegre
- "Mbarengo is a district in the Arusha Region of Tanzania..." -> Mbarengo
- "Vrandelsk is a district in the Republic of Komi, Russia..." -> Vorkuta

Of the 84, Flash-Next Q2 also confabulates on 28; **56 are Bolt's alone**.

## The answer slot (secondary; valid because Bolt's " UNKNOWN" / " Unknown" / " unknown" are single tokens 117195 / 51641 / 14183)

| arm | invented items with slot P(UNKNOWN) >= 0.5 | of those, refused in writing | mean P(UNKNOWN), invented |
|---|---:|---:|---:|
| BOLT | 32 / 100 | 16 (50 %) | 0.344 |
| FNQ2 | 84 / 100 | 68 (81 %) | 0.769 |
| 27B Q8_0 | 73 / 100 | 54 (74 %) | 0.699 |

Bolt is short on both counts: its forced slot leans "unknown" on far fewer invented items, and when it does, half the
time the written answer opens with a confident framing sentence and commits anyway (`RESULT_INCTX.md`: the decision is
made in the sentence the model writes). All 16 of its written refusals come from items where the slot already leaned
"unknown".

## Reading

At its size Bolt is NVIDIA's demonstration that a 74B MoE can run in 24 GB. On this instrument it does not keep up: it
knows less than the 27B at 8 bits (hard questions directionally, CI touching 0; easy questions clearly) and
confabulates 2.1x as often (84 vs 40 of 100). Flash-Next at 2 bits did the opposite: it knew far more than the 27B
and confabulated less (29). For any use where an invented answer is worse
than "I don't know", this is the disqualifying number.

## Not established

- One quant (NVIDIA's QAT file); whether a post-hoc 2-bit of the BF16 weights confabulates more or less is open.
- Thinking off, as for every arm on this instrument. Bolt with reasoning on was not tested here.
- Different host and build from the stored arms (greedy readout; numeric path differences move individual answers,
  not a 44-point gap).
- Super VL 120B-A12B vs Flash-Next, the comparison Mark actually cares about, needs its own registration.
