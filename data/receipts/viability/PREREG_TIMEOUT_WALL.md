# PREREG: what causes the `qwen38_fixed_grader` timeout wall?

**Written:** 2026-09-08, before running the probe. Predictions logged with confidence, scored honestly after.

## Observation to explain

At 15:12:02, immediately after `t08_execute_code_t01_math` PASSED in 26s, every subsequent task returned
INFRA_ERROR at *exactly* the timeout constant (360s / 420s, to the hundredth of a second). 12 consecutive
tasks, no recovery. `run_agent.log` shows `API call #1/10` issued and `trace.jsonl` of 0 lines — the **first**
API call never returns. The task is trivial ("Use `web_search` to find the capital of France"); det02 did it
in 45s with 62 chars of reasoning.

Server is not wedged: GPU at 98%, actively generating (`task 119000`, `n_gen` climbing past 1576).
The model is producing an enormous single response that outlives the harness timeout.

## Already ruled out

- **The toolcalls.py patch** — runs downstream of the subprocess timeout; grading never executes on these tasks.
- **A wedged or crashed server** — actively generating during analysis.
- **A stuck kernel** — `hermes_kernel_p9qkz1d4` dates to Sep 4, 0% CPU, unrelated to this run.
- **Agent/tool configuration** — `run_agent.log` setup lines byte-identical to det02: same 19 tools, same
  16 deferred behind `tool_search`, same 100k context limit, same ~5,896-token first request.
- **Server flags** — live cmdline verified from `/proc`; det02 used the same `--reasoning-effort medium
  --min-p 0`, `n_ctx_slot 32768`, `kv_unified true`, speculative decoding.

## Critical caveat on existing evidence

The pre-wall decode median (33.3 t/s) is computed **entirely from tasks that completed**, all of which ran
before 15:12. There is **no completed-request telemetry after the wall** — by construction, since every
post-wall request was killed. The single post-wall measurement is `tg_3s ≈ 19.6` on task 119000, ~40% below
the pre-wall median. Evidence is suggestive of degradation but is n=1. See AFM-34.

## Hypotheses and predictions

**H1 — Server state degradation (AFM-26).** Something in the server's state at ~2h uptime / after the
`t08_execute_code` task causes runaway generation. *Prediction: the degraded server runs away on the probe
request; a freshly restarted server answers it in <60s.* **Confidence: 60%**

**H2 — Request-shaped runaway.** These prompts reliably induce degenerate generation at IQ3_XXS regardless of
server state, and det02's passes were luck (K=1). *Prediction: both degraded and fresh servers run away.*
**Confidence: 25%**

**H3 — Transient / non-reproducible.** *Prediction: both complete normally; the wall does not reproduce.*
**Confidence: 15%**

## Probe (A/B, identical request both arms)

1. **Arm A (degraded):** before restarting, POST the exact hanging request to the live server with
   `"stream": true`. Observe 20s of tokens. Record: tokens emitted, whether text is a repetition loop,
   an unterminated thinking block, or coherent prose.
2. **Arm B (fresh):** restart llama-server with byte-identical flags. Send the same request. Same observations.

## Discriminator on the stream text

- **Literal repetition loop** → quant degeneration at IQ3_XXS (the "2-Bit Drunk" pattern).
- **Unterminated thinking block / no stop token** → chat-template or stop-token defect.
- **Coherent endless prose** → reasoning-effort injection driving length.

## In-flight discriminator (free, already running)

`t13_humaneval_micro` tasks are micro-tasks in a different family. If they PASS, the wall is task-family
specific (favours H2). If they time out too, it is a server-state transition (favours H1).

## Standing note

This is K=1 vs K=1. Per `agent-benchmark-determinism`, K=1 is an existence proof, not a rate. Twelve
contiguous failures is too many for subprocess-level variance, which is why shared **server** state is the
lead suspect — but no mechanism goes in a receipt until the A/B reproduces it.

---

# ADDENDUM (2026-09-08, post-outage): measurement salvaged from a log that no longer exists

