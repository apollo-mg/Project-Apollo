# RESULT: the timeout wall is content-dependent MTP acceptance, not server degradation

**Date:** 2026-09-08 · **Hardware:** RX 9070 XT · **Build:** buun `3823c9eb6`
**Model:** `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf`, `-c 32768 -np 1 --spec-type draft-mtp`, VBR KV
**Run:** `qwen38_preserve_off` (hermesbench, 61 tasks) — investigated live, mid-run

## The claim this replaces

`PREREG_TIMEOUT_WALL.md` recorded decode "collapsing" 38.8 → 19.7 t/s and read it as the server
degrading with uptime (AFM-26). **That was wrong on both counts.** The signature reproduced tonight
with the server still running, which allowed the question to be asked directly instead of inferred.

## 1. The server does not degrade

Pairing each request's prompt depth with its decode rate, early vs late:

| cohort | shallow (<2k tok) | deep (>8k tok) |
|---|---|---|
| first third | 41.2 t/s (n=19) | 29.5 t/s (n=11) |
| last third | **39.2 t/s** (n=16) | **34.2 t/s** (n=9) |

At matched depth, late is **1.05×** early. Deep prompts got faster. By time quartile, mean decode is
37.8 / 35.0 / 37.4 / **35.5** t/s — flat across 39 minutes of uptime. **A restart fixes nothing.**

## 2. The "19.7 floor" was one stuck request

| cohort | samples | distinct tasks | completed |
|---|---|---|---|
| `tg_3s < 24` | 111 | **1** | **0/1** |
| `tg_3s > 34` | 187 | 27 | 26/27 |

llama-server emits a progress line every ~3 s during generation. One request stuck for six minutes
contributes ~120 samples while nothing else runs, so a rolling median reports **that request's** rate
as the server's. This morning: 1,808 post-wall samples ÷ one per 3 s ≈ 90 min ≈ 15 timeouts × 360 s.

## 3. Decode does NOT decay within a long generation

| task 4641 (max 9,346 tok) | task 12975 (max 7,134) | task 17843 (max 6,737) |
|---|---|---|
| 41.5 → 42.9 t/s | 47.4 → 42.3 t/s | **20.1 → 20.0, flat from n_gen=100** |

The slow request was slow from its first hundred tokens. Slowness is a property it *has*, not one it
accumulates.

## 4. Root cause: MTP draft acceptance, and it is content-dependent

Splitting the same 83 requests by acceptance instead of by time:

| | mean decode |
|---|---|
| acceptance < 0.45 | **23.8 t/s** (n=4) |
| acceptance ≥ 0.65 | **38.9 t/s** (n=43) |
| **ratio** | **1.63×** |

Pearson r(acceptance, decode) = **0.384** (n=83).

**1.63× is the independently measured MTP multiplier** for this class of model (1.58–1.67× on the
DavidAU 40B tonight; 1.40× on Qwen3.8-27B earlier). When the draft is accepted you get the
speculative speedup; when it is rejected you fall back to the no-speculation baseline **and still pay
for generating the rejected drafts** — which is precisely why the GPU sits power-pegged at full
clocks and normal temperatures while producing half the tokens.

### Reproduced deliberately, twice

An identical 23-token prompt ("Count from 1 to 40, one per line"), 96 output tokens:

| probe | sampling | decode | acceptance |
|---|---|---|---|
| 1 | `temperature: 0` | 22.04 t/s | **0.000** (0/187), mean len 1.00 |
| 2 | server default | 22.05 t/s | **0.000** (0/187), mean len 1.00 |

Identical to two decimal places. **Sampling is not the cause** — the first probe's `temperature: 0`
was a confound I introduced and then eliminated. Zero acceptance is a property of the *content*, and
it reproduces exactly on demand. Note the content here is trivially predictable to a human, which
makes it a useful counterexample: draft-head acceptance is not intuitively related to how "easy" the
text looks.

## Why this produces a timeout wall

The harness kills an agent subprocess on **wall clock** (360 s). Generation length is a constant of
the workload — 6–9k-token turns are normal here and appear throughout the run:

| generation | at 43.6 t/s (draft accepted) | at 20.1 t/s (draft rejected) |
|---|---|---|
| 6,077 tok | 139 s — fits | **303 s — at the cliff** |
| 6,865 tok | 157 s — fits | **342 s — at the cliff** |
| 7,700 tok | 177 s — fits | **383 s — dead** |

