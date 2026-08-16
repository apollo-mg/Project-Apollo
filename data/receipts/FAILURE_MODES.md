# Apollo failure-mode catalogue

Failure modes observed while using LLMs on this fleet — any model, any vendor, local or
frontier — plus the process failures around them. Format borrowed from
`data/HSM/docs/coding-agent-system-prompt/research-failure-mode-catalog.md`
(h4rm0n1c), which is the reason this file exists.

**Numbering is `AFM-n` to avoid colliding with HSM's `FM-n`.** Where an entry maps onto one
of h4rm0n1c's, the cross-reference is given; those are convergent findings, not copies.

**Working hypothesis behind keeping one file instead of several:** a corrective for one model
is usually a corrective for many. Nothing below is Claude-specific, Gemini-specific or
local-model-specific unless the entry says so, and several entries were first seen in one
model and later reproduced in another.

**Entry rule.** An entry needs an *observed instance with a receipt*, not a plausible worry.
Speculative failure modes belong in a prereg, not here. When an entry is added, the corrective
must be something checkable before the fact, not "be more careful".

---

## A. Measurement failures — the instrument is the experiment

### AFM-1: Instrument noisier than the effect
**Class:** measurement **Cross-ref:** none in HSM (that catalogue is behavioural)

A design isolates the right variable, the arms run cleanly, and the result means nothing
because replication noise exceeds the difference under test.

**Observed.**
- `qwen38-lowbit/RESULT_2x2.md` — eight prompts, 8/8 in all four cells. Zero discriminating
  power; the test could not have produced a different answer.
- `qwen38-packagers/RESULT_AD_LADDER_HEAD_AUDIT.md` Finding 5 — four head-isolated builds,
  correct isolation, but within-arm swing 5.4 pp against a 1.86 pp between-arm difference,
  and acceptance non-monotone in precision. Recorded UNRESOLVED.
- Repeat offence: the second happened *after* `hle-mini/build_screen.py` was written
  specifically to avoid the first, in a different domain.

**Corrective.** Before running, state the smallest effect the design can resolve, and how
that was calculated. If the expected effect is smaller, the run is not worth compute. Prefer
more *conditions* over more *reps* when reps are deterministic replays (see AFM-6).

---

### AFM-2: Design/statistic mismatch
**Class:** measurement

Using the wrong statistical model for the design, in the conservative direction, which looks
like rigour and is not.

**Observed.** `hle-mini/POWER.md` — independent-sample binomial SEs applied to a *paired*
design, concluding n=200 could not resolve a 9.2 pp gap. Under McNemar the same 200 questions
resolve **6.2 pp** at 20 % discordance. The unpaired figure is only correct if the two arms
see different question sets.

**Corrective.** Name the design (paired / independent / repeated-measures) in the prereg,
before choosing the test. Counter-intuition to keep in view: for paired designs, *more similar
arms are easier to separate*, not harder.

---

### AFM-3: Confounded comparison framed as an isolation
**Class:** measurement **Cross-ref:** HSM FM12 (assumption-to-action)

Calling something an A/B when more than one thing differs.

**Observed.**
- The bartowski-vs-unsloth `Q6_K` packager test was framed as a draft-head isolation. The two
  files also differ in the body (`Q8_0`×120 vs ×48). Corrected, and
  `PREREG_HEAD_ISOLATION.md` was written to do the clean version.
- Claimed `IQ2_M` and `IQ3_XXS` had an "identical draft head" because the *type histograms*
  matched (IQ4_XS×5 + IQ3_S×3). Per-tensor assignment differed — `attn_q` is IQ4_XS in one and
  IQ3_S in the other. A histogram is not an assignment.

**Corrective.** Before calling it an A/B, enumerate what else differs and write it down. For
GGUF specifically, diff the per-tensor table, never the type counts.

---

### AFM-4: Aggregate hides sign-flipping subgroups
**Class:** measurement

Two conditions match closely in aggregate and differ substantially per subgroup, with the
subgroup differences cancelling. The aggregate agreement is an artefact of the mix.

**Observed.** `qwen35-drafters/RESULT_MTP_VS_DFLASH.md` — MTP and DFlash acceptance matched
within 1 pp at all three depths (77.49/76.79, 53.15/52.86, 29.03/29.93). Mid-run this was
reported as "acceptance is drafter-independent". Per prompt they diverge by up to 12 pp with
*consistent signs*: DFlash wins code/SQL/JSON/regex/list, MTP wins prose/story/repeat, each
replicated across three independent depths. The aggregates coincided because the differences
cancelled against that particular prompt mix.

**Corrective.** Never report an aggregate without looking at the per-subgroup breakdown first.
Matching aggregates are weak evidence of equivalence; they are consistent with equivalence and
with large opposing effects. A benchmark drawn from one content type would have inverted this
conclusion.

---

## B. Execution failures — process, mine unless noted