A ~2-hour power outage killed the desktop mid-investigation. The scratchpad server logs
(`clean32k.log`, `qwen_deploy2.log`) lived in `/tmp` and are **gone** — see the `scratchpad-is-volatile`
rule, which this violates again. The numbers below were extracted before the outage and are transcribed
here because **they cannot be regenerated**. The bench `results/` and `traces/` (on `/home`) survived.

## The measurement that fixes AFM-34's survivorship bias

llama-server emits a `tg_3s` progress line every ~3s **during** generation — including for requests that
are later killed. Bucketing those by server-uptime timestamp samples the pathological requests directly,
which the completion-only `eval time` lines structurally cannot.

| run | pre-wall (<34 min uptime) | post-wall (>34 min) | ratio |
|---|---|---|---|
| `qwen38_fixed_grader` | n=273, median **38.8** t/s (p10 27.1, p90 45.0) | n=1808, median **19.7** t/s (p10 19.3, p90 **19.9**) | **1.97×** |
| `qwen38_deploy_det02` (control) | n=309, median 35.5 t/s | n=731, median 25.3 t/s | 1.40× |

Two things stand out:

1. **Both runs degraded with uptime.** det02 was not immune — it fell 1.40×. This is AFM-26 behaviour in
   both, differing in magnitude, not in kind. det02 stayed fast enough that its ~14,000-token generations
   still fit inside 360s; fixed_grader did not.
2. **The post-wall distribution has almost no variance** — p10 19.3, median 19.7, p90 19.9 across 1,808
   samples spanning ~90 minutes and many different context depths. Decode rate normally varies with
   `n_past`. A rate pinned to 19.7 ± 0.3 looks **clamped**, not merely slow.

## GPU state measured live during the degraded period

| metric | value |
|---|---|
| power | **367 W** against a **374 W** cap |
| sclk | 3038 MHz (high — *not* downclocked) |
| junction / memory / edge temp | 82 C / 86 C / 51 C |
| `throttle_status` | 49152 (nonzero) |
| `indep_throttle_status` | 3 |
| busy | 100% |

The card was burning ~98% of its power budget at full clocks while delivering **half** the tokens. That is
wasted compute, not thermal downclocking — the classic signature of speculative decoding whose drafts are
being rejected, or of work being redone.

## Evidence that did NOT survive the survivorship check

- **MTP draft acceptance:** pre-wall n=116, mean 0.661. **Post-wall: zero samples** — acceptance is logged
  only on request completion, so the killed requests report nothing. The MTP-collapse hypothesis is
  therefore *unconfirmed*, not supported. Same trap as AFM-34, caught before it became a claim.
- **VBR events:** 39 pre-wall vs 21 post-wall — fewer after the wall, which does not support a VBR-cascade story.

## Arithmetic that makes the wall make sense

Runaway generations in `fixed_grader` reached 6,600–8,500 tokens.

- at the pre-wall rate (38.8 t/s): 170–219 s → **fits** inside the 360 s timeout
- at the post-wall rate (19.7 t/s): 335–431 s → **does not fit**

So two independent conditions had to coincide: the model must emit a multi-thousand-token response, **and**
decode must have halved. det02 met the first but not the second. This reframes the wall as a *threshold*
effect rather than a new failure — which is why it appeared to switch on instantly at 15:12.

## Status of the pre-registered A/B

**Arm A (degraded server) is permanently unrecoverable** — the outage destroyed the server state that
produced the wall. The hypotheses stand as written and unscored. To test H1 vs H2 now requires
*reproducing* degradation from a cold server (sustained load until decode halves), which is a different and
slower experiment than the probe originally planned. H3 (transient) is weakened but not excluded.

**Do not score H1/H2/H3 from the salvaged data above.** It is consistent with H1 and was collected without
the controlled comparison the prereg demanded.

## Final state of the run (from surviving `results/`)

`passed=34, failed=0, infra_errors=17, task_count=61` — the run was killed by the outage at ~51/61.
The dispatcher-fix conclusion in `RESULT_DISPATCHER_FIX_LIVE.md` is unaffected: it rests on the per-task
outcome diff, which survived on disk.

---

# CORRECTION (2026-09-08, late): the "decode collapse" was a SAMPLING ARTIFACT, not server degradation

