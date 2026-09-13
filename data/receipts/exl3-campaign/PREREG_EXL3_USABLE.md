# Prereg — does EXL3's distribution advantage survive contact with a task? (EXL3 campaign, test 11, ledger O6)

**Written 2026-09-13 ~11:30, while test 10's first arm is still running and no point of its curve
exists yet.** That timing is the point: **the rule that picks the two models is committed before the
data that will pick them.**

Mark set the bar: *"we certainly would need to show a substantial difference in **usable quality** in
order to justify it."* Test 10 measures KL divergence — how far a quantized model's *distribution* sits
from the reference. It cannot say whether code compiles. This test asks whether the distribution
advantage buys anything a user would notice.

## The question

**At matched VRAM, does EXL3's lower KLD produce more correct answers than GGUF?**

## Arm selection — a rule, not a choice

Run `tools/score_exl3_compression.py` against test 10's completed `results.jsonl` and take:

- **EXL3 arm:** the EXL3 point with the **largest log-KLD advantage** over the GGUF lower envelope
  interpolated to its VRAM — the format's *best case*, since a null result there is decisive.
- **GGUF arm:** the GGUF envelope point whose peak VRAM is **closest to the EXL3 arm's from above**.
  GGUF is never handicapped on size; where the two cannot be matched exactly, **the tie goes to GGUF**.

**If no GGUF point sits at or above the EXL3 arm's VRAM, the EXL3 arm falls back to the next EXL3 point
up** until one does. **If test 10 falsifies P-C1 (EXL3 is not below the GGUF curve), this test does not
run** — there would be no advantage to translate, and running it anyway would be fishing.

The selected pair, and the numbers that selected it, are recorded in the result before any task runs.

## Setup

- **Node `.73`**, both P100s, wake proxy paused, orchestrated, one model resident at a time.
- **Harness:** `data/receipts/humaneval-plus/hep_eval.py`, unmodified — the same one behind the
  Puzzle/Laguna panel, including its preflight that aborts rather than reporting a false 0%.
- **HumanEval+**, all 164 problems, both arms seeing an identical problem list in identical order.
- **`-np 1`, temperature 0** for the scored sweep. Per [[agent-benchmark-determinism]], temp-0 is
  byte-deterministic only at `-np 1`; concurrent batching reintroduces nondeterminism.
- **Speculative decoding OFF on both arms.** MTP acceptance differs sharply between the formats
  (1.24× vs 1.69×, test 6), and a decode path that differs between arms is a confound in a quality test
  even where it is meant to be distribution-preserving.
- **One chat template, pinned by file, for both arms.** Both snapshots ship their own and they are not
  the same file. Given what this week's template work found — a single unassigned variable silently
  changing what a model receives — an unpinned template would be a live confound, not a hypothetical.
- **Both servers restarted immediately before their sweep** ([[server-uptime-is-a-variable]]).

## Sweep order: paired, outermost, and resumable

Sweeps run **outermost** — sweep 1 covers all 164 problems on *both* arms before sweep 2 begins.

**Why:** a complete, scoreable, paired K=1 result exists after the first sweep. If the run is cut short
by anything, what survives is a balanced comparison rather than one finished arm and one half-finished
one. K=3 is the target; **K=1 is the floor and is scored on its own terms** ([[incremental-persistence-rule]]).

## Predictions

| id | prediction |
|---|---|
| P-U1 | **The EXL3 arm's pass@1 exceeds the GGUF arm's** on the same 164 problems at matched VRAM |
| P-U2 | **The difference is "substantial" by Mark's bar**, pre-defined below as ≥ 5 points pooled pass@1 |
| P-U3 | The EXL3 arm produces **fewer degenerate outputs** (`degen_ratio`, repetition collapse) — the failure mode aggressive quantization is expected to cause first |
| P-U4 | **Both arms clear 50% pass@1**, i.e. the models at this size are usable at all rather than merely comparable |

**Scoring:** paired two-sided sign test over the 164 problems, as in the Puzzle/Laguna panel. A result
is reported as a difference only when the paired test reaches p < 0.05; otherwise it is reported as **no
detectable difference**, with the discordant-pair counts shown.

## Declared in advance

- **"Substantial" is defined before the data, at ≥ 5 points.** Mark's bar is a large effect, not a
  statistically detectable one, so a 1–2 point win that clears p < 0.05 **confirms P-U1 and falsifies
  P-U2**, and the receipt will say EXL3's advantage is real but not worth switching for. Splitting these
  two predictions is deliberate.
- **P-U4 can sink the whole line of argument, and is meant to.** If the selected pair sits at 2.5–3 bpw
  and *both* models fail most problems, then EXL3's compression advantage is real and lands **below the
  usability floor** — a genuine finding, and an argument against the low end rather than for it.
- **One benchmark, one model, one language.** HumanEval+ is Python code generation. It is mechanically
  scored and paired, which is why it is first; it is not "usable quality" in general, and the receipt
  will not generalize past it. Tool-call and JSON-schema adherence is the more relevant axis for this
  repo's own workloads and is a **separate** test, not a section of this one.
- **`pass@1` at K=1 is an existence proof per problem, not a rate.** Only the K=3 pooled figure is
  quoted as a rate, and only if all three sweeps complete.
