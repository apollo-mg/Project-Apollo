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

---

## Pre-registration — proxied repeat (logged before running)

**Question:** is the proxy causing the latch, or were the two proxied arms unlucky?

**Design:** byte-identical to `noproxy_ctl` (same 20 tasks, same order, VBR, fresh server,
`--timeout-overhead 300`) with **one difference: the harness points at the proxy**.
Timeout deliberately left at 300 rather than shortened, to keep the comparison exact even though
latch detection alone would tolerate a shorter one.

**P-P1: the proxied repeat latches within 20 tasks. 70%.**
Proxied 2/2 so far (tasks 2 and 8); unproxied 1/2 (v5 at 16, `noproxy_ctl` clean through 20).
*CONFIRMED:* 3/3 proxied vs 0/2 unproxied — the proxy is causing it, `RESULT_SLASH_DEGENERACY.md`
becomes a finding about my tooling, and the probe matrix is invalid as designed.
*FALSIFIED:* the two earlier arms were unlucky, the latch is a genuine stochastic model/server
fault, and the `/` capture stands.

**Pre-committed:** either way this gets written up. A clean proxied run does **not** license
quietly restoring the original claim — it moves the proxy from "leading suspect" to "not excluded",
because n=3 with a stochastic trigger is still thin.

### SCORING — P-P1 CONFIRMED (2026-09-09 22:5x, stopped early at 13/20)

**Latched at task 3 — the same position as `cacheab_ctrl`.** 2 PASS then 11 consecutive
INFRA_ERROR at 360 s each. Stopped at 13/20: the verdict was established and the remaining
7 tasks were 42 minutes of GPU for no information.

| condition | runs | latch position |
|---|---|---|
| **proxied** | **3/3 latched** | 2, 8, **2** |
| unproxied | 1/2 latched | 16, never-in-20 |

Wire capture: 24 of 28 responses >90% `/`, first at +239 s. Identical signature.

**Verdict: `tools/llmproxy` in the request path causes the latch.** The instrumentation built to
observe the failure was inducing it. The pre-registered consequence applies —
`RESULT_SLASH_DEGENERACY.md` is a finding about the proxy interaction, not about the model, and
the probe matrix is invalid as designed (it assumed a latched server was model state).

### The claim this does NOT collapse to

The proxy **cannot manufacture slashes**. It only reads `delta.content` out of the SSE the server
sent, and a corrupted parse would yield replacement characters, not 4096 clean `/`. So the server
really did emit them. The correct statement is:

> **Putting this proxy in the path causes llama-server (VBR, IQ3_XXS, gfx1201) to emit degenerate
> `/` output and stay degenerate until restart.**

That is an interaction, not an artefact, and it is still a server-side fault — just one with a
trigger we now partly control, which makes it far more debuggable than a stochastic latch.

### Leading mechanism (untested): consumer backpressure

`llm_proxy.py` awaits `out.write(chunk)` for **every** chunk before reading the next, so each token
costs a Python round-trip and a second socket hop. The server therefore sees a materially slower
consumer than a direct client. VBR re-tiers on timing, and the v5/ctrl logs are full of
`VBR_RETIER_PREFLIGHT` and `vbr reset` events.

**Decisive test:** decouple the two halves — drain upstream as fast as it arrives into a queue,
write downstream from a separate task. Latch disappears → backpressure confirmed, and
"a slow stream consumer corrupts decode" is a genuine, reportable server bug that would affect any
slow client or network. Latch persists → look at connection churn (a fresh `ClientSession`
per request means no keep-alive) next.

**Unproxied latch is still unexplained.** v5 latched at 16 with no proxy. Whatever the proxy
aggravates, something else can trigger it too — and we still have never seen the text of an
unproxied runaway.

---

## Pre-registration — decoupled-drain test (logged before running)

### Mechanism being tested

