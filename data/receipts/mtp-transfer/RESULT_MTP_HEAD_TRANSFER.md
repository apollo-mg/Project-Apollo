# An MTP head transfers across fine-tunes of the same base -- and on one domain drafts BETTER than for its own model

**2026-09-22. RX 9070 XT (gfx1201), upstream llama.cpp build 11095 (`58367713a`), `build_rocm`.**
Answers `PREREG_MTP_HEAD_TRANSFER.md` (written 09-21, blocked same day, amended and unblocked 09-22).

**Prior art:** the prereg's own check found every MTP number this project holds used a head shipped
**with its own target**. None asked whether a head trained against fine-tune A drafts for fine-tune
B of the same base. That is what this measures.

## Setup

One head file drafts for both targets. The only variable across the two `mtp` arms is the target.

| | MiMo-V2.6-Distill-Qwen-9B Q8_0 | Ornith-1.5-9B Q8_0 | Ornith MTP head Q8_0 |
|---|---:|---:|---:|
| packager | bartowski | bartowski | ornith-ai |
| bytes | 9,545,979,424 | 9,545,982,848 | 2,430,895,232 |
| tensors / blocks | 427 / 32 | 427 / 32 | 18 / head at `blk.32` |
| embedded MTP head | none | none | -- |

The two targets are **3,424 bytes apart**, same packager, same quant, both with `ssm_alpha` /
`ssm_beta` at F32. bartowski ships **no** MTP head in either, so the standalone head is the drafter
for both arms.

`-ngl 99 -ngld 99 -c 4096 -fa on -ctk f16 -ctv f16 -np 1`, `--spec-type draft-mtp -md <head>`,
temp 0, `cache_prompt: false`, `enable_thinking: false`, `max_tokens` 400, warmup discarded,
3 reps per cell, 36 rows. Raw: `raw_mtp_matrix.jsonl`.

## Result

| domain | target | acceptance | no-spec tok/s | spec tok/s | speedup | text identical to no-spec |
|---|---|---:|---:|---:|---:|---|
| PROSE | Ornith (matched) | 0.313 | 54.17 | 64.37 | 1.19x | no |
| PROSE | MiMo (transfer) | **0.274** | 55.64 | 60.43 | 1.09x | no |
| CODE | Ornith (matched) | 0.658 | 55.71 | 97.81 | 1.76x | no |
| CODE | MiMo (transfer) | **0.653** | 55.08 | 98.25 | 1.78x | no |
| STRUCT | Ornith (matched) | 0.869 | 55.26 | 117.45 | 2.13x | **YES** |
| STRUCT | MiMo (transfer) | **0.918** | 54.80 | 124.38 | 2.27x | no |

Every cell is stable to the third decimal across 3 reps with identical output hashes.

## The headline: the head transfers, and is never net-negative

**A head trained against Ornith-1.5-9B drafts usefully for MiMo-V2.6-Distill-Qwen-9B**, a different
fine-tune of the same `qwen35` 9B base. It loads without complaint and delivers **1.09x to 2.27x**.
There is no domain where the cross-tune drafter costs throughput.

**P5 falsified** (0.50 confidence): the transfer arm was predicted to be slower than no speculation
on at least one domain. It is faster on all three.

## P2 falsified: on STRUCT the cross-tune head beats the matched one

Predicted at **0.85**: acceptance(transfer) < acceptance(matched) on all three domains.

| domain | matched | transfer | delta |
|---|---:|---:|---:|
| PROSE | 0.313 | 0.274 | **-0.039** |
| CODE | 0.658 | 0.653 | -0.005 |
| STRUCT | 0.869 | **0.918** | **+0.049** |

The ordering holds on prose, is within noise on code, and **inverts on structured output**. The
intuition that a head drafts best for the model it was trained on is wrong here, at least on JSON.

### ...but this comparison carries a confound that must not be skipped

**Acceptance is measured over each target's own generated text, and the two targets do not write
the same text.** On STRUCT, Ornith emits 655 characters and MiMo 475 -- different JSON, different
token sequences. So the cross-arm comparison is *"different model, different output, same
drafter"*, not *"same text, different drafter"*.

