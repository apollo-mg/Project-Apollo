# RESULT: thinking-on sizing run -- xhigh with replayed reasoning fits the 49k lane and never hit the 16k step cap, but costs about 4.5 times the thinking-off wall time; both models read every file one by one first, walk identical paths for 12-13 steps, and declare the missing-data item only after the step-20 reminder

**Plan:** `PLAN_SIZING.md` (committed before any thinking-on episode). **Run:** second launch, 2026-11-19 19:33 to
20:39, code `12259aac` (the first launch, 19:27, aborted before any episode: sshd reset connections seconds after
boot; `sizing/sizing_launch1_aborted.log`, driver fixed to wait for stable ssh and fail closed). **Records:**
`sizing/raw/{BASE,PIA}/` (4 episodes), `sizing/preflight.json`, `sizing/sizing.log`. **Sizing, not measurement:**
one item of each kind per arm.

## Preflight

On both servers (buun `0b2789f23`, Q8_0, with and without the adapter): the three outcomes render, the xhigh sentence
is injected (733 tokens for the first request against 697 thinking off), an earlier turn's reasoning is replayed into
the prompt, and the reply opens a think block.

## Episodes (xhigh, reasoning replayed, greedy, 16k per step)

| | rle twin (solvable) | K3 shallow (impossible: the rates file is absent) |
|---|---|---|
| BASE | solved, 15 steps, 10.7 min (thinking off: 5 steps, 1.9 min) | **declared impossible** at step 21, after the step-20 reminder, 47.6 min (thinking off: stuck, 18 steps, 15.7 min) |
| PIA | solved, 15 steps, 9.7 min (thinking off: 5 steps, 2.1 min) | declared impossible at step 21, after the step-20 reminder, 49.0 min (thinking off: declared at step 10, before any reminder, 6.3 min) |

- **Cost:** 117 min for the four episodes against 26 min thinking off, **4.5x**. About half of it is prefill (the
  prompt is re-read every step: 122k to 134k prompt tokens per K3 episode) and half generation (14k tokens).
- **Step cap and runaways:** 76 requests, none cut at the cap, none failed to stop; the longest single reply was 5,757
  tokens. Greedy thinking looked healthy here.
- **Context:** the largest prompt was 16,678 tokens at step 21 with all reasoning replayed (~47k characters of it).
  The thinking-off main run's largest prompt was 17,616; adding a K3 episode's replayed reasoning still leaves room
  in 49k. No overflow expected on the main items.
- **How xhigh spends its steps:** both models first read every file in the workspace one call at a time (11 steps,
  each reply 30 to 90 characters of reasoning), then wrote the solution; reasoning bursts of 1,000 to 14,000
  characters came only after that. That is why the easy twin took 15 steps instead of 5.
- **The adapter's edge did not show here.** With thinking on, BASE and PIA made identical tool calls for the first 13
  of 15 twin steps and the first 12 of 21 K3 steps, and both declared K3 only after the reminder; thinking off, PIA
  declared it at step 10 unprompted and BASE never did. One item, so a hint, not a result: the adapter was trained
  with thinking off.

## What it means for the A/B (decisions for Mark)

- **Agent half, the main run's 30 items per arm:** thinking-off took 7.2 lane-hours per arm; at 3x to 5x that is
  22 to 36 lane-hours per arm, **about 22 to 36 hours of .194 for both arms** on two lanes. Seed 2 alone (10 items
  per arm) is about 7 to 12 hours, one night.
- **M1 half (240 items per arm, both arms at once, one lane each):** from A6's token counts (xhigh, unanswerable median
  ~1,441 tokens, answerable ~174), about 6 hours without runaways; up to ~14 hours if a fifth of the invented items
  run to a 16k cap, as 5 of 24 did at xhigh in A6. An 8k cap halves the worst case and still shows every runaway.
- **Greedy stays** unless M1 shows runaways; settings otherwise as this run (16k step cap, reasoning replayed, 49k).
- **Preserved-reasoning probe** (Mark's question, 11-19): the two declaration steps here are its first cases; re-asking
  each with the earlier reasoning stripped needs .194 up, so it can ride along with the next run.