So the wall needs **two** coincident conditions: a long generation *and* a request whose content the
draft head predicts poorly. Neither alone is fatal, which is why it appeared to switch on abruptly
and why it is not reproducible by re-running a single task.

## Consequences

1. **MTP raises the mean and widens the variance.** It is a ~1.6× average win with a heavy tail of
   requests that get nothing. Under a wall-clock timeout, the tail is what determines the score.
2. **Wall-clock timeouts convert throughput variance into scored failures.** This is the strongest
   argument yet for token-budget rather than wall-clock caps (`RESULT_CORPUS_HARDENING_GOLDEN.md`
   item 2). A model is currently penalised for the draft head's luck on a given prompt.
3. **Do not restart servers to "fix" this.** It is not uptime degradation. The restart ritual from
   AFM-26 is still right for other reasons, but it does not address this.
4. **Any A/B that compares INFRA counts across arms is measuring draft-acceptance luck** unless
   generation lengths and acceptance rates are reported alongside.

## Limits

- The low-acceptance bucket is **n=4** among bench requests. The mechanism is corroborated by two
  deliberately reproduced probes and by the ratio matching the independently measured MTP multiplier,
  but the *rate* at which content triggers it is not established.
- Not tested: whether the same content is reliably low-acceptance across server restarts, or whether
  a no-MTP arm eliminates the tail entirely (predicted: uniform ~24 t/s, no fast path, no slow
  outliers). That is the obvious next experiment and it is cheap.
- r = 0.384 is a moderate correlation, not a clean fit — acceptance is one driver of decode, not the
  only one.

## Method note

Three separate times today an aggregate was computed over a population defined by the outcome under
investigation: completion-only `eval time` lines (survivorship), progress-line medians dominated by a
stuck request, and an every-Nth sample of acceptance records that skipped the declining tail.
**Before believing an aggregate, ask which requests contributed and whether that set is independent
of what is being measured.** See AFM-34.

---

# CORRECTION (same night, ~1 hour later): section 1 and section 4's conclusion are WRONG

This receipt concluded (1) the server does not degrade and (4) low draft acceptance is
**content-dependent**. Both conclusions rest on the same defect, and it is the *third* instance of
the same defect in one day.

## The defect

Section 1 compared decode "early vs late" among requests **that completed**. After the wall begins,
**nothing completes**. So every request in the "late" cohort was drawn from *before* the transition.
The comparison could not have detected degradation — its sample excluded, by construction, every
request affected by the thing being measured.

Confirmed directly: the only two completed requests after minute 27 are **my own diagnostic probes**.
Zero bench requests completed post-wall.

Section 4's "content-dependent" conclusion has the same root. The two probes that produced identical
`0.000` acceptance were **both taken after the collapse**, at minutes 32.9 and 38.9. They matched to
two decimal places because the server was in the same state, not because the prompt content was
special. I explicitly ruled out sampling as a confound and then failed to check *time*.

## What the data actually shows: MTP acceptance decays with server uptime

Every acceptance record, in time order:

| minute | acceptance | decode |
|---|---|---|
| 19.5 – 20.8 | 0.578 – 0.875 | 28 – 47 t/s |
| 24.2 | 0.517 | 39.8 t/s |
| 25.1 | **0.312** | 25.5 t/s |
| 32.9 (probe) | **0.000** | 22.0 t/s |
| 38.9 (probe) | **0.000** | 22.1 t/s |

Monotonic decline to zero. Last non-zero acceptance: **minute 25.1**. The wall began at **~minute 27**
(22:09 wall clock), in the gap. Every subsequent task timed out at exactly 360.0 s.

## Corrected causal chain

1. MTP draft acceptance **decays with server uptime** and reaches zero at ~25–30 minutes.
2. Decode falls to the no-speculation baseline (~22 t/s) while the GPU **still pays to generate
   rejected drafts** — which is why it sits power-pegged at full clocks and normal temperature
   producing half the tokens.
3. Generations of 6–9k tokens are a normal property of this workload.
4. At ~20 t/s those exceed the harness's 360 s wall-clock cap, so **every** subsequent task fails.

The threshold model from `PREREG_TIMEOUT_WALL.md` stands. What was wrong was attributing the slow
half to per-request content rather than to server state. **AFM-26 was right after all.**