MiMo's higher acceptance is therefore partly a statement about **what MiMo chose to write** (shorter,
plausibly more stereotyped JSON) rather than purely about how well the Ornith head models it. The
direction of P2's falsification is real -- the transfer arm genuinely accepted more drafts on this
domain -- but the *cause* is not isolated.

A clean version forces both targets through identical token sequences (teacher-forced acceptance
over a fixed corpus) rather than free generation. **Not run.** Until it is, the honest claim is the
weak one: **a cross-tune head is not reliably worse, and on at least one domain it is better.**

## Content type dominates everything else

**P4 confirmed** in both arms, cleanly monotonic:

```
Ornith   PROSE 0.313  <  CODE 0.658  <  STRUCT 0.869
MiMo     PROSE 0.274  <  CODE 0.653  <  STRUCT 0.918
```

Acceptance spans **0.27 to 0.92** -- a 3.4x range driven purely by what is being written. The
matched-vs-transfer gap (0.005 to 0.049) is **an order of magnitude smaller than the
prose-vs-JSON gap** (0.56 in the same arm. If you are choosing where to spend effort on
speculative decoding, the workload's content type matters far more than whether the drafter came
from exactly the right fine-tune.

## Bit-exactness: 1 of 6 cells reproduced, and acceptance does not predict which

`spec-decode-determinism/RESULT_SPECULATION_IS_NOT_BIT_EXACT.md` (08-18) established that
speculation does not reproduce non-speculative output on this stack. That holds in **5 of 6 cells**
here, on a new architecture (**P3' confirmed**, replacing the prereg's withdrawn P3, which had
predicted byte-identity at 0.90 against an already-published finding).

The exception is **Ornith/STRUCT**, where head-on and head-off produce byte-identical text
(`2a89d8e121456f4a`), stable across all 6 reps.

**An intermediate hypothesis of mine is falsified by this table.** On seeing that cell I suggested
bit-exactness tracks acceptance -- high-confidence content has wide argmax margins, so the
numerical perturbation speculation introduces cannot flip the top token. **MiMo/STRUCT has *higher*
acceptance (0.918) and does *not* reproduce.** Acceptance does not predict reproducibility. With
one reproducing cell out of six and no working mechanism, the right description is: rare,
content-dependent, and currently unexplained.

## Predictions

| id | prediction | conf | outcome |
|---|---|---|---|
| P1 | head loads against Ornith | 0.80 | **CONFIRMED** |
| P6 | head loads against MiMo (transfer) | 0.85 | **CONFIRMED** |
| P-A1 | matched acceptance 0.45-0.65 on prose | 0.70 | **FALSIFIED** -- 0.313 |
| P2 | transfer < matched on all three domains | 0.85 | **FALSIFIED** -- STRUCT inverts |
| P3' | stable but different output per arm | 0.80 | **CONFIRMED 5/6**, Ornith/STRUCT identical |
| P4 | PROSE < CODE < STRUCT in both mtp arms | 0.70 | **CONFIRMED** both arms |
| P5 | transfer slower than no-spec somewhere | 0.50 | **FALSIFIED** -- faster everywhere |

**P-A1 was mispredicted because of a confound I introduced.** Its 0.45-0.65 band came from a single
warmup probe reading 0.504, taken before `enable_thinking: false` was pinned. That probe was
drafting **reasoning text**, which accepts far better than prose. With thinking off, prose is 0.313.
The prediction was derived from a contaminated observation and the amendment recorded it as such,
which is the only reason the error is visible now.

## Two measurement defects found and corrected mid-run

Both are recorded because each produced plausible, stable, wrong numbers.

**1. Thinking-on made two of three domains measure reasoning text.**
The first pass ran without `enable_thinking: false`. CODE returned
`sha=e3b0c44298fc1c14` -- sha256 of the **empty string** -- with `text_len=0` and HTTP 200, all 400
tokens spent on `reasoning_content`. PROSE returned 60 characters for 256 tokens. So two cells
measured acceptance on reasoning, not on the domain in their label. Effect is material: prose
acceptance **0.415 (contaminated) vs 0.313 (clean)**. `[[thinking-off-in-harnesses]]` states this
verbatim and it was not applied. Raw kept at `raw_CONFOUNDED_thinking_on.jsonl`. The runner now
aborts any cell returning empty content.

**2. Nine rows labelled `MIMO-off` were `MIMO-mtp` measurements.**
Two copies of the orchestration script ran concurrently -- an earlier chained launch wrongly
believed dead, plus a replacement. Their servers collided on port 8090; the second failed to bind
and the health check then passed against the **first**, so the no-speculation arm was measured
against a speculating server. The rows carry `draft_n=423` and hashes byte-identical to the mtp
arm. Raw kept at `raw_MISLABELLED_off_arm.jsonl`.

**`/health` returned 200 and `/props` reported the correct `model_path`. Both true, both useless:
neither says whether speculation is active.** The discriminating probe is `draft_n` in the response
body, and the runner now asserts `bool(draft_n) == arm.endswith("-mtp")` and aborts otherwise.
`[[readiness-probes-lie]]`, and the port-collision half is `[[orchestration-chaining-lessons]]`
almost verbatim.

## What this does not establish

- **One head, one base family, one card, one quant.** No claim that MTP heads transfer in general.
- **Nothing about either model's quality.** Acceptance is a drafter-agreement metric.
- **The cross-arm acceptance comparison is not text-matched** (see the confound above).
- CODE cells hit `fin=length` at 400 tokens. Acceptance is a per-token rate so the figures stand,
  but those are truncated generations.
- The standalone head's `blk.32` is **not** byte-identical to the head embedded in the other
  packager's Ornith build, though all 15 tensors match type and size. Q8_0 is deterministic and
  heads are quantised blind, so different bytes imply different source weights or precision. The
  "matched" arm is matched by *model*, not by *conversion*.

## Practical note

The head costs **2.42 GB of VRAM** but its MTP block is only **258 MB**. The remaining 2.16 GB is
`token_embd` (1.08 GB) plus `output` (1.08 GB), duplicating tensors already in the target. On a
16 GB card that duplication is what forced context down to 4096 (12.43 GiB used, 3.49 GiB free).
A head packaged without the embedding and output tensors would cost ~9x less VRAM.

# ADDENDUM 2026-09-22 -- the base model settles it, text-matched

The stock base, `bartowski/Qwen_Qwen3.5-9B-GGUF` Q8_0 (9,804,541,984 B, byte-exact to the HF blob,
sha256 `b58fe056b5435070240de259f3f981aa38fee96825bbd78c088d5fd90e46f2b5`), arrived after the above
was written. It is the **common ancestor of both fine-tunes**, and unlike them it **ships its own
MTP head** (442 tensors, 33 blocks, `nextn.*` present).

That buys two things the first matrix could not: a **true matched drafter**, and -- as it turned
out -- a **text-matched comparison**. Raw: `raw_base_matrix.jsonl`.

## The trap checked first

With a target that already carries an embedded head, it is not obvious whether `-md` overrides it
or is silently ignored. If ignored, the "borrowed head" arm would be measuring the embedded head
twice. **It is not ignored:** acceptance differs in every domain (0.454 vs 0.390 on prose), and
each server's `/proc` cmdline was printed at launch. The external head is genuinely in use.

## Result

| domain | arm | acceptance | tok/s | speedup | output sha |
|---|---|---:|---:|---:|---|
| PROSE | no speculation | -- | 55.72 | 1.00x | `e11299b7` |
| PROSE | **own** embedded head | **0.454** | 78.15 | **1.40x** | `c2170b6f` |
| PROSE | **borrowed** Ornith head | **0.390** | 72.67 | **1.30x** | `c2170b6f` |
| CODE | no speculation | -- | 55.85 | 1.00x | `82cbc157` |
| CODE | **own** | **0.698** | 103.18 | **1.85x** | `51488053` |
| CODE | **borrowed** | **0.658** | 99.27 | **1.78x** | `51488053` |
| STRUCT | no speculation | -- | 55.97 | 1.00x | `71ff9ed9` |
| STRUCT | **own** | **0.891** | 121.09 | **2.16x** | `b52059e4` |
| STRUCT | **borrowed** | **0.871** | 118.72 | **2.12x** | `b52059e4` |

## 1. An MTP head is a base-family asset

**A head trained on Ornith-1.5-9B drafts for the stock base it was fine-tuned from**, at
**1.30x-2.12x**. Combined with the MiMo result above, one head now drafts usefully for **three
different models** in the `qwen35` 9B family: its own fine-tune, a sibling fine-tune, and the
shared base.

This reframes the practical finding. Neither fine-tune ships an MTP head (427 tensors) while the
base does (442). The fine-tune repos do not publish MTP weights at all, so the likely story is
that **fine-tuning discards the base's MTP head and nobody re-attaches it** -- not that any
packager dropped it. An earlier framing in this session blamed the packager and was wrong:
bartowski ships the head whenever the source has one.

## 2. Text-matched: the matched head wins everywhere, and the STRUCT inversion above was the confound

The two speculative arms produced **byte-identical output** in all three domains. Same target,
same generated tokens, only the drafter differs -- exactly the comparison the MiMo-vs-Ornith table
could not support, and which that section flagged as missing.

| domain | own head | borrowed head | delta | retained |
|---|---:|---:|---:|---:|
| PROSE | 0.454 | 0.390 | **-0.063** | 86.0 % |
| CODE | 0.698 | 0.658 | **-0.040** | 94.3 % |
| STRUCT | 0.891 | 0.871 | **-0.020** | 97.7 % |

**The matched head is better on all three domains, on identical text.** So P2's *direction* is
right, and the STRUCT inversion in the main matrix (transfer 0.918 > matched 0.869) is best
explained by the confound named there: MiMo and Ornith wrote different JSON (475 vs 655 chars), so
that was never a drafter comparison. **The caveat was load-bearing, and the clean test vindicates
it rather than the headline.** P2 remains falsified as literally written -- the inversion is real
in that data -- but it should not be read as evidence that a borrowed head can beat a matched one.

**A borrowed head retains 86-98 % of matched acceptance**, and the retention *rises* with how
constrained the content is. On JSON the penalty for using the wrong head is 2 points.

## 3. The drafter does not change the output; the speculative path does

| comparison | same text? |
|---|---|
| own head vs borrowed head | **identical, all 3 domains** |
| speculation off vs on | **different, all 3 domains** |

This is a sharper statement than `spec-decode-determinism/RESULT_SPECULATION_IS_NOT_BIT_EXACT.md`
(08-18) could make with one drafter. Speculative decoding is distribution-preserving by
construction -- the verify step rejects bad drafts -- so **which** drafter proposed a token cannot
change what is finally emitted, and here it demonstrably does not, across two heads differing
enough to move acceptance by 6.3 points. What *does* change the output is **turning speculation on
at all**: the batched verify path is numerically different from sequential decode.

So the 08-18 finding is not "speculation is nondeterministic". It is **"the speculative code path
is a different numerical path from the non-speculative one, deterministically so"**. Two drafters
land on the same altered text.

This also retires the intermediate hypothesis recorded above. Having seen Ornith/STRUCT reproduce
byte-identically, this receipt speculated that bit-exactness tracks acceptance via argmax margin.
Here all three base domains diverge from non-speculative **including STRUCT at 0.891 acceptance**,
higher than the Ornith/STRUCT cell that did reproduce. That one cell is a coincidence of margins,
not a rule. **Acceptance does not predict reproducibility; the hypothesis is dead.**

## What the addendum still does not establish

- One base family, one card, one quant, three targets. No claim about MTP heads in general.
- Acceptance is a drafter-agreement metric, not a quality metric.
- The base's own head and the standalone Ornith head are both Q8_0 but are different files; part of
  the 86-98 % retention could be conversion differences rather than fine-tune drift.
- `n = 3` reps per cell, all identical to the third decimal. Stable, but a single prompt per domain.