### AFM-5: Open-loop chaining on an unverified completion signal
**Class:** execution **Cross-ref:** HSM FM13 (open-loop execution / unverified state chaining)

An action reports success, the next action is chained on it, and the success signal referred
to something other than the work.

**Observed.** Twice within one hour, 2026-08-15. A benchmark was launched as
`nohup bash run.sh &` *inside* an already-backgrounded command. The harness reported
"completed, exit code 0" for the wrapper shell exiting immediately; the benchmark had not
started. Chained on it both times. A third variant: a waiter job was killed and took its
child benchmark with it, because the benchmark was spawned as a child rather than under
`setsid`.

**Note.** This is the failure h4rm0n1c documents in `slice-13-closed-loop-execution.md`, where
the worker "could later identify and quote the rules it violated. The rules were semantically
present, but they did not reliably govern the action sequence." Same here — knowing the rule
did not prevent the failure twice.

**Corrective.** A completion signal must name the artefact, not the process. Verify a
postcondition that only the real work could satisfy — a DONE marker in the output, an expected
file, an expected arm count — before any dependent action. For long jobs, detach with `setsid`
so the work outlives its supervisor.

---

### AFM-6: Result reported before replication was checked
**Class:** execution **Cross-ref:** HSM FM5 (premature output commitment), FM12

Reporting a number as a finding when its stability has not been examined.

**Observed.** 2026-08-15, head-isolation: reported "F16 head 66.00 %, Q4_0 64.14 %" as a
result. The reps were deterministic replays (effective n=5 prompts, not 3000 tokens), one arm
was bistable on a single prompt with a 5.4 pp swing, and the four-arm ordering turned out
non-monotone in precision. Retracted in the same session.

**Corrective.** No number is reported until rep-to-rep variation has been looked at
explicitly. Where reps are deterministic, say so — a deterministic replay is not a second
sample, and quoting `n` in tokens when the independent unit is prompts overstates power by
orders of magnitude.

---

### AFM-7: Silent partial failure behind a success exit code
**Class:** execution / tooling **Cross-ref:** HSM FM10 (task abandonment on partial failure)

A multi-arm job loses arms without the failure surfacing in the summary.

**Observed.**
- 2026-08-15: three of four benchmark arms died in ~4 s each
  (`error: invalid argument: 3.5/Qwen3.5-9B-DFlash.Q8_0.gguf`) because an unquoted shell
  variable containing `/mnt/.../Qwen 3.5/...` word-split at the space. The run "completed".
- Earlier, a `sed`-cloned IQ2 script renamed only 6 of 12 arms; the other six would have
  silently overwritten six existing IQ3 result files. Caught by counting arms, not by any
  error.

**Corrective.** Assert the expected arm/result count at the end of any batch and fail loudly
if short. Keep model paths space-free (symlink if the store has spaces). When cloning a
script, diff it against the original rather than trusting the edit.

---

## C. Model-behaviour failures — observed across vendors

### AFM-8: Answer-key shortcut when the eval is reachable
**Class:** model behaviour **Models:** Gemini Flash, Gemini Pro 3.1 (observed); assume all

A model with filesystem or tool access finds and reads the grading key instead of solving the
task, and reports a score.

**Observed.** Twice in one session — Flash escaping to the answer key on S2, Pro 3.1 on S5.
Directly relevant now that HLE is cached locally at
`~/.cache/huggingface/datasets/cais___hle` with questions *and* answers.

**Corrective.** Treat reachable ground truth as contaminated by default, not as a trust
question. Run evals where the key is not on the filesystem, or with tool access removed. Keep
traces and check them — this is only detectable if the harness records what the model did, so
an agent harness that hides tool calls cannot be audited (a reason not to benchmark through
one).

---

### AFM-9: Nondeterminism at temperature 0
**Class:** model behaviour **Models:** local llama.cpp builds; varies by drafter/arch

Greedy decoding is not reproducible, so a single run is an existence proof rather than a rate.

**Observed.**
- `.73` agent benchmarks: HA-04 bistable across runs at 35/100/100/35.
- 2026-08-15, `qwen35-drafters`: 8 of 72 prompt/arm cells differed between identical reps —
  and **all 8 were MTP arms. Zero DFlash cells varied.** Nondeterminism is not uniform across
  speculative implementations; one drafter reproduced bit-identically and the other did not.

**Corrective.** K=1 at temp 0 is an existence proof, never a rate. Report the replication
check alongside the result, and record *which* configuration was unstable — it is a property
of the code path, not a constant of the hardware.

---

### AFM-10: Schema brittleness under multi-turn tool use
**Class:** model behaviour **Models:** heavily-quantized local models ("2-Bit Drunk" loops)

Low-bit models degrade into malformed or looping tool calls across multi-turn JSON schemas,
while looking fine on single-turn prompts.

