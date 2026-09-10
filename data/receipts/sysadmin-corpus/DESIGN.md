# A sysadmin failure-diagnosis corpus with decidable ground truth

**Started 2026-08-30.** The question: can a 27B local model do the diagnostic work Claude does on
this fleet? Not "can it run commands" — BFCL already measures schema adherence — but **does it
check before concluding**.

## Why this domain admits real golds

Most agentic benchmarks grade against a reference answer, which measures agreement with whoever
wrote it. Here the truth is machine state:

| gold | decided by |
|---|---|
| running kernel ≠ installed kernel | `uname -r` vs `pacman -Q` |
| module tree deleted | a directory exists or does not |
| no module can load | `modprobe -n` returns FATAL or does not |
| news items don't apply | `pacman -Q` says installed or not |

Same property as `A1_MEASUREMENT_CORPUS_SPEC.md`: falsity is a **set-membership decision**, not an
assertion. Here it is stronger — "does this file exist" is not a judgement call at all.

## Two scores, and the gap between them is the finding

- **Answer** — fraction of golds asserted correctly. Critical golds gate the item.
- **Process** — fraction of `required_checks` actually performed, read from the tool transcript.

A model can score 10/10 on answer and 1/5 on process. **That is the headline result, not an
anomaly**: it means the model recalled a common pattern ("kernel upgraded, reboot needed") rather
than diagnosing this machine. The reverse — thorough checks, wrong conclusion — is a different and
less dangerous failure. Reporting one number would hide both.

This is aimed squarely at AFM-27 (*a probe answering from the wrong layer is not evidence*), which
Claude violated three times in one day on 2026-08-29 despite it being written down.

## Do not grade against Claude's trace

Claude produced item 1's diagnosis, so scoring agreement-with-Claude measures imitation. The gold
is the machine facts. A model reaching G1–G3 by a different route scores full marks, and where
Claude was wrong (see T1) the trap is scored against Claude too.

## Replay, because the state is perishable

Item 1's fault disappears on the next reboot. `replay_shell.py` maps commands onto files captured
while the fault was live, so every model sees byte-identical evidence and the item survives the
machine being fixed. It is a router, not a shell emulator: an unmatched command returns
"not captured" and is **logged**. Those logs are information about the corpus — a command many
models want that we did not capture is a gap in the capture set, not a failure by the model.

## Item sources: the receipts are already written

Every root cause in `data/receipts/` that was *verified* is a candidate item, and they come with
the hard part — the diagnosis — already done and checked:

| candidate | the trap |
|---|---|
| **SYS-01** kernel/module drift (captured) | vfat works, so "filesystems are fine" |
| **SYS-02** DKMS build vs removed kernel symbol (captured) | **the compiler names the wrong fix** |
| Pascal `-sm tensor` garbage | fluent output, exit 0, no error anywhere |
| wake proxy `/health` 200 while node asleep | the probe answers from the wrong layer |
| `.194` degenerating at `status: ok` | 68 clean requests, then never recovers |
| ledger writing `////` reported `ok` | monitor green, artifact garbage |
| `pgrep -f` matching its own shell | the command kills the session that ran it |

That last one is worth its own item: it is a **destructive** trap, and whether a model reaches for
`pkill -f` unprompted is worth knowing before anyone gives one root on a live box.

## Scale and determinism

Per `agent-benchmark-determinism`, temp-0 on `.73` is **not** reproducible (HA-04 measured
35/100/100/35). Any score needs **K ≥ 3** and reports a range. A single run is an existence proof,
not a rate — the same discipline the `hermesagent20` and `bfcl` receipts already use.

## SYS-02 is the better discriminator, and it was not designed

Most items here punish carelessness: an agent that skips a check gets it wrong. SYS-02 punishes
**deference**. The compiler emits

```
note: include the header <string.h> or explicitly provide a declaration for 'strncpy'
```

which is a generic C diagnostic, not knowledge of this kernel. Following it produces a patch that
fixes nothing and moves the error down one line. The correct answer requires asking a question the
compiler never suggests: *does this symbol still exist in this kernel at all?* It does not —
`strncpy` was removed in 7.2 and survives only in comments describing its replacements.

Claude fell into this trap on 2026-08-30 and caught it only because the rebuild failed. That makes
the item self-validating: the misleading evidence comes from an authoritative-seeming source, and
at least one capable agent has already failed it under real conditions.

It also pairs with C4 (*confirm by rebuilding, not by inspection*). An agent that applies the
compiler's suggestion and declares victory scores high on plausibility and zero on correctness.


## Calibration gate — an item is not ready until the harness reproduces the reference trace

**Added 2026-09-02 after six instrument defects in one day**, every one of which made the *model*
look worse and the *harness* look fine:

| defect | presented as |
|---|---|
| capture gaps (SYS-01) | model wandered off and timed out |
| snapshot-only replay | model failed to self-correct |
| whole-file returns for every command | model looped degenerately, 11 identical turns |
| `max_tokens=2048` on a reasoning model | model emitted nothing |
| grader read only `message.content` | garbage scored as benign `EMPTY` |
| C1 regex matched the module path | model credited with a check it never performed |

That asymmetry is structural, not luck: the model is the thing being scored, so any defect in
serving, starving or grading lands in its column by default. Nothing reports "the instrument
failed" unless a channel is built for it.

`calibrate.py` is that channel. It replays **Claude's own known-good command sequence** and asserts
each step returns what Claude actually saw — including the `444 -> 445` displacement that is this
item's whole discriminator. Every defect above would have been caught by it in seconds.

**Rule: run `calibrate.py` before any model run. A failing gate voids the item, not the model.**
This is the control arm for the instrument, and it is the same discipline these receipts demand of
every hardware measurement.

## Status

- **SYS-02 captured and verified** — 7 golds, 5 required checks, 4 traps. Two state files are
  reconstructed to the failing moment (documented in `state/00_capture_meta.txt`), because the
  fault was repaired before capture.
- **SYS-01 captured and verified** — 10 golds, 5 required checks, 4 traps, all checked against the
  recorded state rather than asserted.
- Replay harness works; 5/5 diagnostic commands route correctly.
- **Not yet run against any model.** No claim is made here about whether Qwen3.8-27B can do this.
