# Pre-registration — does context-checkpoint reuse cause the runaways?

**Registered:** 2026-09-09, before either arm ran. Predictions logged before any result was seen.

## Hypothesis

In `bitdepth_iq3xxs_v5`, every task from #17 (`t04_search_grep/t01_basic`) onward ran away: the
model generated to the output cap without ever emitting a tool call. The server was healthy
throughout (decode 26.5 t/s, prefill 769 t/s). Probe B showed the same task **passes in 20.8 s
when run first on a fresh server**, so it is not task-type and not accumulated agent context.

Proposed mechanism, from the v5 server log on a stuck task:
```
cache_plan_s: selected slot by LCP similarity, f_sim_best = 0.997, f_keep = 0.762
edit/divergence (cached/incoming/lcp/reusable/rewind/append/cache_prompt)
              = (17264/13203/13162/13162/4102/41/1)
restored context checkpoint (pos_min = 13047, n_tokens = 13048, size = 149.626 MiB)
```
The server restored a checkpoint holding the **previous task's** 17,264-token context to serve a
13,203-token incoming prompt, rewinding 4,102 tokens. If that rewind is not semantically clean the
model decodes against another task's tail, which would produce degenerate non-terminating output
from a clean-looking prompt.

**Already ruled out without running anything:** `--cache-reuse` defaults to **0**, so KV-shifting
reuse was never active. The mechanism, if real, is checkpoint restore + slot LCP selection.

## Design

Two arms, the **first 22 tasks in v5's recovered execution order** (16 healthy + 6 past onset).
Everything identical except one flag. Fresh `llama-server` per arm. Both arms through
`tools/llmproxy` so the runaway text is captured — v5 lost 13/13 of them to empty traces.

| | CTRL | TREAT |
|---|---|---|
| `--ctx-checkpoints` | 32 (default) | **0** |
| everything else | identical | identical |

`--timeout-overhead` drops 900 → 300. A runaway is identifiable at call #1 (`finish_reason=length`
at ~170 s), so 960 s of waiting bought nothing but GPU burn.

**Confound acknowledged:** onset at #17 coincides with the `t03_patch_edit → t04_search_grep`
category boundary, so order and category change together. Probe B breaks that tie (the same task
passes when run first), but this design does not re-test it.

## Predictions

**P-C1: CTRL reproduces onset** — ≥3 consecutive runaways beginning at or before task 20.
**75%.** v5 showed it consistently, but the server was restarted and the timeout changed.
*Falsified if CTRL completes 22 tasks with ≤2 runaways.*

**P-C2: TREAT suppresses it** — ≤1 of tasks 17-22 runs away. **45%.**
Deliberately below even odds: the mechanism is plausible and I have a log line consistent with it,
but "plain uptime/VBR drift" remains a live alternative I cannot exclude, and I have not shown the
rewind is actually incorrect — only that it happens.
*Falsified if TREAT runs away at a rate within 1 task of CTRL.*

**P-C3: the system prompt does not drift** — `sys_sha` identical across all 22 tasks in each arm.
**80%.** Tests whether shared `HERMES_HOME` leaks into the prompt. My earlier "not accumulated
agent context" conclusion rested on prompt *size* (~4,647 vs ~4,644 tokens), and equal size is not
equal content. This checks it properly.
*Falsified if sys_sha changes mid-arm — which would reopen agent-state as a cause.*

**P-C4: runaway text is degenerate, not coherent** — the first captured runaway is repetitive or
looping rather than coherent prose that simply never stops. **50%.**
Genuinely a coin flip; nobody has ever looked at this output. It matters because a repetition loop
(sampling/KV corruption) and coherent-unbounded-reasoning (prompt/stopping-rule) have different fixes.

## What will NOT be claimed

If TREAT suppresses the runaways, that shows checkpoints are *implicated*, not that the rewind is
incorrect. Demonstrating the latter needs a prompt-level diff of what the model actually attended
to, which this design does not provide.

---

## SCORING (2026-09-09, both arms complete)

| pred | conf | result |
|---|---|---|
| P-C1 CTRL reproduces onset | 75% | **CONFIRMED** — 6/6 past #17, 20/22 overall |
| P-C2 TREAT suppresses it | 45% | **FALSIFIED** — 6/6 past #17, 14/22 overall |
| P-C3 sys_sha stable | 80% | **FALSIFIED** — 22 distinct hashes per arm |
| P-C4 text is degenerate | 50% | **CONFIRMED** — 4096 `/`, 99.1% shingle share |

### P-C2 falsified: checkpoints are not the cause

`--ctx-checkpoints 0` did not suppress the latch. It moved it (task 9 vs task 3) and produced
**byte-identically shaped output** — 4096 `/`, 99.1% top-shingle share, same tail.

Latch position across three runs:

| run | `--ctx-checkpoints` | proxy | clean tasks before latch |
|---|---|---|---|
| bitdepth_iq3xxs_v5 | 32 (default) | no | 16 |
| cacheab_ctrl | 32 | yes | 2 |
| cacheab_treat | **0** | yes | 8 |

16 / 2 / 8 does not order by the flag. The trigger is stochastic and independent of context
checkpoints. **The cross-task checkpoint-reuse mechanism is withdrawn.** The `restored context
checkpoint` log line that motivated it is real but incidental — it still appears in runs that
latch and in tasks that pass.

This also retires the mechanism P-C3 was shoring up. The system prompt does drift per task
(~28 chars of ~17,660) and `f_sim_best` is genuinely 0.992-0.997, but since disabling checkpoints
changes nothing, foreign-slot selection is no longer a candidate explanation for the degeneracy.

### What survives

Only the shape of the fault: **a stochastic trigger producing persistent corrupt decode state,
cleared by a server restart.** No mechanism identified.

### Next, in order of what they gate

1. **No-proxy control** — VBR, no proxy, 14 tasks. Gates whether any of this is reportable.
   Proxied runs latched at 2 and 8; the single unproxied run latched at 16. n=1 is not enough
   to clear the proxy.
2. **`-ctk f16 -ctv f16` control** — gates *whose* bug it is. Every run so far has been on
   `-ctk vbr -ctv vbr --vbr-floor t2`. If the latch vanishes without VBR it is buun's KV path;
   if it survives it is upstream or the quantisation.

---

## Pre-registration — no-proxy control (logged before running)

**Design:** VBR exactly as before, **no proxy** (harness → `:8090` directly), fresh server,
**20 tasks** in the same order. Sized at 20 rather than 14 deliberately: the only unproxied run we
have latched at task 16, so a 14-task probe could miss the latch and produce a false exoneration
of the proxy.

Detection without the proxy relies on harness status alone — a latch shows as consecutive
`INFRA_ERROR` timeouts. That is sufficient for this question; we do not need the text again.

**P-N1: the latch occurs within 20 tasks with no proxy in the path. 70%.**
v5 latched at 16 unproxied, so the phenomenon clearly does not require the proxy; the uncertainty
is whether 20 tasks is enough given a stochastic trigger (observed latch points 2, 8, 16).
*If CONFIRMED:* the proxy is cleared and the finding is reportable.
*If FALSIFIED* (20 clean tasks unproxied): the proxy becomes a prime suspect, since proxied runs
latched at 2 and 8. That would invalidate the wire captures and make `RESULT_SLASH_DEGENERACY.md`
a finding about my own tooling rather than about the model.
