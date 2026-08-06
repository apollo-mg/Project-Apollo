# MTP on an agent benchmark: same score, 35 % scenario instability, and a logprob defect

RX 9070 XT 16 GB, `llama_cpp_turboquant` (TheTom), `Qwen3.6-35B-A3B-UD-IQ2_M`.
Arms differ **only** by `--spec-type draft-mtp --spec-draft-n-max 2`.
`-c 65536`, f16 KV, `-np 1`, `--cache-ram 0`, temperature 0, stevibe's HA-20 runner unmodified.
Date 2026-07-29. Builds on `MTP_DETERMINISM.md` and `MTP_STRUCTURED_OUTPUT.md`.

## Design

| arm | K | why |
|---|---|---|
| base | 1 | determinism verified on this model/build (6/6 byte-identical) |
| MTP | 3 | MTP is nondeterministic at temp 0 — a single draw carries no information |

Timeouts **token-matched, not wall-matched**: base 300 s, MTP 240 s, both ≈23.9k tokens.
Measured decode confirmed the sizing: base **79.31 t/s** (predicted 79.5), MTP **116.57 t/s**
on this workload — higher than the 99.7 t/s measured on prose, because HA-20's structured
tool-call output drafts better.

## Headline: the score is identical, the stability is not

| arm | PASS | FAIL | PARTIAL | no-verdict |
|---|---|---|---|---|
| base (K=1) | **14** | 5 | 1 | 0 |
| MTP rep 1 | **9** | 8 | 1 | **2** |
| MTP rep 2 | **15** | 5 | 0 | 0 |
| MTP rep 3 | **13** | 6 | 1 | 0 |
| **MTP majority** | **14** | | | |

**MTP's majority vote equals base exactly: 14/20.** Anyone running this benchmark once per
configuration would conclude MTP is free. The per-rep spread says otherwise.

### 7 of 20 scenarios (35 %) are unstable across MTP reps

| scenario | base | r1 | r2 | r3 |
|---|---|---|---|---|
| HA-04 recall + reuse | PASS 100 | **FAIL 35** | PASS 100 | **FAIL 35** |
| HA-07 execute_code | FAIL 30 | **no verdict** | FAIL 30 | FAIL 30 |
| HA-08 browser automation | PASS 100 | **no verdict** | PASS 100 | PASS 100 |
| HA-10 skill discover+apply | PASS 100 | **FAIL 20** | PASS 100 | PASS 100 |
| HA-12 skill files | PASS 100 | **FAIL 20** | PASS 100 | PASS 100 |
| HA-14 cron update | PASS 100 | **FAIL 70** | PASS 100 | PASS 100 |
| HA-19 recover + retry | PARTIAL 80 | PARTIAL 80 | **PASS 100** | PARTIAL 80 |

**35 % is more than double the ~15 % flip floor measured for vendor-recommended *sampling***
(`HA20_SAMPLING_ARMS.md`). Speculative decoding at temperature 0 is noisier on this workload
than deliberately randomised decoding — while presenting as a deterministic-looking config.

**Direction:** every unstable scenario except HA-19 moved base-PASS → MTP-FAIL. **MTP never
converted a base failure into a success.** With 6 differing scenarios that is suggestive of a
downward tilt, not proof of one.

### Two non-terminating generations, both in rep 1

HA-07 and HA-08 hit the 240 s ceiling with no verdict; base completed them in **51 s** and
**21 s**. Since the budgets are token-matched, these are genuine runaways, not clock artifacts.
Longest single generation observed: **36,465 tokens without stopping** (base's longest
completed turn: 3,756).

**A correction made mid-analysis:** I first reported MTP's median turn as "79× longer than
base". That was wrong — llama-server emits *cumulative* `n_decoded` progress lines for one
continuing generation, and I counted each snapshot as a separate turn. Taking the final value
per task, the medians are effectively identical (**base 100, MTP 102 tokens**). MTP is **not**
more verbose; it occasionally fails to terminate. The corrected picture is narrower and more
useful than the one I nearly published.

## The mechanism question: how does an "accepted" token diverge at all?

Mark asked how many steps stand between a draft token confirmed by the authoring model and a
divergent agentic outcome. Reading the acceptance rule in this fork
(`common/sampling.cpp:621`, `common_sampler_sample_and_accept_n`):

```c
const llama_token id = common_sampler_sample(gsmpl, ctx, idxs[i], grammar_first);
common_sampler_accept(gsmpl, id, true);
result.push_back(id);          // the TARGET's token, never the draft's
if (draft[i] != id) break;     // reject on first mismatch
```

**Zero steps in the acceptance logic are wrong.** The emitted token is always the target's own
sample; the draft is only a comparison key. A draft token cannot reach the output unless the
target independently produced the identical id.

