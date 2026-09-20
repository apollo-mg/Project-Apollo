# Argus corpus v2 — judgement under underspecification, measured in spec

**Status: DESIGN. Not yet prereg'd — predictions section must be filled and committed before any
arm runs.** Supersedes `CORPUS_DESIGN_v1.md` for measurement purposes; v1's mitigation-log schema
is retained.

## Why v1 has to change

v1 fixed v0's ceiling/floor problem in design but not in outcome. `RESULT_PANEL.md`:

| partition | n |
|---|---:|
| all arms succeed | 8 |
| all arms fail | 5 |
| **discriminating** | **2** |

**Effective N = 2 out of 15.** The entire 67/57/53 spread was two items. And v1's keep-criterion
("1-4 clean of 5") turned out to be **inapplicable at temp 0**, where every item is 0/5 or 5/5.
Difficulty could only be discovered *after* running every arm — the chicken-and-egg that produced
13 dead items.

The two live items shared a theme: `rent-amount` (assert no information without looking) and
`mark-read-all` (act without establishing scope). **Both punish answering without checking.** That
is the axis v2 is built on.

## The claim under test

> **Does quantization degrade judgement before it degrades knowledge?**

Everyone benchmarks quantization against knowledge and reasoning accuracy. Nobody has asked
whether the *first* casualty is the disposition to check before acting. Both outcomes publish:

- **Judgement goes first** → "Q4 is indistinguishable from fp16" is measuring the wrong thing, and
  agent deployers are shipping models that answer fine and stop asking.
- **Judgement tracks KLD** → quantization is boring in a useful way, and "use the KLD curve" becomes
  defensible advice with evidence behind it.

The claim is **differential** and **within-model** (same weights, different bitrates), so it is
immune to leaderboard churn and to baseline drift.

## Design: graded families, not independent items

**6 families x 5 rungs = 30 items.** Each family is one scenario shape written at five levels of
underspecification, rung 1 unambiguous through rung 5 severely underspecified.

**The measurement is not a pass rate. It is the rung at which the model stops checking.**

This converts a binary instrument that saturates into an ordinal one that cannot. Difficulty
becomes a *designed parameter* rather than an emergent property discovered too late. Every arm
yields a threshold; thresholds differ continuously; effective N is fixed by construction.

Rung construction rule (from v1, still correct): **discoverable, not signposted.** A rung is
resolvable with one extra step the model has to think to take.

## Instrument configuration — PINNED

**Sampling: the model card, exactly.** Qwen3.8-27B thinking mode (default):

```
temperature 1.0   top_p 0.95   top_k 20   min_p 0.0
presence_penalty 0.0   repetition_penalty 1.0
```

`profiles.yaml` is **STALE** on this (it carries the Qwen3.6-era 0.6/0.95/20). Pin from the card
here; do not reference the yaml.

Running the documented recipe is a deliberate rhetorical choice — "we ran it as specified" — and
it is also the more valid one. Temp 0 takes the argmax, so a narrow top-1/top-2 margin flips a
discrete token under quantization noise; at temp 1.0 the same perturbation shifts a distribution
instead. **Temp 0 is the sampling regime that maximally amplifies quantization damage**, which
would contaminate the judgement axis with plain fidelity damage and destroy the differential.

(Note: the card carries **no** explicit warning against greedy decoding. The argument above is
mechanistic, not documented. Do not cite the card for it.)

**Serving configuration - PINNED, and every one of these is a comparison-breaker if it drifts.**

| setting | value | why |
|---|---|---|
| `preserve_thinking` | **default (ON)** | Stock 3.8 line 116: `preserve_thinking is undefined or ... is true`. buun's 3.6 template defaults it to FALSE -- same knob, inverted default, so a 3.6-vs-3.8 comparison would silently compare configs. Run as shipped. |
| `auto_disable_thinking_with_tools` | **not applicable** | Does not exist in the stock 3.8 template; it is a buun 3.6 invention. Nothing upstream disables thinking when tools are present, so the effort axis is safe by absence. |
| split mode | **`-sm tensor`, PROVISIONAL (speed grounds only)** | Determinism under `-sm tensor` is UNESTABLISHED -- the 15/15 receipt was taken at layer split and does not transfer, and tensor parallelism adds an all-reduce per layer, a new reduction-order surface. This is the ONLY objection: `-sm tensor` is measured at **>1.6x on this fleet** for dense models and is worth reclaiming. See the gate below. (An earlier draft cited the sm_60 all-reduce / NCCL note here as evidence the fast path was unavailable. That note concerns a different code path; the measured 1.6x refutes it and the claim is withdrawn.) |
| MTP / spec decode | **OFF -- now REQUIRED, not preferred** | Originally chosen on deployment-realism and arm-dependent-speed grounds. **Measured 2026-09-20: with MTP ON and the prompt cache warm, the same seed does not reproduce** -- bistable under `-sm tensor` (2 distinct outputs), worse under `-sm layer` (6 distinct). Paired seeds would be fiction. With MTP OFF the warm-cache path was byte-identical 9/9. See `data/receipts/argus-v2/RESULT_PROMPT_CACHE_BISTABILITY.md`. |
| KV codec | **constant across arms** | Not the variable under test. VBR is likely required to reach the context target on a 32 GB partition; pass KV flags explicitly (buun defaults to VBR silently) and verify from the server log. |

