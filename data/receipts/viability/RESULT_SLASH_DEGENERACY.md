# RESOLVED — a slow stream consumer makes llama-server latch into degenerate `/` output

> **Final status (2026-09-10 00:08).** The trigger is **consumer backpressure**, isolated by a
> single-variable experiment. The caveat block below is kept for the record; it was correct when
> written and the proxy is now rehabilitated as an observation tool.
>
> | drain mode | latch | responses >90% `/` | result | wall |
> |---|---|---|---|---|
> | **inline** (awaits client per chunk) | task 2, **3/3 runs** | 24/28 | 2 PASS, 11 INFRA | ~90 min |
> | **decoupled** (client cannot backpressure) | **none** | **0/54** | **19 PASS, 1 FAIL, 0 INFRA** | 11 min |
>
> Same proxy binary, same server flags, same 20 tasks, same order. Only `--drain-mode` differed.
>
> **Claim now supported:** *when the HTTP client drains the SSE stream slowly, llama-server
> (VBR `-ctk vbr -ctv vbr --vbr-floor t2`, IQ3_XXS, gfx1201) latches into degenerate output and
> stays degenerate until restart.* This is a real server-side fault with a controllable trigger,
> not an artefact of logging — the proxy only reads `delta.content` and cannot manufacture 4096
> clean `/`.
>
> **P-D1 (55%) CONFIRMED.** **Mechanism still unproven** — see P-D2.

# Superseded caveat (kept for the record)

> **Read this first (added 2026-09-09, 22:26, after the no-proxy control).**
> The no-proxy control ran **20 tasks, 18 PASS / 2 FAIL, zero INFRA_ERROR, in 11 minutes** —
> **no latch at all**. Pre-registered P-N1 (70%) is **FALSIFIED**.
>
> | run | proxy | clean tasks before latch |
> |---|---|---|
> | bitdepth_iq3xxs_v5 | no | 16 |
> | cacheab_ctrl | **yes** | **2** |
> | cacheab_treat | **yes** | **8** |
> | noproxy_ctl | no | **20/20, never latched** |
>
> **`tools/llmproxy` is now the leading suspect for the latch rate**, exactly as the
> pre-registration said it would become if this control came back clean. Everything below was
> measured through the proxy and must be read as conditional on it.
>
> **What survives:** the latch is real without the proxy — v5 latched at task 16 unproxied and
> stayed latched for 13 tasks. So the phenomenon exists; the proxy appears to raise its rate.
>
> **What does NOT survive:** the `/` character finding is established **only under the proxy**.
> We have never captured the text of an unproxied runaway — v5's 13 runaways left empty traces,
> which is why the proxy was built. **It is unknown whether v5's unproxied runaways were slashes.**
>
> **Not reportable to buun or Tom** until the proxy is either cleared or the mechanism identified.

# Original result (proxied runs only)

**Date:** 2026-09-09. **Arm:** `cacheab_ctrl` (`--ctx-checkpoints 32`, the default).
**Model:** Qwen3.8-27B-GSQ-RCO-IQ3_XXS, VBR (`-ctk vbr -ctv vbr --vbr-floor t2`), `-np 1`, no MTP.
**Wire capture:** `data/receipts/viability/cache-ab/wire_ctrl.jsonl` (via `tools/llmproxy`).
**Pre-registered:** `PREREG_CACHE_REUSE_AB.md`. TREAT arm still running at time of writing.

## What the "runaway" actually is

Nobody had ever looked. It is not unbounded reasoning and it is not a failure to call tools:

```
'////////////////////////////////////////////////////////////////////  … 4096 chars … '
```

**100% forward slashes**, head, middle and tail. Top-40-char-shingle share **99.1%**.
4096 characters ≈ 4096 tokens at the `-n 4096` cap, at 26.5 tok/s — the 168 s we kept measuring.

This is degenerate token repetition — a decode-level failure, not an agent-logic one. It moves the
suspect list from prompts and stopping rules to KV cache / numerics / quantisation.

## It latches

| arm | clean tasks before onset | after onset |
|---|---|---|
| v5 | 16 | 13/13 failed, never recovered |
| cacheab_ctrl | **2** | 20/20 failed, never recovered |

`ctrl` ran clean through tasks 1-2 (`tool_calls`, `stop`, 179/45/196/467-char normal outputs,
zero slashes) and from task 3 onward **every single first call was 100% slashes**. Once it starts
it never recovers within the life of the server; a restart clears it (probe B, and tasks 1-2 here).

**The latch point varies (16 vs 2); the latch itself does not.** That is the shape of a stochastic
trigger plus a persistent corrupt state, not a deterministic input-dependent bug.

## Prediction scoring

**P-C1 — CTRL reproduces onset. 75%. CONFIRMED**, more severely than predicted: 6/6 past task 17,
and in fact 20/22 overall.

**P-C4 — runaway text is degenerate, not coherent. 50%. CONFIRMED**, unambiguously.
Logged as a coin flip because nobody had ever seen this output. It is the single most useful thing
the proxy has produced: "the model stops emitting tool calls" and "the model emits 4096 slashes"
imply completely different investigations, and until today we had only the former.

**P-C3 — `sys_sha` identical across tasks. 80%. FALSIFIED.**
**22 distinct system-prompt hashes across 44 chat requests** — one per task. The earlier receipt's
claim that the system prompt is byte-identical across tasks (asserted at 35,207 chars) is **wrong**,
and it was load-bearing for the cache-similarity mechanism.

