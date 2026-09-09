# PREREG: does the sub-3-bit quality drop show up in AGENTIC work?

**Written 2026-09-09 before the runs.** Predictions logged with confidence; scored honestly after.

## The gap this fills

ISTA's published curve (`reference/ISTA_GSQ_RCO_BASELINES.md`) measures **AIME25, GPQA-Diamond,
LiveCodeBench v6** — all **single-turn**. It shows a sharp knee at 3.0 bpw: 91.2 at IQ3_XXS against a
91.87 base, 89.6 at IQ2_S, 86.0 at IQ2_XS.

**Nobody in that comparison tested multi-turn agentic tool use.** Our TURBO result suggests the floor
behaves differently there — a model can hold single-turn quality and still fail to terminate on
"read the tail of a file." This measures the axis their charts do not.

## Design

| arm | model | GiB | isolates |
|---|---|---|---|
| A | `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp` | 9.73 | 3-bit baseline |
| B | `Qwen3.8-27B-GSQ-RCO-IQ2_XS-mtp` | 8.17 | **bit depth alone** |

Same base model, same quant family, same MTP head, same everything except bit-width.
`-c 32768 -np 1 -fa on --kv-unified -ctk vbr -ctv vbr --vbr-floor t2 --vbr-vram auto`, **no
`--spec-type`**, fixed grader, fresh server per arm.

**The baseline is re-measured rather than reused.** det02 scored 0.943 but ran *with* MTP and hit the
acceptance collapse partway through. Comparing a 2-bit MTP-off run against a 3-bit MTP-on-degraded
run would confound quantisation with the defect found on 2026-09-08. Costs ~40 min, removes the
objection entirely.

## Predictions

- **P1: arm A (3-bit) completes 61 tasks without a contiguous wall.** 70%. MTP-off removed VBR
  clamping in the TURBO run (watermark flat at 13,312 vs the 21,504 trigger), which suggests the
  draft head was contributing most of the checkpoint pressure.
- **P2: arm B (2-bit) shows a LARGER agentic drop than the 5.9-point single-turn drop ISTA measured
  at this bit-width.** 65%. Multi-turn work compounds errors across turns and adds a stopping-rule
  requirement that single-turn benchmarks never test.
- **P3: arm B's failures are dominated by non-termination, not wrong answers.** 60%. That is the
  shape TURBO showed at 2-bit (bimodal: ~100 tokens or ~8,300), and it is a different failure mode
  from "gets the answer wrong."
- **P4: arm B still completes the corpus** (fails tasks but does not wall). 45% — genuinely
  uncertain. TURBO walled at 2-bit, but TURBO was also a merge; GSQ-RCO IQ2_XS is the strongest
  2-bit recipe by ISTA's own numbers.

## What would falsify the premise

If arm B's `valid_pass_rate` drop is close to ISTA's 5.9-point single-turn drop, then single-turn
curves **do** predict agentic degradation, and the extra measurement is unnecessary. That would be a
useful negative result and is explicitly worth reporting.

## Known limits

- K=1 per arm. Existence proof, not a rate.
- 61 tasks, one corpus, one hardware target.
- The verdict schema still collapses INFRA/FAIL — report all three counts separately, never a single
  rate (see `RESULT_TURBO_IQ2M_WALLED.md`, where 6/6 INFRA produced a flattering 1.000).

---

## PROTOCOL CHANGE (2026-09-09, mid-experiment): server-side `-n 4096` added

**First attempt abandoned at 17/61.** Arm A produced `PASS 8 / INFRA_ERROR 9` — a 53% timeout rate —
and `valid_pass_rate 8/8 = 1.000`, the same hollowed-denominator artifact this campaign keeps hitting.

**Cause:** `RESULT_RUNAWAY_ROOT_CAUSE.md`. Every task declares `max_tokens: 4096`; hermesbench parses
it and never sends it; llama-server's `--predict` defaults to **-1 (infinity)**. Measured on the
abandoned arm: **9 of 16 requests (56%) exceeded 4096**, max 9,379. The run was measuring the harness
defect, not bit depth.

**Change:** both arms relaunched with `-n 4096` on the server, which enforces exactly the budget the
corpus already declares. Nothing else changed.

**Why this is a fix and not a thumb on the scale:** it applies the corpus's own stated budget, equally
to both arms, and converts unmeasurable `INFRA_ERROR` timeouts into graded outcomes. Without it the
comparison measures how often each model hits a non-terminating task — a real property, but not the
one this prereg asks about.

**The abandoned run is kept** as `results/bitdepth_iq3xxs_NOBUDGET` — it is direct evidence of the
unenforced-budget defect reported in am423 issue #5.