**Note on `preserve_thinking`:** it trades context headroom for not re-prefilling -- prior reasoning
stays in the prompt, but append-only, so the cached prefix survives. Dropping it would rewrite
history each turn and invalidate the cache. Consequences: (a) the token cap must cover PEAK
CONTEXT, not just generated tokens, which is exactly what `ctx_used_peak` now measures;
(b) the `xhigh` arm compounds, since extra reasoning is carried into every later turn;
(c) it is a third candidate explanation for the observed runaway, independent of temp 0 and the
14k ceiling -- more thinking, more context, more to attend to. **Baseline should check that the
prefix cache actually holds under VBR**; if eviction breaks reuse you keep the context cost and
lose the compensating benefit, visible as wall-clock per turn rising faster than context does.

**SUPERSEDED IN PART, same day.** That gate ran with **MTP ON and the cache cold**, and both
conditions turn out to matter. With MTP on and the cache WARM the same config is bistable, so the
gate's pass was conditional on a state the campaign will not be in. The split-mode question is
nonetheless **settled in tensor's favour**: the defect appears under `-sm layer` too (and worse),
so it is not tensor-parallel specific and does not argue against using it.

**The determinism requirement is now met by turning MTP off, not by choosing a split mode.**
Measured with MTP off, `-sm tensor`, cache warm (`cached_tokens: 30` on 8 of 9): **9 of 9
byte-identical, including the cold first request.** n=9 on one config is encouraging, not a gate --
re-run properly under campaign conditions before relying on it.

**A welcome consequence: the `preserve_thinking` collision dissolves.** This document previously
warned that restoring determinism would require `cache_prompt: false`, which would have removed
exactly the cache reuse that justifies `preserve_thinking`'s context growth, making re-prefill
quadratic in turn count. **That is no longer necessary.** With MTP off the cache can stay on, the
prefix stays reusable, and `preserve_thinking` keeps its compensation. `cache_prompt: false`
drops from a requirement to a fallback.

**Unchanged and still mandatory: record `cached_tokens` with every determinism claim.** A run that
lands in a non-caching window looks clean and proves nothing about the warm path -- which is
precisely how the gate below passed.

**GATE RESULT 2026-09-20: `-sm tensor` PASSED on `.73`.** 24 consecutive byte-identical
generations under seeded card sampling; only the first request after model load differed.
`cached_tokens` was 0 throughout, so prefix caching is not the explanation. Full workings:
`data/receipts/argus-v2/RESULT_TENSOR_SPLIT_DETERMINISM.md`.

**Consequent rule, now mandatory for every leg: DISCARD ONE WARMUP REQUEST after each model
load.** Restarting the server before a leg is necessary but not sufficient -- the first request
after the restart is itself unreliable. At K=2 this gate would have read 1-of-2 differing and
thrown away a 1.6x speedup on a warmup artifact.

**Still required before the campaign: the same gate on `.194`, under CAMPAIGN conditions.** The
`.73` pass does not transfer (a fail would have). Three things were untested there and all three
are campaign-relevant: multi-turn with tools, thinking ON with `preserve_thinking`, and above all
**prefix-cache reuse** -- `cached_tokens` was 0 for all 25 requests, so that path was never
exercised and it is the likeliest place for this result not to hold. Fail -> `-sm layer`, accept
the ~11 h.

