# Lab Spec: Tool-Call Temperature Sweep (Gemini task)

**For:** Gemini (executor). **Spec + validated scripts:** Fable (Architect). **Owner:** Mark.
**Date:** 2026-07-14. **Rig:** 4× Tesla P100, node `.194` (`ai-supermicro-server`).

## The question
Temp-0 tool-calling was quant-robust to Q3 (all tiers 24/24) — because greedy argmax dodges the
damaged low-confidence tail. **Real agents sample (temp 0.6-0.7), which can LAND in that tail.**
Does realistic temperature expose a floor at low quant that temp-0 hid? Q8_0 is the control: if
Q8 also degrades at temp 0.7, the failures are *sampling*, not quant; if only Q3/Q4 degrade while
Q8 holds, that's the quant-tail-under-sampling interaction — the real agentic floor.

## ⚠️ EXECUTION MODEL — read first (this is why the last runs thrashed)
- You (Gemini) run on `mark-desktop-pc`. **All compute is on `.194`, reached by SSH.** The desktop
  has no `nvidia-smi` / no `llama_stock` — expected, not a failure.
- **The scripts are already staged and VALIDATED on .194. Do NOT rewrite them.** Your job is to
  RUN one command and REPORT the receipts. `run_temp_sweep.sh` serves each tier once (via the
  wait-based `serve_persistent.sh` — the launcher that works; a bare `setsid $BIN` orphans
  llama-server and it hangs at 0 VRAM), then runs `toolcall_bench.py` at temps {0.0, 0.4, 0.7}
  (temp 0 = 1 rep deterministic; temp>0 = 5 reps to measure a real pass RATE, since sampling is
  stochastic). Tiers: Q3_K_M, Q4_K_M, Q8_0.

## RUN IT — exactly this, as a BACKGROUND task
Run the driver in the **foreground over a single persistent SSH**, held open by your background-task
mechanism. Do NOT background it on the remote with `&`/`nohup`/`setsid` (rapid/again-detached SSH
gets throttled → exit 255; the foreground-over-one-ssh pattern is what finally worked):

```
ssh -o ServerAliveInterval=15 mark@10.0.0.194 'bash ~/quant_ladder/run_temp_sweep.sh'
```

It takes ~45-75 min (3 tiers × [1 model load + ~264 tool-call requests]). The command's stdout
streams the per-config result lines. Let it finish; do not poll .194 with repeated SSH (that
throttling is what caused the 255s).

## ⚠️ REPORTING (Ground Truth Gate — GEMINI.md is in force)
- **Report ONLY numbers that exist in the JSON receipts on disk.** After the run, read each file
  and paste its `stat`/content — do not restate expected numbers or summarize from memory.
- Receipts land in `.194:~/quant_ladder/temp_sweep/sweep_<tier>_t<temp>.json`. There should be 9
  (3 tiers × 3 temps). For each, the headline is the `success`/`n` ratio and `by_cat`.
- Pull the summary line per file:
  ```
  ssh mark@10.0.0.194 'for f in ~/quant_ladder/temp_sweep/sweep_*.json; do python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(\"%s: %d/%d (%.1f%%) | \"%(sys.argv[1].split(\"/\")[-1],d[\"success\"],d[\"n\"],100*d[\"success\"]/d[\"n\"])+\" \".join(\"%s=%d/%d\"%(c,d[\"by_cat\"][c],d[\"by_cat_n\"][c]) for c in sorted(d[\"by_cat\"])))" "$f"; done'
  ```
- If a tier prints "NEVER READY" in the stdout, STOP and report it verbatim — do not fake results.
- **Do not touch, edit, or "fix" the scripts.** If something errors, report the verbatim error and
  stop; the Architect adjusts. (You are running validated tools, not authoring them.)

## Deliverable
The 9-line summary (tier × temp → overall % + per-category), plus the raw receipt paths. That's it.
The Architect verifies against disk and interprets.

## Architect prediction (logged pre-run, score against this)
- **Q8_0: flat ~100% across all temps** — near-lossless weights, so sampling has a clean
  distribution to sample from; temp alone shouldn't break well-specified tool calls. If Q8 *does*
  drop at 0.7, the effect is sampling-general, not quant.
- **Q3/Q4: I expect the FIRST real degradation of this whole campaign at temp 0.7** — sampling lands
  in the ~100×-inflated tail that greedy dodged. If it appears, it should concentrate in **nested +
  parallel** (the structurally hardest, most tail-sensitive) and in the "no tool_call at all" /
  wrong-arg-value failures. Confidence: moderate. If Q3/Q4 also stay ~100%, then tool-calling is
  robust even under sampling and the agentic floor is purely a multi-turn/cascade phenomenon —
  itself a strong finding.
