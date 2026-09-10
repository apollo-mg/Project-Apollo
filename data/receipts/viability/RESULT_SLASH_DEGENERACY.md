# RETRACTED — "backpressure isolated" was wrong. The latch is unexplained.

> **Retraction 2026-09-10 01:00.** Two hours ago this file was marked RESOLVED, claiming a
> single-variable isolation of consumer backpressure. **That claim does not survive the overnight
> control arms and is withdrawn.**
>
> The positive control (`pd2_control`: inline drain, stock flags — the exact configuration that
> latched 3/3) **did not latch**: 20/20, 19 PASS / 1 FAIL, 0 slashes. Pre-registered P-D3 (85%)
> is FALSIFIED, and by the pre-committed table both P-D2 arms are void.
>
> ### The full ledger, ordered by start time
>
> | run | client | flags | started | outcome |
> |---|---|---|---|---|
> | bitdepth_iq3xxs_v5 | direct | — | 13:49 | **LATCH** |
> | cacheab_ctrl | inline | ckpt32 | 18:41 | **LATCH** |
> | cacheab_treat | inline | ckpt0 | 20:43 | **LATCH** |
> | noproxy_ctl | direct | — | 22:15 | clean |
> | proxy_repeat | inline | stock | 22:31 | **LATCH** |
> | decoupled_run | decoupled | stock | 23:57 | clean |
> | pd2_novbrcache | inline | no-vbr-cache | 00:32 | clean |
> | pd2_control | inline | stock | 00:48 | clean |
>
> inline **3/5**, decoupled **0/1**, direct **1/2**.
>
> **Every latch is before 22:31. Every run from 23:57 on is clean.** Start time predicts the
> outcome better than any flag I manipulated. The decoupled result — the entire basis for the
> backpressure claim — is fully explained by where it sits in that sequence, with no drain-mode
> effect required.
>
> ### What went wrong methodologically
>
> I ran **sequential arms with one repetition each** against a **stochastic** outcome, and
> attributed every difference to the variable I had just changed. That is invalid, and I did it
> three times in one night: checkpoints (P-C2, falsified), backpressure (claimed resolved, now
> retracted), and idle-cache (P-D2, void). The key comparison arm was **n=1** and I wrote
> "RESOLVED" on it.
>
> I also never logged GPU temperature or clocks per run, despite `gpu-clock-benchmark-discipline`
> requiring exactly that. The card ran under sustained load from 13:49 to ~22:45 and had long idle
> gaps afterwards. **A thermal/clock confound is now a live hypothesis and I have no data to test
> it against**, because I did not record the one thing the project's own rule says to record.
>
> ### What still stands
>
> - The degenerate output is real and captured: 4096 `/`, 99.1% shingle share, across three runs.
> - It latches until server restart.
> - Harness defects (doubling ladder, 960 s timeout, discarded traces) were real amplifiers.
> - IQ3_XXS on tasks 1-20 is **18-19/20** on clean runs; `t03_patch_edit/t05_v4a` always fails.
>
> ### What a valid experiment needs
>
> Interleaved conditions (A/B/A/B, not A-then-B), **≥3 reps per condition**, GPU temp and clocks
> logged per task, and a latch-rate comparison with an interval — not a single clean run treated
> as proof. Nothing goes to buun or Tom before that.

# Superseded claim (kept for the record)

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