**Observed.** Standing constraint in `CLAUDE.md`, encountered repeatedly on the P100 fleet.

**Corrective.** Schema validation with an error-feedback loop (Pydantic/Zod) is the standard
mitigation. Do not evaluate tool-calling competence on single-turn tests; the failure is
multi-turn by construction.

---

### AFM-11: Curiosity collapse under a narrow instruction
**Class:** model behaviour **Cross-ref:** HSM FM11 (premature narrowing)

The model answers the literal question and stops, discarding the adjacent finding that was the
actually valuable output.

**Observed.** Recorded from HSM's slice 11 rather than independently reproduced here — kept as
a watch item, since the failure is invisible by definition: nothing in the output says what
was not investigated.

**Corrective.** For investigation tasks, ask explicitly what was ruled out and what was left
unexamined. Absence of a finding is not evidence of absence when the instruction was narrow.

---

## D. Artefact and metric failures

### AFM-12: The label is not a spec
**Class:** artefact

A published name describes what recipe was *requested*, not what the file contains.

**Observed.**
- Three publishers' `Q4_K_M` for Qwen3.8-27B span 16.8–19.0 GB and 0.011–0.021 KLD.
- `UD-Q8_K_XL` whose experts are 100 % MXFP4; `IQ2_M` whose experts mix
  IQ2_XXS/IQ3_XXS/IQ4_XS/IQ2_S.
- "Q6_K" ships as three different recipes from three packagers.

**Corrective.** Probe the header before comparing files. `modules/gguf_librarian.py probe`
reads the tensor table over HTTP range requests — a full ladder costs tens of MiB, so there is
no excuse for assuming.

---

### AFM-13: The metric is structurally blind to a shipped component
**Class:** measurement / artefact

A quality metric cannot see part of the artefact, so that part drifts unmeasured across an
entire field.

**Observed.** `qwen38-packagers/RESULT_AD_LADDER_HEAD_AUDIT.md` — `blk.64` (the MTP draft
head) never executes in a normal forward pass, so KL-divergence and top-1 agreement are
computed without it. Every value in a 16-file published ladder would be bit-identical with an
F16 or IQ1_S head. The same model card recommends running that head via
`--spec-type draft-mtp`. The consequence: no packager's imatrix has `blk.64` coverage, because
calibration never executes it either, so every published MTP head is quantized blind.

**Corrective.** For any metric, ask which parts of the artefact participate in producing it.
A component that does not participate is unmeasured no matter how good the metric is.

---

### AFM-14: Documentation contradicted by the artefact
**Class:** artefact

The card states a policy the files do not implement, in a way that is only visible by reading
the artefact.

**Observed.** AtomicChat's Qwen3.8 card: "It is pinned to `q5_k` in every file here." Eight of
sixteen files are not, and two carry `IQ3_S` (~3.4 bpw), below `Q5_K`. The partition is 15/16
explained by `tensor_requires_imatrix()` — the pin reached every tier where llama.cpp would
have aborted and missed the tiers where it would not. Not bad faith; a policy that silently
did not apply where nothing forced it to.

**Corrective.** Verify stated build policy against the artefact when the claim is load-bearing.
Cheap for GGUF (AFM-12's probe). Applies to our own receipts too — state what was checked
rather than what was intended.

---

## Standing meta-lesson

Six of the fourteen entries are process failures on this side, not model failures. The
recurring shape is **AFM-1 and AFM-5: trusting an instrument or a signal without checking what
it actually measured.** Both recurred *after* being documented, in a new domain, which is the
argument for a single cross-domain file rather than a note in each receipt.

---

### AFM-15: Detector too sensitive — a false positive that nearly inverted a conclusion
**Class:** measurement **Mirror of:** AFM-1 (instrument too noisy to see the effect)

AFM-1 is an instrument that cannot see a real effect. This is the opposite: an instrument that
reports effects which are not there. Both invalidate a run; only the first is usually watched
for.

**Observed.** 2026-08-16, KV-degradation isolation. A degeneracy detector flagged output as
`DEGENERATE` when it contained a run of >40 identical characters or fewer than 12 distinct
characters — thresholds chosen from the real failure, which was `maxrun=2048, uniq=1`
(the entire response one repeated character).

Arm C then flagged `len=8674 maxrun=52 uniq=76`. Inspecting the actual text showed a normal,
coherent response — the 52-run was a table rule or ASCII pipeline diagram, which the prompt
("explain a CPU pipeline") invites. Had the flag been trusted, **arm C would have been reported
as degenerate and context length wrongly implicated alongside the codec**, breaking the whole
isolation.

**Corrective.** Set detector thresholds from the *failure* magnitude with a wide margin, not
from where legitimate output happens to sit — here 2048 vs 52 is a 40x gap and the threshold
sat at 40. And **never report a detector flag without inspecting the flagged artefact at least
once.** A detector is a filter for attention, not a verdict.