- **This test cannot separate format from quantizer.** EXL3's points come from one quantizer at one
  setting; the GGUF point comes from whichever packager owns that part of the envelope. A win is a win
  for *that file*, not proof that trellis quantization beats k-quants in general.
- **Runtime is a real risk and is measured, not guessed.** EXL3 decodes at ~0.65× the daily driver on
  `.73`, so the EXL3 arm is the slow one. **Sweep 1 is timed, and K=3 is only committed to if the
  measured sweep-1 wall clock leaves room inside the dead-man.** Otherwise the test reports K=1.
- **Not launched.** Needs Mark's go-ahead and a free `.73`; test 10 holds the node until ~15:00.

**Driver:** `exl3_usable.py` (to be written with this prereg's scorer, before the run).
**Scorer:** `tools/score_exl3_usable.py`, committed before any arm runs.

---

## Amendment 1 — 2026-09-13 ~11:40, still before any arm runs

Written after **reading `hep_eval.py` rather than trusting my memory of it**. Three corrections; the
predictions P-U1–P-U4 are unchanged.

### 1. The K=3 outermost-sweep design is withdrawn as moot, and replaced

The harness fires its K completions **inside** `run_one`, one problem at a time — sweeps are inner, and
"outermost sweeps, harness unmodified" was not achievable as written. More to the point it was **moot**:
at temperature 0 with a single in-flight request the run is byte-deterministic, so three sweeps would
produce three identical results.

**The primary measurement is therefore `HEP_TEMP=0`, `HEP_K=1`** — one deterministic pass of 164
problems per arm, scored as a **paired two-sided sign test** over the 164 problems. For comparing two
quantizations of one model this is the cleaner instrument anyway: it removes sampling noise entirely,
so every difference between the arms is attributable to the weights.

**Consequence for P-U1/P-U2, declared now:** `pass@1` at K=1 is an existence proof per problem, so the
pooled figure is reported as **"solved 164/164 greedy"**, never as a deployment rate. The ≥5-point bar
for P-U2 is unchanged and applies to that greedy figure.

**A temperature-recommended `K=3` run is a secondary, optional extension**, run only if the greedy
result is interesting and the node is free. It is explicitly *not* what P-U1–P-U4 are scored on.

### 2. The determinism requirement was already met, and is now verified rather than assumed

`hep_eval.py:49` hardcodes `WORKERS = 1`, commented *"single in-flight -> one server slot -> no
batch-nondeterminism confound"*. The prereg's `-np 1` condition stands, and the harness cannot violate
it — checked by reading the line, not by inferring it from the run's behaviour.

### 3. The harness violates the incremental-persistence rule, and the mitigation is declared

`hep_eval.py` calls `json.dump` **once, after all 164 problems finish**. A run that dies at problem 150
leaves no JSON at all — precisely the failure [[incremental-persistence-rule]] exists to prevent.

**The harness will not be modified**, because its scoring logic is what makes these numbers comparable
to the Puzzle/Laguna panel, and editing it to fix persistence would silently fork that comparison.

**Instead:** each arm's stdout is captured with `tee` to a per-arm log, and its per-problem line
(`[ n/164] HumanEval/x pass_frac=... buckets=... toks=...`) is **declared to be the incremental
record**. If an arm dies partway, it is scored from the log over the intersection of problems both arms
completed, and the receipt states the reduced N. The log is a weaker record than the JSON — it carries
no traces and no `rc_chars` — so a partial run can score P-U1 and P-U2 but **not P-U3**, which needs
`degen_ratio` over saved traces.

---

## Amendment 2 — 2026-09-13 ~16:05: the arm pair, chosen after test 10 (disclosed as post-data)

**The selection rule was ambiguous and only turned out to be so with the data in hand.** It asked for the EXL3
point with the largest advantage over "the GGUF lower envelope" without naming which of test 10's two envelopes,
and the two readings pick different pairs — neither of them the comparison the rule was written to produce:

- **all packagers** → EXL3 3.00bpw against **AD-IQ3_XXS**, a recipe far off the UD curve, which EXL3 beats by default;
- **UD only** → EXL3 3.50bpw against **UD-IQ4_XS**, 1.5 GB larger and closer to the reference.

**So the pair below was chosen after seeing test 10, and that is recorded rather than papered over.** Mark's call:

| side | file | peak VRAM | mean KLD (test 10) |
|---|---|---|---|
| **EXL3** | EXL3 3.00bpw | 10,568 MiB | 0.046152 ± 0.001743 |
| **GGUF** | UD-IQ3_XXS | 11,532 MiB | 0.047609 ± 0.001210 |

**Why this pair.** The two differ by 3% in KLD, inside the summed uncertainties — a **TIE** by test 3's rule —
while EXL3 uses **964 MiB less**. It asks what the campaign actually needs to know: **when two files are
indistinguishable in distribution, do they behave the same on a task, and is the VRAM saving free?** GGUF is not
handicapped: it holds more VRAM and the marginally lower KLD.

**The registered predictions stand unchanged, and their priors have moved.** P-U1 (EXL3's pass@1 exceeds the
GGUF's) is now a genuine coin flip rather than a favourite, because the pair is a distribution tie; the
informative outcomes are **no detectable difference** or a falsification. **A confirmed P-U2 (≥ 5 points) would be
the surprise** — it would mean KLD is blind to something the task exposes. P-U3 and P-U4 are unaffected.
