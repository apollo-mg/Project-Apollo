# Prereg — argus noise floor: the same model on both arms

**Written 2026-09-22 before any run.** The control that decides whether every discordance number
this campaign has produced means anything.

**Prior art checked:** `ledger_precheck.py "test-retest reliability same model twice noise floor
discordance" --deep` -> `agentic-ladder/RESULT_PA0_GATE.md`, `battle16gb/HA20_SAMPLING_ARMS.md`,
`hle-mini/POWER.md`, `[[agent-benchmark-determinism]]`.
**What this adds:** `RESULT_PA0_GATE` measured the agentic noise floor at **temp 0** and found it
**zero** — 15/15 identical verdicts *and* identical tool-call counts. **Argus runs at temp 1.0**
(`SAMPLING.md`, Qwen3.8 thinking profile), and its noise floor at that temperature has never been
measured. The same receipt records that the earlier **temp-0.6** calibration flipped **5 of 16
scenarios** between passes. Nothing establishes the figure for argus at temp 1.0, and every
sizing number depends on it.

## Why it matters right now

| run | discordance |
|---|---:|
| v3 pilot | 12.1 % |
| v4 pilot (broken scorer) | 22.2-27.6 % |
| **v4 re-run (correct scorer)** | **10.3 %** |

If two *identical* arms disagree at ~10 %, then 10.3 % between two different quants is
**sampling variance with a model label attached**, every comparison to date is void, and the
swinging between runs is explained. This is the `AFM-39` discipline applied to the instrument
itself rather than to a single verdict.

## Design

Both arms are **`Qwen3.8-27B-Q6_K`**, the identical file, on `.194`:

| arm | GPUs | socket | port | fixture |
|---|---|---|---|---|
| N1 | {0,1} | 0 | 8084 | `pilotA` |
| N2 | {2,3} | 1 | 8085 | `pilotB` |

Everything else matches the v4 re-run exactly: buun `08826ad6`, `-c 65536 -ngl 99 -sm tensor
-fa on -ctk f16 -ctv f16 -np 1`, `reasoning_effort: medium`, card sampling (temp 1.0 / top_p 0.95
/ top_k 20 / min_p 0.0), `families_v4.json`, 40 items, 1 rep, 900 s timeout, `TZ` pinned from the
fixture, fixed scorer. **The only difference between the arms is the sampling draw.**

Note the two arms sit on different sockets and different GPU pairs, so a difference could in
principle come from hardware rather than sampling. `splitscale/RESULT_2V4.md` measured the two
pairs as equivalent (13.00 vs 13.03 t/s), and `[[194-partitioning-and-weather]]` permits this
because both arms share one partition scheme. Recorded as a declared limitation, not dismissed.

## Predictions, committed before data

| id | prediction | confidence | falsifier |
|---|---|---|---|
| **P-N1** | noise-floor discordance is **below 10.3 %**, the v4 re-run figure | 0.55 | >= 10.3 % |
| **P-N2** | noise-floor discordance is **> 0** — temp 1.0 is not deterministic | 0.90 | 0 discordant pairs |
| **P-N3** | both arms' pass rates land within 10 pp of each other | 0.80 | a wider gap |
| **P-N4** | `WRONG-INACTION` stays 0 on both arms, as in every run so far | 0.75 | any inaction failure |
| **P-N5** | gate rungs (rung 1) pass on both arms | 0.85 | a gate failure |

**P-N1 is the one that matters.** At 0.55 I am close to genuinely uncertain, which is the honest
position: `RESULT_PA0_GATE`'s temp-0.6 figure of 5/16 suggests the floor could be high, and its
temp-0 result of 0/15 suggests sampling is the entire story.

## What each outcome means

| noise floor | reading | action |
|---|---|---|
| ~10 % or above | 10.3 % is entirely sampling; **every quant comparison to date is void** | argus moves to temp 0, or to reps sized from this number |
| ~2-3 % | 10.3 % is mostly signal | sizing stands; proceed to authoring |
| between | gives the **rep count** A1's sizing has always been missing | size reps, then re-pilot |

## What this cannot establish

- **One rep of a two-arm comparison is one sample of the noise**, not a distribution. A second
  pair would tighten it; this is the cheapest informative version.
- **Socket and GPU-pair are confounded with arm**, as declared above.
- **Nothing about quant differences.** Both arms are the same file; that is the point.