`llm_proxy.py --drain-mode inline` awaits the downstream write for every chunk, so the server's
socket sink drains at Python speed across an extra hop. When that sink stalls, llama.cpp's
generation loop stalls between tokens.

**The proposed corruption path:** this build publishes idle dynamic-VBR slots as prompt-cache
artifacts — the server log carries
`publish_idle: VBR_IDLE_CAPTURE manifests=1 published=1 ... transfers=32` and repeated
`VBR_RETIER_PREFLIGHT owner=server_checkpoint_restore`. If a slot that is stalled *mid-generation*
is classified idle and its KV is re-tiered (re-quantised in place), the in-flight decode continues
against KV that changed underneath it. That would produce exactly what we see:

- degenerate output, because the attended KV no longer means what the logits were built from
- **latching**, because the KV stays re-tiered
- cleared by restart, because that rebuilds the cache
- **rate proportional to how slow the consumer is** — 3/3 with the inline proxy, 1/2 direct
- and it explains the unproxied v5 latch at task 16: a direct client can stall too, just rarely

This is a hypothesis. It has not been tested and no code path has been traced end-to-end.

### Design

Identical to the proxied repeat — same 20 tasks, VBR, fresh server, `--timeout-overhead 300` —
with `--drain-mode decoupled`: upstream is drained at full speed into a queue and a separate task
writes downstream, so the client can never backpressure the server.

Client-disconnect propagation was added and verified first (killed client at 0.8 s of a 2.0 s
stream → `aborted` at 17 chunks, upstream closed). Without it the server would keep generating for
a dead client and still be busy when the next task starts — a worse confound than the one being fixed.

### Predictions

**P-D1: the decoupled proxy does not latch within 20 tasks. 55%.**
Barely above a coin flip on purpose. Inline latched 3/3 at positions 2, 8, 2, so the trigger is
strongly proxy-linked, but "proxy-linked" does not confirm *backpressure* specifically —
connection churn (a fresh `ClientSession`, hence no keep-alive, per request) is untested and would
survive this change.
*CONFIRMED:* backpressure is the trigger, "a slow stream consumer corrupts decode on VBR" becomes a
real and reportable server bug, and the proxy is rehabilitated as an observation tool.
*FALSIFIED:* backpressure is not it; connection churn is next, then header/framing differences.

**P-D2: if P-D1 confirms, `--no-vbr-prompt-cache` with the INLINE proxy also suppresses the latch. 50%.**
Logged now so it cannot be invented later. This is the direct test of the idle-capture path above:
if disabling idle-slot publication fixes an inline run, the mechanism is identified rather than
merely correlated.

---

## Pre-registration — P-D2 overnight, WITH positive control (logged before running)

**Arm A (the test): inline proxy + `--no-vbr-prompt-cache`.**
**Arm B (positive control): inline proxy, server flags unchanged.**

Arm B exists because `llm_proxy.py` was edited *after* the three inline latches (decoupled mode
plus disconnect propagation were added). Inline should be untouched — `q is None` takes the old
path — but "should be" is not evidence. Without Arm B, a clean Arm A is ambiguous between
"the flag fixed it" and "my edit silently changed inline behaviour", and I would have no way to
tell those apart tomorrow.

**P-D2 (50%, logged before the decoupled result was known): Arm A does not latch within 20 tasks.**

**P-D3 (85%): Arm B latches within 20 tasks**, reproducing the 3/3 inline behaviour on the current
binary. *If FALSIFIED, Arm A is uninterpretable* — it would mean inline no longer latches at all
and both arms are measuring nothing.

Joint reading:

| Arm A (no-vbr-prompt-cache) | Arm B (control) | conclusion |
|---|---|---|
| clean | latches | **idle-slot VBR capture is the mechanism** |
| latches | latches | not idle capture; backpressure corrupts by another path |
| clean | clean | the proxy edit changed inline behaviour; both void, re-test needed |
| latches | clean | incoherent; suspect drift, re-run everything |

Order: A then B, so the approved test lands first if the night is cut short.