**Original gate rationale, retained.** A 1.6x speedup across a ~30 h
campaign is ~11 h saved, against roughly an hour to test for it. Protocol: the P-A0 analogue at
**K=15**, not K=2 -- reduction-order nondeterminism from timing-dependent reductions is FLAKY
rather than consistently broken, so "reproduced twice" is weak evidence and "no failure in 15"
is what the original determinism receipt earned. If it reproduces byte-identically at K=15 under
card sampling with a fixed seed, run the campaign on `-sm tensor` and bank the speedup. If it does
not, `-sm layer` and the cost is accepted. **Decide by measurement, not by caution.**

**Open question, not on this campaign's path:** `-sm tensor` gives >1.6x on dense models but
little on the newer big MoE models, and that is unexplained. A plausible mechanism is that
tensor-parallel dense matmuls amortise one all-reduce over a large amount of compute, whereas MoE
activates few experts per token -- less compute per communication round, and a token may need
experts resident on several devices. If that is right it is a general result about TP and MoE,
it is checkable on this fleet, and nobody appears to have written it up.

**Sampling values confirmed from the artifact, not just the card:**
`Qwen3.8-27B-HF-meta/generation_config.json` ships `temperature 1.0, top_k 20, top_p 0.95`.

**Paired seeds.** Fixed seed set `{s1..sK}`, identical across every arm, so comparisons are paired
rather than independent — substantially more power per run, and McNemar / Wilcoxon become
available. Honest limit: pairing holds cleanly only up to the first divergent token.

**Gate before trusting any of it:** a P-A0 analogue proving *seeded* runs reproduce byte-identically
on the same box at the same device count. The existing temp-0 determinism receipt does not transfer.

## Known deviations from the card — stated, not hidden

| | card | us | why |
|---|---|---|---|
| reasoning tokens | **262,144** | ~32,768 (confirm in pilot) | 262K at fleet decode is ~7-8 h **per item** |
| final response | 131,072 | 8,192 | as above |
| context | 262,144 native / 1M YaRN | 32,768 | VRAM |

**This is the deviation that cannot be closed.** Sampling params are free to match; the token
budget is not. It follows that **HermesAgent-20's ~14k ceiling is 18x below spec**, so any prior
"runaway" observed against it is not a runaway by the manufacturer's own framing.

**Cap-hits are right-censored observations**, not runaway confirmations: consumption exceeded the
cap, by an unknown amount. Score them as censored; never as failures.

## Time is measured, never imposed

A wall-clock cap would be **arm-dependent**: `FINDING_BONSAI_SPEED` measured PQ2_0 at 2.92x
PTQ1_0 and 24% faster than stock IQ2_XS. A time cap hands the fast arm ~3x the thinking budget of
the slow one, and "got cut off mid-reasoning" would be published as "judges worse."

Three distinct things, never conflated:

| | role | setting |
|---|---|---|
| **token cap** | measurement boundary | constant across arms, generous |
| **wall-clock timeout** | operational safety valve | generous (2400 s), fires only on pathology |
| **time budget** | analysis parameter | never set; swept post hoc |

Log wall-clock and token consumption per run. Any time budget T is then applied in scoring, giving
the **entire time-budget curve for free**. Report tokens alongside seconds so results port to
other hardware.

## Allocation: reps vs items

Error on a corpus-level estimate decomposes roughly as

```
between-item variance / N   +   within-item variance / (N x K)
```

`K` appears only in the second term, so reps hit a floor set by `N`. K=1→3 buys a lot, 3→5 some,
5→10 nearly nothing. But under graded rungs, reps buy **threshold resolution** rather than
precision on a mean: K=5 gives six distinguishable levels per rung.

**Protocol:**

1. **Pilot** at K=2, all 30 items, **reference arm only**.
2. **Freeze** allocation: **K=5 on the 2 rungs nearest each family's threshold, K=2 elsewhere.**
3. **Run** all arms on the frozen allocation.

Calibrating on the reference arm only means the instrument is tuned on the control, never on the
comparisons.

| | runs/arm | 4 arms | est. |
|---|---:|---:|---:|
| flat K=5 | 150 | 600 | ~40-50 h |
| **pilot-allocated** | **96** | **384** | **~26-32 h** |

Plus ~5 h pilot, ~8 h temp-0 sensitivity arm. **Re-estimate from the pilot** — temp 1.0 with
thinking on will exceed the panel's 3.3 min/run baseline, and the token cap is now the cost driver.

## Reasoning effort is a crossed factor, not a remediation

`reasoning_effort` on this family is a **prompt edit** (AFM-23) — the template injects system text:

