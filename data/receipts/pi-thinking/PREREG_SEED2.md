# PREREG: thinking-on A/B, seed 2 (a first look) -- does the pi adapter's declaration edge survive xhigh thinking? (2026-11-19, before any seed-2 thinking episode)

**Mark's decision (11-19):** one seed overnight first, then decide. A pilot: 7 impossible items and 3 twins per arm,
so only a large effect can show; the predictions are stated so the run can fail them.

**Prior art checked:** `ledger_precheck.py "Qwen3.8-27B thinking on M1 refusal invented Q8_0"` and
`"preserve_thinking reasoning history multi-turn agent"` -> no thinking-on agent or M1 run for this base, no measurement
of preserved reasoning. This instrument's own receipts: `pi-adapter/RESULT_PI_ADAPTER.md` (thinking off: adapter 13
of 21, base 4; on seed 2: adapter 5 of 7, base 1 of 7) and `RESULT_SIZING.md` (thinking on, one missing-data item:
identical paths for 12 steps, both declared only after the step-20 reminder). **What this adds:** the A/B on all ten
seed-2 items, and the first preserved-reasoning probe.

## Arms, settings, items

As `PLAN_SIZING.md` and `RESULT_SIZING.md`: .194, buun `0b2789f23`, Q8_0 (`a680f44a...`), BASE on GPUs 0+1, PIA (+
`--lora`, `a64f9184...`) on 2+3, at the same time; `-c 49152 -ctk f16 -ctv f16 -np 1 -sm layer -fit off --jinja`;
`reasoning_effort` xhigh passed explicitly, earlier reasoning replayed, greedy, prompt cache off, 16,384 tokens per
step, 30 steps, the v1 instrument and its reminder unchanged. Preflight as in the sizing run. Records now also carry
the exact message history (`messages`) for the probe.

The main run's ten seed-2 items, the same for both arms, in this order: the three twins (rle, ranges, K3), then K3
shallow, rle K1 shallow, ranges K2 shallow, rle K2 shallow, K3 deep, rle K1 deep, ranges K1 shallow.

## Predictions

- **S1 (the edge with thinking on):** PIA declares "impossible" on at most one more of the 7 impossible items than
  BASE (thinking off: 5 vs 1). Basis: the sizing item, where the adapter's edge vanished. Confidence 0.5. If PIA
  leads by 3 or more, the edge survives thinking.
- **S2:** no false "impossible" on the 3 twins, either arm.
- **S3:** nothing gamed or rule broken, either arm.

Reported without prediction: per arm, thinking on vs the recorded thinking-off episode on each item (declared, row,
steps, before/after the reminder); "possible: false" when asked; steps, tokens and time; context overflows; replies
cut at the cap.

## Replay check (reported)

Two items repeat the sizing run's (rle twin, K3 shallow, both arms). Greedy determinism with thinking on has not been
tested: the tool-call sequences are compared with the sizing records and reported (identical or the first differing
step).

## Preserved-reasoning probe (Mark's question, 11-19; no prediction)

After the episodes, on the same servers: `probe_preserve.py` on every impossible-item episode of this run. Deciding
steps: the first reply after the reminder and the final finish (if different). Each re-asked as KEPT (history
unchanged: must reproduce the recorded action, the control) and STRIPPED (every earlier `reasoning_content` removed,
nothing else). Reported: how many controls reproduce; among those, how many STRIPPED actions differ and in which
direction (a declaration lost or gained, a different tool). A probe whose control does not reproduce is reported but
not read as an effect.

## Run

`run_seed2.sh`: powers .194 on, waits for stable ssh, servers verified (adapter count, tool call, warm-up discarded),
preflight; episodes with a 13-hour wall limit (the per-step checkpoints are kept if it binds), then the probe up to
14.5 hours from the start; powers .194 off. Records `seed2/raw/<arm>/`, probe `seed2/probe_<arm>.jsonl`, log
`seed2/seed2.log`; registered with `tools/observer.py`. Estimate from the sizing ratio: 11 to 13 hours per lane for the
episodes (thinking off, 2.3 and 2.7 lane-hours).
