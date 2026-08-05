# Protocol — Lab Measurement Standard

**Status:** v1, 2026-08-05.
**Scope:** the house rules every `Lab_Spec_*` and `Protocol_*` in this lab inherits. Campaign specs
say *what* is measured; this says *how anything is measured here*, so each spec stops re-deriving it
and a delegate does not have to infer it.
**Companions:** `Protocol_Reasoning_Mode_Eval.md` and `Protocol_Mode_Recovery_Eval.md` own the mode
axis in detail; §6 defers to them rather than restating.

---

## 0. The two failures this exists to prevent

**(a) An unmeasured variable becomes a claim.** This is the failure the mode protocols already
document, generalised: every harness setting you did not vary is a setting you attributed to the
model.

**(b) A measurement that never ran is reported as a pass.** This one is newer, more dangerous, and
under-documented, because it fails *green*. Three instances on 2026-08-04 alone:

- `test-backend-ops` returned **exit 0, 3/3 backends passed** on the branch carrying a real NaN —
  because the failing shape had **zero occurrences** in that branch's test file. Clean run, absent
  case, meaningless result.
- A determinism check reported **"0 of 5 runs showed NaN"** across five runs in which the case never
  registered: the insertion anchor landed inside an `#if 0` block, so it compiled into nothing. The
  guard printed `!! case did not run` five times and the script *still* printed a confident summary.
- A job-completion wait looped forever because `pgrep -f nan_probe.sh` matched **its own command
  line**, which contained that string.

Failure (a) produces a wrong number. Failure (b) produces a *right-looking* number for a
measurement that does not exist. Assume (b) until you have positively excluded it.

---

## 1. Positive verification — the load-bearing rule

**An exit code is not evidence a measurement ran. Find the measurement's own artifact.**

- Not "the suite passed" → **"this case's own row is in the output."**
- Not "the script finished" → **"the log contains the value I came for."**
- Not "the file was written" → **"the file contains N records of the expected shape."**

Concretely, before trusting any run:

```bash
grep -c "<the exact case/shape/metric>" "$OUT"     # must be > 0, checked, not assumed
```

**Guards must abort, not warn.** A guard that prints a warning while the script continues to compute
a summary will hand you a confident wrong answer — that is exactly what happened above. If a
precondition fails, exit non-zero at the guard.

**Process checks must not match themselves.** `pgrep -f foo.sh` matches any command line containing
`foo.sh`, including the shell that is checking. Verify by side effect (a log file appearing, a PID
file, a sentinel line) rather than by name matching.

---

## 2. Matched ladders — build every arm yourself

Never compare artifacts produced by different packagers and attribute the difference to the format.
For the same base model, one packager shipped **180 TQ tensors + 258 Q8_0** while another shipped
**480 TQ + Q6_K**. Any comparison across those measures packaging, not quantization.

**Rule:** one base file, every arm produced locally with the same tool and the same flags, one
variable changed at a time. `--pure` when isolating format; pin `--token-embedding-type` and
`--output-tensor-type` identically across arms when isolating body tensors.

Public files are for *auditing claims*, never for *generating* our own comparisons.

---

## 3. Instrument choice — KLD over perplexity, and say why

PPL scores only the true token's log-probability. KLD scores the whole distribution. They disagree,
and the disagreement is not academic:

