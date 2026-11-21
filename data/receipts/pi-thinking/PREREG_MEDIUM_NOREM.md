# PREREG: two more cells to take xhigh apart -- thinking at medium (no sentence), then xhigh with the reminder off (2026-11-20, before any run of either)

**Mark (11-20):** "Might as well have the data... We can do whichever you prefer first." Order: medium first (with
`RESULT_SENTENCE.md` it splits xhigh into thinking vs sentence), then the no-reminder cell, chained on one boot.

**Prior art checked:** `ledger_precheck.py "medium effort thinking reminder off declared impossible"` -> this series:
`RESULT_SEED2.md` (xhigh: base 7/7, adapter 7/7; base 5 of 7 right after the step-20 reminder), `RESULT_SENTENCE.md`
(the sentence alone, thinking off: base 2/7, adapter 4/7; the sentence causes the read-every-file style),
`viability/RESULT_A6_EFFORT_NOT_SAMPLING.md` (xhigh vs medium on factual items, thinking on). **What this adds:** the
two missing cells of the decomposition on the agent test.

## Settings (as `PREREG_SEED2.md` unless stated)

.194, buun `0b2789f23`, Q8_0 with (PIA) and without (BASE) the pi adapter, one lane each; the model's own template;
greedy, prompt cache off, earlier reasoning replayed, 16,384 tokens per step, 30 steps, 49k context. Preflight per
server at both efforts: outcomes render, reasoning replays, think block opens; xhigh injects its sentence, **medium
injects nothing** (checked on .73: 695 tokens vs 697 thinking off, the difference being the think tail).

## Cell M: thinking on at `medium`, reminder on

All ten seed-2 items per arm, the seed-2 order. Then the preserved-reasoning probe on its impossible items (as in
`RESULT_SEED2.md`, each probe re-asked at the episode's own effort), up to one hour per lane.

- **M1:** BASE declares "impossible" on at least 5 of 7 (thinking off 1, sentence alone 2, xhigh 7): thinking carries
  xhigh's effect. Confidence 0.6. At most 2 means neither part alone does it: xhigh's effect needs both.
- **M2:** the read-every-file style goes away without the sentence: on the 3 twins, the median number of calls before
  the first write is at most 6 for each arm (thinking off 2-5, sentence 9-11, xhigh 10-13). Confidence 0.7.

## Cell N: xhigh, reminder off

An episode then ends only by the agent's own finish or the 30-step budget (as the bridge cells). Items: the
impossible items whose xhigh episode received the step-20 reminder (BASE: ranges K1, ranges K2, rle K1 shallow, K3
deep, K3 shallow; PIA: rle K1 deep, K3 deep, K3 shallow), plus one impossible item per arm that got no reminder at
xhigh as a replay control (BASE rle K2 shallow, PIA rle K1 shallow). The other xhigh items never saw the reminder, so
the cell would replay them unchanged; the control checks that.

- **N1:** with no reminder, BASE still declares on at least 4 of its 7 impossible items, counting the two it declared
  unprompted at xhigh (so at least 2 of the 5 reminded items declare anyway). Confidence 0.5. PIA reported without a
  prediction (4 unprompted at xhigh; 3 reminded items here).
- **N control:** each control item replays its xhigh episode byte for byte; each reminded item is identical to its
  xhigh episode up to the step that carried the reminder.

## Both cells

- **S2/S3 as before:** no false "impossible" on twins (cell M), nothing gamed (both cells).

## Run

`run_medium_norem.sh`: power on, stable ssh, servers verified, preflight at both efforts; per lane: cell M (8 h wall),
then its probe (1 h), then cell N (8 h wall); power off. Records `medium_norem/medium/<arm>/`,
`medium_norem/norem/<arm>/`, probe `medium_norem/probe_<arm>.jsonl`, log `medium_norem/run.log`. Estimate: 10 to 14
hours, overnight.