**New run ids:** `bitdepth_iq3xxs_budget`, `bitdepth_iq2xs_budget`.

**Prediction added before relaunch — P5: the budget cap cuts INFRA_ERROR by more than half in arm A**
(from 53% to under 25%). 75%. If it does not, timeouts have a second cause beyond unbounded
generation.

---

## PROTOCOL CHANGE 3 (2026-09-09): `HERMES_MAX_TOKENS=4096`

v4 ran clean of orphans (process tree verified) and still produced **43% INFRA with 7/13 requests
over the 4096 cap**, max 12,999. So **server-side `-n 4096` does not bound generation** on this
build — confirmed independently of AFM-36.

Found the client-side lever in hermes-agent `cli.py:2670`:

```python
_env_mt = os.environ.get("HERMES_MAX_TOKENS")
_mt = _model_config.get("max_tokens")
self.max_tokens = _int_or(_env_mt, None) if _env_mt else (_mt if isinstance(_mt, int) else None)
```

With neither set the agent sends `max_tokens: None` (omitted), so the request carries no budget at
all. `HERMES_MAX_TOKENS` makes it send an **explicit** value — a different code path from the server
default. hermesbench builds the subprocess env as `{**os.environ, ...}` in both
`hermes_invocation.py` and `run_real.py`, so exporting it propagates.

**This is also the concrete fix for am423 issue #5**: rather than "pass `task.max_tokens` through,"
the harness should set `HERMES_MAX_TOKENS` from `task.max_tokens` when spawning the agent.

**P6: with `HERMES_MAX_TOKENS=4096`, no request exceeds ~4096 tokens.** 70%. If explicit
`max_tokens` also fails to bound, then nothing at any layer bounds generation on this build and the
only viable control is the wall clock — which would make agentic benchmarking on this stack
fundamentally unreliable, and is worth reporting on its own.

---

## SCORING — P6 FALSIFIED (2026-09-09, same day)

**P6 was: "with `HERMES_MAX_TOKENS=4096`, no request exceeds ~4096 tokens." Logged at 70%.**
**Result: FALSIFIED.** The server's own log records **14 generations ending at exactly 8192**
in run v5 — with the variable exported for the whole run.

### Why the reasoning failed

The `cli.py:2670` snippet quoted above is real, but **it is not the code path hermesbench uses.**
hermesbench drives `run_agent.py`, which constructs the agent at `run_agent.py:1477`:

```python
agent = AIAgent(base_url=base_url, model=model, api_key=api_key, max_iterations=max_turns,
                enabled_toolsets=..., disabled_toolsets=..., save_trajectories=..., ...)
```

**`max_tokens` is never passed**, so `agent.max_tokens` keeps its default `None`. I found the
right code and the wrong entry point — the error was reading a grep hit as *the* implementation
without checking which caller the benchmark actually invokes. (`HERMES_MAX_TOKENS` is read only in
`cli.py`, `gateway/run.py`, `api_server.py`.) Environment propagation was never the problem;
the receiving path simply doesn't read it.

**Verified on the wire, not by inference:** a capture stub recorded the outgoing request bodies.
With `HERMES_MAX_TOKENS=1024`, and with it unset, **all 9 captured requests omitted `max_tokens`
entirely** (`[messages, model, stream, stream_options, tools]`).

### The 8192 comes from somewhere else

`finish_reason='length'` triggers a continuation that boosts and *does* send an explicit cap
(`turn_iteration_prep.py:382`, injected by `chat_completion_helpers.py:1381`):
`(agent.max_tokens or 4096) * 2**n` → **8192, 16384, 32768** — hard-anchored to the literal 4096
because `agent.max_tokens` is `None`, and **not reachable from any env var or server flag.**
An explicit request cap also overrides the server's `-n`, so `-n` bounds only the first call.

### Retracted recommendation — do NOT send this upstream

The line above — *"This is also the concrete fix for am423 issue #5: the harness should set
`HERMES_MAX_TOKENS` from `task.max_tokens` when spawning the agent"* — **is wrong and is retracted.**
Setting that variable does nothing for the `run_agent.py` path. Had we posted it, we would have
sent an upstream maintainer a fix that cannot work. The follow-up comment was drafted but never
approved; it must not go out in that form.

A correct fix would pass the cap into `AIAgent(...)` at `run_agent.py:1477` (or have hermesbench
supply `max_tokens` per request), and separately bound the continuation ladder — which today can
reach 4096+8192+16384+32768 = **61,440 tokens ≈ 2,318 s** on this hardware for a single turn.

**P6's closing sentence was right for the wrong reason:** generation is effectively unbounded from
the benchmark's side, and the wall clock is the only control the harness currently has.