> On the Qwen3.5-4B ladder, **IQ4_XS had the best PPL ratio of any arm** (1.0087, better than
> Q5_K_S's 1.0222) while ranking **4th of 5 on median KLD**. Ranking by perplexity alone would
> conclude IQ4_XS beats Q5_K_S, which the distributional evidence contradicts.

See `Instrument_Disagreement_PPL_vs_KLD.md`. Use PPL only as a secondary, and label it as such.

KLD has a second property worth exploiting: **contamination is impossible by construction.** It
measures divergence from a reference you produced, not recall of a public answer key.

---

## 4. Report the distribution, never a single point

Mandatory for any fidelity measurement: **mean, median, 99%, max, and same-top-1.** A format can be
tight in the body and catastrophic in the tail, and the median will hide it:

> TQ4_1S had the **best 99% KLD** of the sub-5.5 bpw arms (0.330) and the **worst maximum of any
> arm (19.35)**.

This also determines which statistic a comparison is allowed to use. Mean KLD is tail-weighted;
median is not. If an external result uses mean and ours uses median, that difference must be stated
before the numbers are placed side by side.

---

## 5. Measure the property, do not read the label

Derive quantities from the artifact, not from its name or its metadata:

- **bpw from tensor offsets**, not from the type name. Prediction P-F4 (0.85 confidence) asserted
  measured bpw would exceed nominal; per-type bpw was *exactly* nominal on every arm. The intuition
  held only at whole-file level, which was not what was being measured.
- **File size is not tensor content.** `--pure Q4_K_S` and `--pure Q4_K_M` produce byte-identical
  tensor data differing only in the `general.file_type` KV.
- **Byte comparisons across GGUFs must align to each file's own data section.** Supplying
  `--imatrix` adds four `quantize.imatrix.*` KVs that shift the data region by 256 bytes; comparing
  from a fixed offset guarantees a spurious mismatch. This produced a wrong verdict — "TQ *does* use
  the imatrix" — that was only corrected by per-tensor offset-aware hashing (`cmp_tensor.py`).

---

## 6. Mode is an axis, not a setting

Enumerate modes from the model's own chat template rather than a hardcoded list, and report all
modes. Owned in full by `Protocol_Reasoning_Mode_Eval.md` and `Protocol_Mode_Recovery_Eval.md`; do
not restate them in campaign specs, cite them.

---

## 7. Repetition — K=1 is an existence proof, not a rate

**Single runs establish that something *can* happen. They never establish how often.**

- HA-04 on `.73` at temp 0 produced **35 / 100 / 100 / 35** across four runs. Temp-0 is not a
  reproducibility guarantee.
- On 2026-08-04 an unrelated `test-backend-ops` case (`q5_1`, `ERR 0.000534801 > 0.000500000`) failed
  **once in five identical runs**. The suite has real run-to-run variance on this hardware.

**Rules.** Any claim of the form "X does not happen" requires N ≥ 5 and the count reported as
`n_observed / n_runs`. Prefer **pass^k** (all k succeed) over **pass@k** (any k succeeds) for
reliability claims — pass@k rewards the lucky run and is the metric leaderboards optimise. When a
single run is all that is affordable, label the result an existence proof in the receipt.

A useful corollary from today: when a bisect lands on a commit whose diff has **no causal path** to
the observed failure, suspect a latent defect being *exposed* rather than *introduced*, and test the
clean side repeatedly before reporting a cause.

---

## 8. Pre-registration and honest scoring

Before a run, write predictions with explicit confidences into the receipt. After, score every one
including the falsifications, and state the reasoning error rather than only the outcome.

This is not ceremony — it is the only mechanism that catches mid-course rationalisation. Worked
example from 2026-08-04: P-D2 predicted a NaN would reproduce (0.60); after seeing that the test
targeted branch-exclusive code I revised *downward* to P-D4 "will not reproduce" (0.45). The
revision was wrong and the original reasoning was right — the gate argument applied only to the CUDA
path and never bore on the CPU reference where the fault actually lived. Without both predictions on
record, that self-correction would have been invisible.

**Retractions stay visible.** If a claim was published or pasted before being corrected, the receipt
keeps the retraction rather than silently editing.

---

## 9. Environment must be recorded with every receipt

Minimum set, because each has already changed a result somewhere in this lab:

| field | why |
|---|---|
| build commit + branch, and whether the tree was dirty | two builds of "the same" fork differed by a merge and produced coherent vs garbage output |
| exact flags, including `-ngl`, `-sm`, `-fa`, `-ctk`/`-ctv`, `-ub` | the `-ub 64` and `-fit off` recipes are hardware-mandatory, not stylistic |
| GPU clock + power cap | the P100 fleet boots 150 W / 1063 MHz since 2026-07-17; pre-change receipts are autoboost-1328 and are not comparable |
| **node timezone** | `.194` runs **UTC**, `.73` and the control plane run **EDT**. Cross-node timelines can appear four hours and a date boundary apart with no clock drift at all |
| env vars that change the code path | `GGML_TQ_NATIVE=1` switches which kernel runs; a default-flag "TQ decode" number is a q8_0 number |
| scored-token count and corpus | 5,100 vs 15,400 tokens is a different error bar on the same claim |

## 10. Provenance of anything not built here

Record where a third-party artifact came from *before* reporting a result about it — clone origin,
remote actually fetched from, and commit author. A regression report this lab filed was built from a
clone whose `origin` was a fork-of-a-fork; the tested commits were in fact the upstream maintainer's
own objects fetched from a second remote, but that was only demonstrable because it had been
recorded. Volunteering provenance removed the one ambiguity the maintainer would otherwise have
raised.

Corollary: a commit that is reachable today may not be tomorrow. If a finding depends on a branch
someone else controls, **archive the artifact into this repo**, not a link.

---

## 11. Delegation checklist

When a run is executed by another agent, the following must come back or the result is not accepted:

1. **The raw artifact path**, not a summary of it. Summaries cannot be re-checked.
2. **The positive-verification evidence from §1** — the grep and its count, showing the measurement
   ran.
3. **`n_observed / n_runs`** for any negative claim (§7).
4. **The environment block from §9.**
5. **Which predictions were scored, and the falsifications** (§8).

A delegated result that reports only "passed" or "no errors found" fails this checklist by
construction, because those are exactly the strings failure mode (b) produces.