The divergence therefore has to come from `common_sampler_sample` returning a different `id`
than it would without speculation. The only candidate: the draft path evaluates the target on
a **batch of N+1 positions at once**, where plain decoding evaluates **one at a time** —
different batch shape, different reduction order, last-bit differences in the logits.

Mark's objection: *"Doesn't feel like that should invoke enough noise to cause such a
cascade."* Fair, and my earlier "one ULP" was rhetoric, not measurement. Two rival stories:

1. **tiny perturbation + genuine near-ties** — inherent to batched verification, not a bug
2. **large perturbation** — something in the MTP path is substantively wrong

## Measurement: the flip lands in the tightest 0.75 % of positions

Same prompt both arms, `n_probs 5`, 400 positions captured, first disagreement located.

**Base top1−top2 logprob margin across 400 positions:**

| min | p10 | median | p90 | max |
|---|---|---|---|---|
| 0.0094 | 0.567 | **3.631** | 10.78 | 15.91 |

Positions with margin < 0.01: **1 (0.2 %)**. Below 0.1: **6 (1.5 %)**.

**First flip at position 32**, base `' and'` vs MTP `' indexing'`:

```
' and'       -1.1714836
' indexing'  -1.2027336     margin = 0.03125
```

**Margin at the flip = 0.03125 logprob — tighter than 99.25 % of all positions**, against a
median of 3.63 (over 100× wider). The flip site is not arbitrary; it is strongly selected for
near-ties. That is story **1**, and it explains the class-dependence directly: only ~1.5 % of
positions are even eligible to flip, and structured output has almost none of them — which is
the same fact as tool calls drafting at 0.857 acceptance while prose drafts at 0.620.

The margin is exactly **1/32**, a clean binary fraction — consistent with low-precision
arithmetic granularity rather than a large numerical error.

**What this does NOT settle:** whether one flip *suffices* to produce a 36k-token runaway.
The cascade is observed (one flip → four distinct endings, `MTP_DETERMINISM.md`) but not
proven to be the only mechanism in play.

## Second finding: MTP destroys logprob reporting

While measuring the above:

| arm | positions with `top_logprobs` populated |
|---|---|
| base | **400 / 400 (100 %)** |
| MTP | **2 / 400 (0.5 %)** |

Worse than empty — MTP reports `"logprob": 0.0` for tokens whose true logprob is nowhere near
zero. At the flip position it emits:

```json
{"token": " indexing", "logprob": 0.0, "top_logprobs": []}
```

A logprob of 0.0 means probability 1.0. Base scored that same token at **−1.20**. Accepted
draft tokens never pass through the target's sampler bookkeeping, so the server has no
distribution to report and emits **placeholder zeros instead of omitting the field or
erroring**.

Anything consuming logprobs — confidence gating, perplexity/KLD harnesses, constrained
re-ranking, self-consistency scoring — receives plausible-looking garbage under MTP. This is
independently reportable to TheTom and is arguably more actionable than the instability,
because it fails silently and looks like valid data.

It also caps this receipt: the "did the distribution move, or merely reorder?" discriminator
is **unresolved**, because MTP does not report the distribution needed to test it.

## Practical guidance

- **Never benchmark with MTP on.** Not because it scores worse — the majority vote is
  identical — but because 35 % of scenarios become unstable while the config still looks
  deterministic (temperature 0, fixed seed).
- **Treat MTP as a different configuration**, never a transparent speedup. A suite run with it
  on is not comparable to one run with it off.
- **For interactive use it remains a good deal**: +25–47 % decode depending on workload, with
  the caveat that it can rarely produce a non-terminating generation. A hard token cap is the
  mitigation, as it was for the greedy runaway in `HA20_SAMPLING_ARMS.md`.
- **Do not consume logprobs from an MTP server.**

## Limits

- One model, one `n-max` (2), one backend, one card.
- K=3 on the MTP arm: enough to establish instability exists at 35 %, not to pin its rate.
- The downward tilt (6 of 7 unstable scenarios moving PASS→FAIL) is suggestive; n is small.
- The margin measurement is **one flip on one prompt**. The margin distribution is solid
  (n=400); the claim "flips select for near-ties" rests on a single located flip and should be
  repeated across prompts before being stated as general.
- Base-arm margins only — MTP's own distribution is unavailable (see the logprob defect).

## Provenance

- `~/projects/HermesAgent-20/run_ha20_mtp_ab.sh` → `ha20_mtp_ab/`
- `~/projects/HermesAgent-20/mtp_margin.sh` → `mtp_margin/`
- Acceptance rule: `engines/llama_cpp_turboquant/common/sampling.cpp:621`
- Server-side verification call site: `tools/server/server-context.cpp:3800`