*But the mechanism survives, narrowly.* The prompts differ by at most 28 characters
(`sys_chars` spans 17,656-17,684, 12 distinct sizes), i.e. they are ~99.8% identical — consistent
with an embedded per-task path. That is exactly why the server reports `f_sim_best = 0.992-0.997`
and picks a foreign slot. So: the premise as stated was false, the conclusion it supported is not
yet damaged. Both facts belong in the record.

**P-C2 — TREAT suppresses it. 45%. PENDING**, arm running.

## Open — the proxy is a confound and has NOT been excluded

`ctrl` latched at task 3 where v5 latched at task 17, and `ctrl` is the first run to go through
`tools/llmproxy`. Arguments that the proxy is not the cause:

- A corrupting proxy should fail from task 1; tasks 1-2 were clean, with correct tool calls.
- The end-to-end validation task passed through the proxy earlier the same evening.
- Measured overhead is 0.2% and chunks are forwarded before they are parsed.
- The parser only *reads* `delta.content`; it cannot manufacture slashes that did not cross the wire.

None of these is proof. **Required control: run the first ~6 tasks against the server directly,
no proxy, and see whether the latch still occurs.** Until that runs, every conclusion here is
conditional on the proxy being transparent.

## Why this matters more than the timeout finding

"An agentic benchmark times out" is a harness story. "This model on this build emits 4096 `/`
tokens and never recovers until restart" is a concrete inference bug, and it is the kind of thing
worth reporting to buun/turboquant once the proxy is excluded and the TREAT arm is in.

---

## Addendum — no-proxy control, 2026-09-09 22:25

`noproxy_ctl`: VBR identical, harness → `:8090` directly, 20 tasks, fresh server.
**18 PASS / 2 FAIL / 0 INFRA_ERROR in 11 minutes (~34 s/task).** A latched task costs 300 s, so
20 latched tasks would have taken ~100 minutes; the wall time alone rules out a latch.

It tracked v5 **exactly** through task 16 — the same two tasks failed
(`t02_file_read/t03_read_paginated`, `t03_patch_edit/t05_v4a`) — then diverged precisely at v5's
latch point, passing task 17 and running clean to 20.

### Two consequences

**1. A usable bit-depth number, finally.** IQ3_XXS on the first 20 tasks: **18/20 = 90.0% valid
pass rate**, 0% infra. The first gradeable agentic result of the day, and it came from removing
our own instrumentation.

**2. The proxy has to be cleared before any of this is reportable.** Latch positions 2 and 8
(proxied) against 16 and never (unproxied) is suggestive, but n=2 per condition and the trigger
is stochastic — this is not yet proof.

### Candidate mechanisms (none tested)

- **Not client disconnect.** `ctrl` latched at task 3 with no prior timeout, so no disconnect had
  occurred. Orphaned upstream generations cannot explain onset.
- **Socket drain timing.** The proxy adds a hop and drains with `iter_any()`; if it drains slower
  than a direct client, the server's send path stalls differently, and VBR re-tiers on timing.
- **Connection churn.** A fresh `ClientSession` per request means no keep-alive reuse, so the
  server sees a new connection for every call.
- **Plain chance.** n=2 per condition.

### Next test

Repeat the proxied arm on the same 20 tasks. Latch again → 3/3 proxied vs 0/2 unproxied, strong.
Run clean → chance, and the earlier arms were unlucky. This must run before the probe matrix,
because the probe matrix assumes a latched server is a *model* state rather than a proxy artifact.

---

## Final — backpressure isolated (2026-09-10)

**`decoupled_run`:** 20/20 tasks, **19 PASS / 1 FAIL / 0 INFRA_ERROR**, 11 minutes.
54 responses captured, **zero** above 90% slashes, **zero** `finish_reason=length`.
The only difference from `proxy_repeat` (which latched at task 2) is that the upstream read no
longer waits on the downstream write.

### Full run ledger

| run | client | latch at | result |
|---|---|---|---|
| bitdepth_iq3xxs_v5 | direct | 16 | 14 PASS / 2 FAIL / 13 INFRA |
| cacheab_ctrl | proxy inline | 2 | 2 PASS / 20 INFRA |
| cacheab_treat | proxy inline, ckpt 0 | 8 | 8 PASS / 14 INFRA |
| noproxy_ctl | direct | none | **18 PASS / 2 FAIL / 0 INFRA** |
| proxy_repeat | proxy inline | 2 | 2 PASS / 11 INFRA (stopped early) |
| **decoupled_run** | **proxy decoupled** | **none** | **19 PASS / 1 FAIL / 0 INFRA** |

Direct 1/2, inline 3/3, decoupled 0/1. The dose-response tracks consumer speed.

### What is established vs hypothesised

**Established:** slow SSE consumption triggers a latching degenerate-output state on this build;
a restart clears it; the harness's token ladder and 960 s timeout were amplifiers, not causes.

**Hypothesised, untested:** that the corruption path is idle-slot VBR re-tiering — a slot stalled
mid-generation being classified idle and having its KV re-quantised in place. The log lines exist
(`publish_idle: VBR_IDLE_CAPTURE`, `VBR_RETIER_PREFLIGHT`) but nothing has been traced.
**P-D2 (50%, pre-logged): `--no-vbr-prompt-cache` on an INLINE run also suppresses the latch.**
That converts correlation into an identified mechanism and is the next test.

**Still unexplained:** v5 latched at 16 with a direct client. Consistent with a direct client
occasionally stalling, but not shown.

### Corpus note

`t03_patch_edit/t05_v4a` failed in every clean run (v5, noproxy, decoupled) — a genuine content
failure. `t02_file_read/t03_read_paginated` failed in v5 and noproxy but passed decoupled, so it
is borderline. Best clean estimate for IQ3_XXS on tasks 1-20: **18-19/20**.