## Also falsified tonight

`t08_execute_code_t01_math` **did not recover** (INFRA_ERROR, 360.0 s). The t06/t07 clustering was
an artifact of task ordering, not a family effect. So:

- **P2 (preserve_thinking effect concentrates in specific families): FALSIFIED.**
- The hypothesis that preserve_thinking OFF breaks multi-step stateful tasks: **FALSIFIED.** It was
  attractive, matched Mark's prior, and was wrong. It survived only as long as the wall happened to
  overlap two stateful families.

## Consequence for benchmarking on this build

**A 61-task agent run cannot complete with MTP enabled on buun `3823c9eb6`.** The draft head degrades
to zero before the corpus finishes. Options: disable MTP for long runs (uniform ~24 t/s, no fast
path but no collapse), restart the server periodically mid-run, or cap by token budget so a slow
request costs tokens rather than a scored failure.

**Every INFRA-count comparison across arms in this campaign is confounded by where the arm sat
relative to the collapse.** The `preserve_off` arm's 9 infra vs det02's 8 measures uptime position,
not preserve_thinking.

## Pending

Restart test running: a freshly loaded server, identical probe. Prediction (logged before the
result): acceptance returns to ~0.6–0.9 and decode to ~40 t/s. If it does not, the decay is not
uptime-linked and this correction needs correcting in turn.

---

# RESTART TEST — CONFIRMED. Uptime-linked MTP degradation, fully reversible.

**Prediction logged before running:** acceptance returns to ~0.6–0.9, decode to ~40 t/s.
**Result: acceptance 0.93–0.97, decode ~60 t/s.** Confirmed, and stronger than predicted.

Identical prompt, identical flags, identical binary — the only variable is server uptime:

| condition | decode | draft acceptance | mean draft len |
|---|---|---|---|
| old server, min 32.9 | 22.04 t/s | **0.000** (0/187) | 1.00 |
| old server, min 38.9 | 22.05 t/s | **0.000** (0/187) | 1.00 |
| **fresh server, probe 1** | **59.62 t/s** | **0.933** (70/75) | 3.80 |
| **fresh server, probe 2** | **61.63 t/s** | **0.972** (70/72) | 3.92 |
| **fresh server, probe 3** | **60.65 t/s** | **0.933** (70/75) | 3.80 |

**2.7× decode restored by a restart alone.** Note `mean len` collapsing to 1.00 in the degraded state:
the draft head stops proposing multi-token continuations entirely, so every step pays draft cost for
at most one speculative token, all of which are rejected.

## Final causal chain

1. MTP draft acceptance **decays with server uptime**, reaching zero at ~25–30 min under load
   (0.58–0.88 → 0.517 → 0.312 → 0.000).
2. Decode drops to ~22 t/s — worse than no speculation, because rejected drafts are still generated.
   This is why the GPU sits power-pegged at full clocks and normal temperature at half throughput.
3. 6–9k-token generations are normal for this workload.
4. At ~20 t/s they exceed the harness's 360 s wall-clock cap → every subsequent task fails →
   the contiguous wall.
5. **A restart fully reverses it.**

## Actions

- **Restart llama-server between benchmark legs** — already the rule (AFM-26); this gives it a
  precise mechanism and a measurable signature (`draft acceptance`, `mean len`).
- **A >25-minute agent run cannot complete with MTP on buun `3823c9eb6`.** Either disable MTP for
  long runs, restart mid-run, or cap by token budget so a slow request costs tokens not a scored
  failure.
- **Monitor `draft acceptance` and `mean len`, not decode rate.** Acceptance is the leading
  indicator; decode is downstream, and decode aggregates are corrupted by whichever request is stuck.
- **Report upstream to buun.** A draft head degrading to zero acceptance over ~25 minutes of
  continuous serving, fully reset by restart, is a concrete and reproducible defect. Repro: sustained
  agent load, watch `draft acceptance` per request; contrast a fresh server on the identical prompt.

## Corrections this receipt went through, recorded deliberately

1. "Decode collapsed 38.8 → 19.7, server degrading" — **wrong** (rolling median dominated by one
   stuck request).
2. "Server does not degrade; low acceptance is content-dependent" — **wrong** (both comparisons
   drawn from completed-only populations that excluded every post-wall request; both probes taken
   after the collapse).