The addendum above reports decode falling **38.8 → 19.7 t/s** post-wall, with "almost no variance"
across 1,808 samples, and reads that as the server degrading. **That reading is wrong**, and the
error is the same family as AFM-34 one level up.

## What reproduced it

The `preserve_off` run on the 9070 (2026-09-08 evening) hit the identical signature — `tg_3s` at
19.89/19.87, GPU power-pegged at 340 W, full clocks, normal temps. This time the server was still
running, so the question the outage cost us this morning could actually be asked.

## The server was not degrading

Pairing every request's prompt depth against its decode rate, split early vs late in the run:

| cohort | shallow prompts (<2k tok) | deep prompts (>8k tok) |
|---|---|---|
| EARLY (first third) | 41.2 t/s (n=19) | 29.5 t/s (n=11) |
| LATE (last third) | **39.2 t/s** (n=16) | **34.2 t/s** (n=9) |

**At identical prompt depth, late decode is 1.05× early — i.e. unchanged.** Deep prompts actually got
*faster*. There is no accumulated state degradation. A restart would have "fixed" nothing.

## What the 19.7 floor actually was

Profiling the samples by cohort:

| cohort | samples | distinct tasks | completed |
|---|---|---|---|
| `tg_3s < 24` | 111 | **1** | **0/1** |
| `tg_3s > 34` | 187 | 27 | 26/27 |

**Every slow sample came from a single stuck request.** llama-server emits a progress line roughly
every 3 s during generation, so one request that runs for six minutes contributes ~120 samples while
nothing else is running. A rolling median over recent samples therefore reports *that one request's*
rate as if it were the server's.

The same arithmetic explains this morning: **1,808 post-wall samples ÷ one per 3 s ≈ 90 minutes ≈ 15
timeouts × 360 s.** The "near-zero variance at 19.7" was never a clamped server — it was a handful of
stuck generations at steady state, each sampled ~120 times.

## Also falsified: decode declining within a long generation

The obvious mechanism — a long generation slowing as its own output extends the context — does **not**
hold. Tracing `tg_3s` against `n_gen` inside single long generations:

| task 4641 (max 9,346 tok) | task 12975 (max 7,134) | task 17843 (max 6,737) |
|---|---|---|
| 41.5 → 42.9 t/s | 47.4 → 42.3 t/s | **20.1 → 20.0, flat from n_gen=100** |

The slow request was slow **from its first hundred tokens** and stayed flat. Slowness is a property
the request has from the start, not something it accumulates.

## What still stands from the addendum

- **The threshold model.** Confirmed live: 6,077 tokens took ~157 s at 43.6 t/s early and ~303 s at
  20.1 t/s later — the monitor fired `TIMEOUT RISK` on exactly that arithmetic. Long generations are
  a normal property of this workload and only become fatal when paired with a slow request.
- The GPU is power-pegged at full clocks with normal temperatures while producing half the tokens.
  That remains true and still indicates wasted compute rather than thermal throttling.

## What is now OPEN (was wrongly considered closed)

**Why are some individual requests ~2× slower from their first tokens?** MTP draft acceptance is the
leading candidate — a fully-rejected draft burns GPU on tokens that are thrown away, which matches
"full power, half the output" exactly, and the healthy-vs-slow ratio (~43 vs ~20 t/s) is close to the
measured MTP multiplier. But the evidence is **not there yet**:

- All 81 *bench* requests show acceptance 0.46–1.00. None collapsed.
- The one zero-acceptance record (0/187, mean len 1.00, 22.04 t/s) is **my own probe**, sent with
  `temperature: 0`, which the bench does not use. That is a confound in the probe, not a finding.
- The slow bench request never completed, so it printed no acceptance record at all.

**Do not write "MTP collapse causes the wall" anywhere until a probe under the bench's own sampling
reproduces zero acceptance.** That test is running.

## Standing lesson

Three times today a rolling statistic was computed over a population defined by the very outcome
under investigation — completion-only `eval time` lines (survivorship), and now progress-line
medians dominated by whichever request happens to be stuck. **Before believing an aggregate, ask
which requests contributed to it and whether that set is independent of what you are measuring.**