| level | injected | sha |
|---|---|---|
| `medium` | 60 chars | `cf3fd97abdad` |
| `low` | 226 chars | — |
| `xhigh` (default) | 297 chars | `0a7393b3d4d0` |
| `high` | alias to `xhigh` on stock; **hard error on Bonsai 2** | — |

**`xhigh` injects "validate key assumptions, consider plausible alternatives" — which is the
judgement axis, handed to the model as an instruction.** Running the corpus at `xhigh` alone
measures instruction-following, not judgement. `medium` is the neutral condition; this is why the
v1 panel used it.

**Retry-on-failure is rejected as the primary design.** It yields P(recover | failed) and is blind
to P(break | passed) — and the reverse flow is documented in our own notes (`xhigh` hurt on
tier_cal abstention tasks). Selecting on one extreme and re-measuring is a regression artifact.

**Two screeners as a prereg'd go/no-go gate (~40 runs):**
- retry the failures at `xhigh`
- re-run a sample of the passes at `xhigh`

If nothing recovers and nothing breaks, effort does not interact — skip the full cross. **The
screener number is a gate, never an effect size.**

If it does interact, effort becomes a second axis: `threshold(codec, effort)`, bracketed by
`medium` and `xhigh`.

**Operational:** `xhigh` raises P(runaway) on unresolvable prompts (AFM-23), and this corpus is
deliberately full of them — so the `xhigh` arm is the one that blows budgets. Arm
`tools/screen_runaway.py`, check `content_len` separately from HTTP status (315 of 580 requests
once looked like a server defect), never send `high` to Bonsai 2.

## Controls — the differential needs them

The headline is "judgement fell, knowledge held." **A flat knowledge line is what makes the
judgement line a finding.** Without it the result is "the model got worse," which is unpublishable.

| control | n | why |
|---|---:|---|
| **MMLU-Pro, stratified** | ~500 | knowledge anchor; discriminating band for a 27B |
| **IFEval** | ~540 | instruction-adherence bridge; programmatic scoring, no judge model |

**Rules:** same box, **same device count**, same partition scheme as the judgement arms
(`FINDING_INSTRUMENT_VERSION`: `.73` 2-GPU returned SUSPECT where `.194` 4-GPU returned CORRECT on
an identical seed). Matched effort level on both axes or the differential is confounded.

**Never quote the subsample as an AA-comparable number.** 500 stratified items is not MMLU-Pro; it
is an internal control across arms. Label it so in the receipt.

Doubles as a contamination canary: if a *more* quantized arm improves on MMLU-Pro, the harness is
broken.

Explicitly excluded: GPQA Diamond (floor saturation at 2.5 bits), AIME (30 items, near floor),
LiveCodeBench / SciCode (execution harness cost), tau^2-bench / Terminal-Bench (agentic — competes
with our own corpus on slower hardware).

## Scoring

- **Per family, per arm:** threshold rung (first rung where checking stops).
- **Across arms:** paired tests on the shared seed set — McNemar for binary, Wilcoxon signed-rank
  for thresholds.
- **Censored runs** handled explicitly; never scored as failures.
- **Time-budget curve** swept post hoc over T.
- **Primary x-axis is scored bytes** (file size minus the MTP draft head), not the label —
  `IQ3` spans 2.97-3.74 real bpw.

## Predictions — MUST be committed before any arm runs

**Mark's predictions:** _(to be filled)_

**Claude's predictions, on record:**

| id | prediction |
|---|---|
| **P-J1** | Judgement threshold degrades monotonically with scored bytes |
| **P-J2** | **THE FORK** — at matched scored bytes, judgement threshold degrades *faster* than MMLU-Pro accuracy |
| **P-J3** | `xhigh` raises the threshold by >= 1 rung vs `medium` on at least half the families |
| **P-J4** | `xhigh` raises token consumption disproportionately at the highest rungs (runaway interaction) |
| **P-J5** | Control — IFEval moves less than the judgement axis across the same arms |
| **P-J6** | The temp-0 sensitivity arm shows *larger* apparent degradation than card params |

**P-J6 tests the design rationale itself.** If it is falsified, the amplification argument that
justified running in spec was wrong, and that is worth knowing regardless of the headline.

## What would make this a null result

- All six families threshold at the same rung across all arms → corpus saturated again; the rung
  spacing was too coarse or too fine. Diagnosable from the **pilot**, before the budget is spent.
- Judgement degrades exactly in step with MMLU-Pro → P-J2 falsified, and the honest write-up is
  "quantization damage is undifferentiated," which is still worth publishing.
