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

---

## Amendment 3 — 2026-09-13 ~16:15: the test moves to `.194`, the arms run side by side, thinking off

Mark: *"move the test to .194 since it'll complete faster, and .73 can be allowed to sleep."*

**Node: `.194`, four P100s — one socket and two cards per arm.** EXL3 on GPUs 0–1 under
`numactl --cpunodebind=0 --membind=0`; the GGUF on GPUs 2–3 under node 1 (topology from
`scripts/startup/llama_cluster_ctl_194.sh`, verified 2026-07-06). Stage 1's triad measured cross-socket reads at
**7.0 GB/s against 22.7 local**, so binding each arm to its own socket keeps the two out of each other's memory.
Each arm's harness process is bound to the same socket as its server.

**The arms therefore run at the same time. Declared consequences:**
- **Wall-clock times are not comparable between arms and are not scored.** Test 11 scores correctness.
- **Determinism is unaffected:** each server runs `-np 1` at temperature 0, so neither arm's load can change the
  other's output ([[agent-benchmark-determinism]]).
- If either server dies, its arm is scored over the problems both completed, per Amendment 1.

**Thinking is off** — `chat_template_kwargs: {"enable_thinking": false}`, identical in both arms. **Why:** on two
P100s the EXL3 arm decodes about 8 tok/s, which makes a thinking-on pass of 164 problems roughly **six hours per
arm** against about **1.5 with it off**. HumanEval+ scores the code, not the chain, and A6 already found `medium`
(which injects nothing) beating the `xhigh` default on every axis. **A thinking-on run remains available as an
extension**, and is the first thing to try if the off run is a tie.

**Provenance, an upgrade on test 10.** Both files are copied to `.194` and verified there: the EXL3 snapshot
against a manifest of the hf_fetch-verified control-plane copy, and **the GGUF against unsloth's published
sha256** — test 10's GGUFs were size-checked only.

**Pinned identically across arms:** the 27B EXL3 snapshot's `chat_template.jinja` via `--chat-template-file`
(byte-identical to stock Qwen3.8; the copy's sha256 is recorded at staging), `-c 8192 -np 1 -fa on -ctk f16
-ctv f16 -sm layer -ngl 99 -fit off`, `HEP_TEMP=0 HEP_K=1 HEP_MAXTOK=4096 HEP_THINK=0`. `-sm layer` is required:
`32c2c1479` rejects multi-device EXL3 tensor split.

---

## Amendment 4 — 2026-09-13 ~16:25: the GGUF arm's provenance, the dataset, and how P-U3 is actually measured

**1. The GGUF arm is unsloth's UD-IQ3_XXS at revision `f9758630` (2026-08-19), and that is now proven, not
assumed.** Staging aborted because our copy — 11,913,559,104 B, sha256 `0a6129dc…` — does not match the file
unsloth publishes today (10,934,860,704 B, `c0b7c303…`). Walking the repo's history: **`f9758630` carries our
exact size and hash, and every later revision carries the smaller re-cut.** unsloth re-cut the file the same day.
`tools/hf_fetch.py`'s docstring warns about exactly this; here is a documented instance.

**We keep our copy and pin the revision.** The pair in Amendment 2 rests on the KLD test 10 measured **for this
file**; the current cut is a different file with unmeasured fidelity. The staging gate now verifies against
`0a6129dc…` and records the revision.

**Consequence for test 10:** its G3u point is "unsloth UD-IQ3_XXS **at revision f9758630**", not "the file
unsloth publishes today". A note goes into `RESULT_EXL3_COMPRESSION.md`; the measurement is unaffected.

**2. Dataset.** `humanevalplus.jsonl` already on `.194` at `~/hep/`, 11,317,638 bytes — matching
`fetch_dataset.py`'s recorded fingerprint for the file the Puzzle and Laguna legs used. The driver asserts that
byte count and 164 problems before it spends any inference, alongside `hep_eval.py`'s own preflight, which proves
the grader passes a canonical solution.

**3. P-U3 is scored on what the harness records.** The prereg said "fewer degenerate outputs (`degen_ratio`)", but
`hep_eval.py` computes `degen_ratio` only for the one saved failing trace per problem, not per sample. **P-U3 is
therefore scored on two recorded quantities:** the count of degeneracy-shaped buckets (`TRUNCATED` + `NO_ANSWER`)
over the 164 samples, and mean output tokens; the saved traces' gzip ratios are reported alongside when both arms
have them. Fixed here, before the run.

**4. Everything else stands:** temperature 0, K=1, thinking off, one pinned template, `-np 1`, arms on separate
sockets and GPU pairs, wall-clock not scored.

---

## Amendment 5 — 2026-09-13 ~16:50, both arms running: the KV check is vacuous here too

**Recorded while the run is in flight, before any result.** Both arms logged `KV []`: buun's server prints no
`K (…)` / `V (…)` lines at its default verbosity, so the driver's guard — *abort if a found type is not f16* —
had nothing to inspect. **A check that cannot fail.** The identical defect was found and disclosed this morning
in `qwen4exp/PREREG_FLASHNEXT_RESIDENCY.md` Amendment 2; I did not carry the fix into this driver.

**What is and is not affected.** Both arms pass `-ctk f16 -ctv f16` explicitly on the same command line, so the
KV type **cannot differ between them** — the paired comparison is intact either way. What is unproven is the
*absolute* claim that both ran f16 rather than buun's VBR default.

**The real check, after the run:** reload each arm's exact command with `-lv 4`, load only, no requests, and
record the K/V types — the same procedure that supplied the positive check for Stage 1 of the Flash-Next test.
Recorded in the result whichever way it lands.
