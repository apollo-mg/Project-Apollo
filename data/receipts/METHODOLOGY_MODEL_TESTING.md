# How we test models -- a game plan, written from 2026-09-19's failures

Every rule below cost something today. None are general principles borrowed from elsewhere;
each has a receipt behind it.

---

## 0. Decide which question you are asking, first

**Fidelity and behaviour are different measurements and they disagreed today.**

| | fidelity (KLD vs a fixed reference) | behaviour (task/agentic) |
|---|---|---|
| Bonsai 2 vs GSQ-RCO | Bonsai **77% worse** | Bonsai **better** (10/15 vs 8/15) |
| cost | ~16 min/cell, cheap, continuous, sensitive | ~50 min/arm, binary per item, saturates |
| answers | "how far did the distribution move" | "does it still do the job" |

**Neither is a proxy for the other.** `lowbit-ladder/RESULT_LADDER.md` and
`agentic-ladder/RESULT_PANEL.md` measured the same seven files and ranked them differently.
Pick the question before picking the instrument.

---

## 1. Freeze the reference and the invocation. Never vary them.

`ref.kld` has not moved since the EXL3 campaign. Today's P-L0 reproduced it **to every printed
digit including the 99th-percentile tail (0.000038)** weeks later, which is why an 18-point
benchmark deflation cannot touch those numbers.

- one reference, pinned by **sha256 and byte count**
- one corpus, pinned by sha256
- one flag set, copied verbatim -- **never reconstructed from a similar run**

**Cost of ignoring this:** two of today's four gate failures came from assembling a serving
command by analogy (wrong binary, then `-sm tensor` instead of `-sm layer`) instead of reusing the
invocation already proven on those exact files.

---

## 2. Every number carries its instrument version

Node, binary + commit, seed, sampling config, corpus version. No exceptions.

**Evidence:** Artificial Analysis moved Qwen3.8-27B **52 -> 41 -> 34 across three index versions
in 30 days** with the weights unchanged, as four of ten evaluations were swapped. The whole index
deflated 12-18 points. A score without its version has a shelf life of weeks.
(`agentic-ladder/FINDING_INSTRUMENT_VERSION.md`)

**Our own version of the same error:** temp-0 determinism proved 15/15 on `.73` and **did not
transfer to `.194`** -- different GPU count means a different layer split and reduction order.
A cross-machine comparison had already been written down as a finding before the control caught it.

---

## 3. Preregister, and keep expectation separate from prediction

Write predictions, falsification conditions and thresholds **before any data**. Then:

- when the data shifts your expectation, **record the shift without editing the prediction**
  (`PREREG_CODEC_LADDER.md` Amendment 2 did this: "I now expect P-L2 to be FALSIFIED", prediction
  untouched, later scored as wrong)
- when partial data makes two predictions **mutually exclusive**, say so before the deciding cell
  runs (Amendment 3), not afterwards where it reads as hindsight

Today's score: fidelity ladder **5 of 6**, agentic panel **0 of 3**. Both are reportable.

---

## 4. Gate first. A gate that runs last can void everything before it

P-L0 (reference reproduces against itself) and P-A0 (two passes agree) both ran **first**, by
design. P-A0 returning 15/15 identical verdicts *and* tool paths collapsed the noise floor to zero
and cut the panel from 3-5 passes per arm to **one**.

State the stopping rule in advance: *if the gate fails, stop and report the instrument, not the
subject.*

---

## 5. Build controls that can void your own result

Two controls each caught a wrong finding today, for about 40 minutes apiece:

- **C-XBIN** -- same model, both binaries. Agreed to 3.1e-5, so the cross-binary comparison was
  valid. It was not assumed.
- **the replication arm** -- same model, different machine. **Diverged**, invalidating a
  cross-machine comparison already stated as a finding.

A control is worth its cost when it is capable of overturning the headline. If it cannot, it is
decoration.

---

## 6. Report EFFECTIVE N, not nominal N

A 15-item corpus where 13 items are passed-by-all or failed-by-all has **N = 2**.

Today's panel: 8 saturated easy, 5 saturated hard, **2 discriminating**. The entire 67/57/53
spread was two scenarios. A ranking built on two items is not a ranking, and the receipt says so
instead of quoting the headline rate.

**Partition every corpus this way and print it.** `tools/score_agentic_panel.py` does.

---

## 7. Calibrate a corpus before measuring with it -- and match the criterion to the sampling

`CORPUS_DESIGN_v1` asks for n=5 on a reference config, keeping items at **1-4 clean of 5**.

**That criterion cannot exist at temp 0**, where a deterministic run is 0/5 or 5/5. The temp-0
analogue is **"items where ARMS disagree"**, which is what effective N measures.

| regime | keep an item if |
|---|---|
| temp > 0 | 1-4 clean of 5 **runs** |
| temp 0 | **arms** disagree on it |

A corpus is only calibrated **for a model and a sampling regime**. Both drift.

---

## 8. Root-cause every failure before interpreting any of them

Mark's instruction, and it changed today's reading. The anchor scored 10/15 -- suspiciously low
for a model that benchmarks near frontier. Auditing the five universal failures:

**3 genuine, 1 by-design coin-flip, 1 arguably harsh.** All five were the same class: scenarios
whose correct answer is *ask, do not act*. **The models were failing at caution, not capability** --
a different axis from what capability suites reward, and the reason the low score was not a
harness bug.

Ask specifically: *is this the model erring, or my grader being unfair, or my environment broken?*
The verdict taxonomy must separate those (`TOOL-FAIL`/`INFRA` are VOID, not failures).

---

## 9. Pre-flight everything checkable in under a minute

Four configuration faults cost four cycles today. Each was a one-minute check:

- **does this binary support this format?** (buun cannot read types 142/143 -- and reports it as
  "failed to read tensor info", which looks like file corruption)
- **do these flags work for this model?** (ternary aborts `-sm tensor` *after* loading to VRAM)
- **is the fixture current?** (a stale world makes scenarios unsatisfiable)
- **does the host compiler match the toolkit?** (CUDA 12.4 hard-errors above gcc 13)

And verify **rendered output**, not configuration: today's chat-template check rendered both
templates and compared hashes rather than reading the jinja. `medium` was byte-identical; `high`
raised on one side. Reading would have missed it.

---

## 10. Never conclude from a derived view when the raw value exists

Four instances today, every one wrong:

| derived view | conclusion | truth |
|---|---|---|
| `%.1fM` rounding | "all binaries are zero bytes" | 15,960 bytes |
| a plausible story | "I took down `.73`" | `sar` showed the cascade began 2 min before my script |
| truncated 130-char log field | "7 identical tool calls, a runaway" | 8 **distinct** calls, task solved correctly |
| one slow scenario | "7 min/scenario, 3.5 hours" | 190s mean, half that |

`grep -c` prints `0` **and** exits 1, so `|| echo 0` fires too. `pgrep -c` does the same. The
harness shell is **zsh**, which does not word-split unquoted parameters. Check the raw value.

---

## The standing checklist

**Before:** question chosen · reference + invocation frozen and hashed · prereg committed ·
gate defined with a stopping rule · controls that can void the result · pre-flight passed

**During:** record PIDs at launch, never search a process list you are inside · bound every
external command that can hang (`timeout 10 nvidia-smi`) · a probe must not share a failure mode
with its subject

**After:** root-cause failures before interpreting · report effective N · score every prediction
including the wrong ones · attach the instrument version to every number · corrections go in the
history, not over the top of the original