3. "preserve_thinking OFF breaks multi-step stateful tasks" — **wrong** (t08 did not recover; the
   t06/t07 clustering was task ordering).

All three were survivorship in different clothes: an aggregate computed over a population defined by
the outcome under investigation. The correct instinct each time would have been the same one
question — **which requests contributed to this number, and is that set independent of what I am
measuring?**

---

# MECHANISM IDENTIFIED: VBR budget clamp at `--vbr-floor` kills MTP draft acceptance

**Mark's call ("draft acceptance drops if they are comparing the wrong things — it's gotta be cache")
is correct, and the log names the transition.**

## The trigger

```
24.2  slot release: task 12975 | stop processing: n_tokens = 21481, truncated = 0
24.2  VBR_RETIER_PREFLIGHT owner=server_checkpoint_restore result=fits
        watermark=21504 needed=199360512
24.4  W prepare_with_slots: VBR budget 4433.27 MiB exceeded with the degrade order
        CLAMPED AT THE --vbr-floor (projected 132.12 MiB at 14848 cells)
```

A 21,481-token request drove the retier watermark to **21,504 cells** — against 14,336–19,200 for
every prior request. VBR could not fit inside its 4,433 MiB budget **even after degrading to the
floor tier**, so the degrade order clamped at `--vbr-floor t2` (2.25 bits/value) with nowhere further
to go.

## Perfect separation

| | n | mean acceptance | min |
|---|---|---|---|
| **before** the first clamp (min 24.4) | **80** | 0.682 | **0.444** |
| **after** | 3 | 0.104 | 0.000 |

Not one of the 80 pre-clamp requests fell below **0.444**. Every post-clamp value is **≤ 0.312**.
No overlap. Subsequent clamps at min 32.9, 38.9, 65.8.

## Why this kills speculation

Speculative decoding accepts a draft token only when the target model's verification agrees. Once the
KV is pinned at the floor tier, the target verifies against heavily-quantised cache while the draft
proposes from its own view — the two sides are computing from materially different state. Every
proposal is rejected (`mean len` → 1.00), and the GPU still pays to generate the rejected drafts.
That is the "full power, full clocks, half the tokens" signature exactly.

## Ruled out along the way

- **`CHECKPOINT_ATTN_ONLY_TRIM ... target=1 draft=0`** — looked like a smoking gun (draft context not
  restored alongside target), but it fires **47 times from minute 0.29**, always `draft=0`, and
  acceptance stayed healthy for 80 requests afterwards. Constant, not causal. Called prematurely and
  retracted within minutes.
- **`vbr reset ... 0/14,2xx prompt tokens reusable`** — also constant from min 0.6. The prompt cache
  is discarded on nearly every request throughout, before and after the collapse.

## Predictions for the fix (logged before testing)

- **P-A: raising `--vbr-floor` above t2 prevents the collapse.** 70%. More headroom above the floor
  means the degrade order never clamps.
- **P-B: increasing `--vbr-vram` beyond 4,433 MiB prevents it.** 65%. Same mechanism, attacked from
  the budget side.
- **P-C: `-ctk f16 -ctv f16` (no VBR) shows no acceptance decay at all.** 80%. If VBR is the cause,
  removing it removes the effect — the cleanest discriminator.
- **P-D: the collapse is triggered by request SIZE, not elapsed time.** 75%. A single oversized
  request (>21k tokens) causes it; a run of only small requests should never collapse regardless of
  uptime. This reframes it from "uptime degradation" to "one bad request poisons the slot."

**P-D matters most.** If true, "restart between legs" is the wrong mitigation and "cap per-request
context, or raise the floor" is the right one.

## Report to buun

Concrete, reproducible, with a log signature:

> Under `-ctk vbr -ctv vbr --vbr-floor t2 --vbr-vram auto` with `--spec-type draft-mtp`, once
> `prepare_with_slots` reports *"VBR budget … exceeded with the degrade order clamped at the
> --vbr-floor"*, MTP draft acceptance drops to 0.000 and `mean len` to 1.00 for all subsequent
> requests on that slot. Decode falls ~2.7× (60 → 22 t/s on an identical prompt). A server restart
> fully restores acceptance to 0.93–0.97. 80 requests before the clamp never fell below 0.444
> acceptance; every request after was ≤ 0.312.

