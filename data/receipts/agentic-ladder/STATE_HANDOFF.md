# Agentic ladder -- operational state and resume point

**2026-09-19 evening.** Written while the panel was mid-run so it survives a compaction.

## What is running

**Four-arm agentic panel on `.194`**, started 17:44:52, ~50 min per arm, ETA ~21:30.

| arm | model on `.194` | scored bpw | mean KLD | status |
|---|---|---:|---:|---|
| P-BASE | `~/AI/Models/Qwen3.8-27B/Qwen3.8-27B-Q6_K.gguf` | 6.522 | 0.002770 | **DONE 10/15** |
| P-GIQ2 | `~/AI/Models/ladder/Qwen3.8-27B-GSQ-RCO-IQ2_XS-mtp.gguf` | 2.476 | 0.202243 | running |
| P-AIQ3S | `~/AI/Models/ladder/Qwen3.8-27B-AD-IQ3_S-IQ3_XXS.gguf` | 3.732 | 0.048110 | queued |
| P-BPQ2 | `~/AI/Models/ladder/Ternary-Bonsai-2-27B-PQ2_0.gguf` | 2.119 | 0.358047 | queued |

Runner `scripts/run_panel_194.sh`, PID in `/tmp/panel194.pid`, log
`logs/panel.log`, per-arm results `argus/runs/panel_<ARM>.jsonl`.

## Configuration that must not drift

- **One binary for all arms**: `~/prism_llama_cpp/build_sm60/bin/llama-server` on `.194`, commit
  `9a9394a8`. Verified to serve **stock** GGUF as well as types 142/143, so there is no
  cross-binary confound. buun cannot read 142/143 -- it reports
  "gguf_init_from_reader: failed to read tensor info", which looks like a corrupt file.
- **`-sm layer`, never `-sm tensor`.** Ternary aborts tensor-split at
  `ggml-backend-meta.cpp:1086 GGML_ASSERT(split_state.ne[j] % div == 0)` AFTER loading to VRAM.
- **`GGML_CUDA_ALLREDUCE=internal`** is mandatory on `.194`; unset defaults to NCCL, which aborts.
- **`reasoning_effort: medium`**, temp 0, top-k 1, `-np 1`, `-c 65536`, no MTP on any arm.
- **Seed frozen at `806c5016...`** (rebased +28d to 2026-09-24 to keep the Thursday alignment).
  Pool is `argus/scenarios_v1_pool_gate.json`, **15 scenarios** -- `clear-drive-old` excluded as
  mutually unsatisfiable with `free-thursday-pm` (AFM-25b).
- Gateway on **8643** (Mark's production gateway is 8642 -- do not touch).

## Results so far

**P-A0 gate (on `.73`): CONFIRMED.** Two passes of B-PQ2, **15/15 identical verdicts AND
tool-call counts**, several matching to the second. Temp 0 is deterministic for agentic work, so
the noise floor is zero and **one pass per arm suffices**. **0 RUNAWAY in 30 scenario-runs**
against a >4-of-15 stopping rule -- the temp-0 hazard is retired with evidence.

**P-BASE anchor: 10/15 (67%)**, zero void.
**B-PQ2 (gate, `.73`): 9/15 (60%)**, zero void.

**They agree on 14 of 15 outcomes** despite a **129x KLD gap and 3x the bits**. Retention ~90%,
against PrismML's own paper reporting ~76% on Terminal-Bench and SWE-bench.

**The one discriminating scenario so far is `rent-amount`**, and it grades monotonically with
fidelity: Q6_K **CORRECT** (looked it up) -> GSQ-RCO **NO-ATTEMPT** (wrong backend) -> Bonsai
**SUSPECT** (zero tool calls). Everything else is saturated.

## Open obligations

1. **`.194` is powered on** (216 s boot, ~218 W idle). Power it down when the panel is done if it
   is not wanted for the EXL3-vs-ncmoe spill work.
2. Kill the panel gateway (`/tmp/panel_gateway.pid`) after scoring.
3. `.73` is untouched and serving normally -- do not confuse the two nodes.

## Next actions

1. Wait for `PANEL DONE` in `logs/panel.log`.
2. Score: `python3 tools/score_agentic_panel.py argus/runs/panel_P-*.jsonl`. It reports retention
   vs the anchor, P-A1/A2/A3, the paired per-scenario table and **EFFECTIVE N** -- the count of
   scenarios that actually separate the arms.
3. **Root-cause every failure before interpreting** (Mark's instruction). The anchor's 5 failures
   were audited: 3 genuine, 1 designed to split (`cancel-thursday`, "defensible either way"),
   1 arguably harsh (`move-sync-implicit` penalises a helpful extra `gmail.reply`).
4. Expect effective N to be small. If ~1 of 15 discriminates, say so plainly rather than quoting
   a headline rate.

## Findings from today worth carrying

- `FINDING_BONSAI_TEMPLATE_DEFECT.md` -- Bonsai 2 drops the `high` -> `xhigh` alias, so a
  documented value hard-errors. `medium` is byte-identical to stock, so the panel is clean.
- `INCIDENT_73_NVIDIA_SMI_PILEUP.md` -- root cause was a **suspend/wake race in `wake_proxy.py`**,
  since fixed; the `nvidia-smi` timeout guard addresses the amplifier, not the cause.
- The fidelity ladder is complete: `../lowbit-ladder/RESULT_LADDER.md`, 5 of 6 predictions
  confirmed, P-L2 falsified.