Build: buun `3823c9eb6`, RX 9070 XT / ROCm, `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp`, `-c 32768 -np 1`.
Note this build **predates** `a56eeef5`.

---

# P-D FALSIFIED — the driver is accumulated context checkpoints, not request size or uptime

**P-D predicted (75%):** a single oversized request (>21k tokens) triggers the collapse.
**Result: it does not.**

| | checkpoints created | watermark reached | acceptance |
|---|---|---|---|
| fresh server + one 20,901-token request | **4** | **256** | 0.972 → **0.939** (held) |
| the collapsed agent run | **120** | **21,504** | 0.68 → **0.000** |

KV budget was effectively identical (4,441 vs 4,433 MiB). A single large request on a fresh server
does not move the watermark at all.

**First attempt at this test was INVALID and nearly reported as a falsification.** The payload was
estimated at ~20k tokens by character count but actually tokenised to **138,778**, was rejected with
*"exceeds the available context size (32768 tokens)"*, and never ran — while the unchanged acceptance
looked exactly like a clean negative result. v2 sized the payload by binary search against the
server's own `/tokenize` endpoint (measured: 20,901 tokens). **Estimate character-to-token ratios at
your peril; the server will tell you if you ask it.**

## Refined mechanism

The `VBR_RETIER_PREFLIGHT owner=server_checkpoint_restore` watermark tracks KV state held by the
**context-checkpoint** machinery. Multi-turn agent conversations create checkpoints (`created context
checkpoint N of 32`); they accumulate across requests; the watermark climbs; eventually the VBR
budget cannot be met even at `--vbr-floor`, the degrade order clamps, and MTP draft acceptance goes
to zero.

This explains every observation:

- **why ~25 minutes of *agent* load specifically** — it takes many multi-turn conversations to
  accumulate enough checkpoints
- **why a single big request cannot reproduce it** — one request creates ~1 checkpoint
- **why a restart fully fixes it** — checkpoints are cleared
- **why the wall hit at different task indices** in two runs — it depends on conversation shape, not
  clock time

Mark's original call stands and is now specific: **it is cache — the context-checkpoint cache.**

## Available knobs (buun/llama.cpp flags, unverified)

| flag | default | relevance |
|---|---|---|
| `-ctxcp, --ctx-checkpoints N` | **32** | max checkpoints per slot — the direct lever |
| `-cms, --checkpoint-min-step N` | 8192 | minimum token spacing between checkpoints |
| `--vbr-reclaim-floor BPV` | — | *"clear idle slots' KV caches before a degrade"* — purpose-built relief |
| `--vbr-reset-keep-frac FRAC` | — | governs reuse under degrade |
| `--vbr-anchor-cache-mib N` | 0 | quality-anchor cache |

## Next experiment (single variable, ~25 min to the trigger point)

Re-run the same agent load with **`--ctx-checkpoints 8`**, everything else identical.

- **P-E: acceptance survives past the point where the baseline collapsed.** 65%. If checkpoint
  accumulation drives the watermark, capping checkpoints should prevent the clamp.
- Secondary: `--vbr-reclaim-floor` set so idle slots are reclaimed before degrading.

**This is the route to "VBR working well" rather than "VBR disabled."** VBR's premise — spend bits
where they matter instead of uniformly — is sound, and nothing here contradicts it. The defect is an
interaction between checkpoint accumulation and the floor clamp, and it appears to have configuration
remedies that do not require giving up variable-rate KV.

## Corrected repro for buun

Not "send a big request" and not "wait 25 minutes". It is:

> Sustained **multi-turn** load (an agent benchmark) against `-ctk vbr -ctv vbr --vbr-floor t2
> --vbr-vram auto --spec-type draft-mtp -c 32768 -np 1`. Watch `created context checkpoint N of 32`
> accumulate and the `VBR_RETIER_PREFLIGHT ... watermark=` value climb. When `prepare_with_slots`
> reports *"VBR budget … exceeded with the degrade order clamped at the --vbr-floor"*, MTP draft
> acceptance drops to 0.000 and `mean len` to 1.00 for every subsequent request on that slot; decode
> falls ~2.7× (60 → 22 t/s on an identical prompt). A restart restores acceptance to 0.93–0.97.
> 80 requests before the clamp never fell below 0.444; every request after was ≤ 0.312.
> A single 20,901-token request on a fresh server does **not** reproduce it (watermark stays at 256).
