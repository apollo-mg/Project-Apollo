# The MTP draft head is quantised blind — no imatrix covers it in either ladder

**Date:** 2026-08-15 · **Method:** GGUF headers read over HTTP range requests
(`modules/gguf_librarian.py probe`) — no weights downloaded. 8 files totalling
**133 GiB on the hub, 96 MiB actually transferred.**
**Sources:** `bartowski/Qwen3.8-27B-GGUF`, `unsloth/Qwen3.8-27B-GGUF`, same base model
(`Qwen/Qwen3.8-27B`), both published within a day of launch.

## The finding

Qwen 3.8 27B ships an MTP (multi-token prediction) self-speculation head as a block of 8
tensors named `blk.64.*`, including `blk.64.nextn.eh_proj.weight`. It is what
`--spec-type draft-mtp` runs as the draft model. A packager can quantise it independently of
the body, and **these two do so on completely different principles**:

| packager | file | size | **MTP draft head** | body |
|---|---|---|---|---|
| bartowski | `Q6_K` | 21.85 G | **`Q4_0` x8** | Q6_K x280 + Q8_0 x120 |
| bartowski | `Q4_K_M` | 16.55 G | **`Q4_0` x8** | Q4_K x248 + Q6_K x96 + Q5_K x32 + Q8_0 x24 |
| bartowski | `IQ3_XXS` | 11.76 G | **`Q4_0` x8** | IQ3_XXS x288 + Q5_K x48 + Q8_0 x24 + IQ3_S x16 + ... |
| bartowski | `Q8_0` | 27.12 G | `Q8_0` x8 | Q8_0 x400 |
| unsloth | `Q6_K` | 21.31 G | **`Q6_K` x7 + `Q8_0` x1** | Q6_K x352 + Q8_0 x48 |
| unsloth | `UD-Q6_K_XL` | 24.14 G | `Q8_0` x6 + `Q6_K` x2 | Q8_0 x272 + Q6_K x128 + Q5_K x96 |
| unsloth | `UD-IQ3_XXS` | 11.10 G | `IQ4_XS` x5 + `IQ3_S` x3 | IQ3_S x192 + IQ4_XS x144 + IQ3_XXS x112 + IQ1_M x48 |
| unsloth | `UD-IQ2_M` | 9.61 G | `IQ4_XS` x5 + `IQ3_S` x3 | IQ3_XXS x224 + IQ1_M x96 + IQ3_S x96 + IQ2_S x64 + ... |

**bartowski pins the head at `Q4_0` in every tier except `Q8_0`. unsloth scales it with the
model.** At the `Q6_K` tier that is a two-bit difference in the draft head between two files
carrying the same label.

Note the direction reverses at the bottom: at `IQ3_XXS`, bartowski's `Q4_0` head is *higher*
precision than the body it drafts for, while unsloth's `IQ4_XS`/`IQ3_S` head is in line with
its body. This is not "one packager is careless." It is two different policies — fixed-type
head versus tier-scaled head — that happen to converge at 4-ish bits and diverge at 6.

## Why this is not just trivia

Speculative decoding pays only if drafts are *accepted*. Acceptance is a property of the
draft model, and here the draft model is those 8 tensors. So **the MTP speedup is a function
of a component the label does not describe and the packager chose independently.**

This fleet measured MTP as a clear win on unsloth files:

| node | off | on | speedup | file |
|---|---|---|---|---|
| RX 9070 XT (RDNA4) | 27.09 | 55.40 | **2.05x** | unsloth |
| 2x P100 (`.73`) | 8.58 | 13.00 | **1.52x** | unsloth `UD-IQ3_XXS` |

Two other people report MTP making Qwen 3.8 *slower*. Both observations can be correct about
different files. **This receipt does not establish that this is the explanation** — it
establishes that the files differ in the one component that would produce that disagreement,
which makes it a testable hypothesis instead of a contradiction.

**Unknown and material: which files those reports used.** Nobody has been asked. That is the
cheapest next step and it should happen before any test is run.

## The deeper finding: the MTP head has no importance data in either ladder

bartowski publishes his imatrix (`Qwen3.8-27B-imatrix.gguf`). Read directly, 4 MiB over the
wire: **992 entries, covering `blk.0` through `blk.63`. Zero entries for `blk.64`. No
`nextn` entries anywhere.**

`tensor_requires_imatrix()` — **identical in upstream `llama-quant.cpp` and the `buun_vbr`
fork** — returns true for `IQ3_XXS`, `IQ2_XXS`, `IQ2_XS`, `IQ2_S`, `IQ1_M`, `IQ1_S`, and for
`Q2_K` inside a `Q2_K_S` file. Targeting one of those on a tensor with no imatrix entry is a
hard abort, not a downgrade:

```
Missing importance matrix for tensor %s in a very low-bit quantization
The result will be garbage, so bailing out
```

So for every IQ-tier file, the MTP head **must** be forced to a type outside that set. `Q4_0`
qualifies. So do `IQ3_S`, `IQ4_XS`, and every K-quant. Both packagers picked from that set:

| | head type | requires imatrix? |
|---|---|---|
| bartowski, all tiers except `Q8_0` | `Q4_0` | no |
| unsloth, IQ tiers | `IQ4_XS` / `IQ3_S` | no |
| unsloth, K tiers | `Q6_K` / `Q8_0` | no |

unsloth does not publish an imatrix, so their coverage cannot be read. But their
`UD-IQ3_XXS` **body** uses `IQ3_XXS` x112 and `IQ1_M` x48 — both imatrix-requiring — while
its **head** uses only non-requiring types. That is the signature of the same gap.

**This weakens the "he has data showing 4-bit is fine" reading, without refuting it.** At the
IQ tiers `Q4_0` is close to forced. But at `Q6_K` the abort rule forces nothing — K-quants
never require imatrix, so a `Q6_K` head was freely available and `Q4_0` still shipped. The
most economical explanation is a single uniform `nextn` override applied across the whole
ladder, set at the floor the lowest tiers need. That is a pipeline-shape decision rather than
a per-tier quality judgement — **but it is not established here, and only bartowski can say.**

**The upstream gap this exposes is the more useful result:** imatrix generation does not
exercise the MTP layer, so in every published ladder examined the draft head is quantised
*blind*. Whatever the right precision for a draft head is, nobody currently has importance
data to inform the choice.

## Sealed predictions

**Sealed before the imatrix coverage above was discovered.** Left unchanged; the mechanism
turned out to be different from the one assumed when they were written.

If the MTP A/B (`data/receipts/qwen38-splitmode/raw/mtp_ab.py`, `-np 1`, temp 0) is run on
bartowski `Q6_K` against unsloth `Q6_K` on the same node:

| # | prediction | conf |
|---|---|---|
| P1 | bartowski `Q6_K` shows a **lower** MTP speedup than unsloth `Q6_K` | 0.70 |
| P2 | bartowski `Q6_K` MTP is still net-positive (>1.0x), not a slowdown | 0.65 |
| P3 | Both files' MTP-off throughput is within 5 % of each other | 0.75 |
| P4 | The gap in speedup between packagers is larger at `Q6_K` than at `IQ3_XXS` | 0.60 |

P2 is the one that matters for the reports: if bartowski's `Q6_K` is still faster with MTP
on, then draft-head quantisation is **not** sufficient to explain "MTP made it slower," and
the cause is elsewhere (build, flags, hardware).

### Second seal — acceptance rate, sealed 2026-08-15 before the run started

P1-P4 were written when throughput was the only planned measurement. The server turns out to
report **draft acceptance directly** (`timings.draft_n`, `timings.draft_n_accepted`, set at
`server-context.cpp:581`, serialised at `server-task.cpp:273`), which measures the draft head
rather than its downstream effect. Throughput is a lagging, much blunter proxy: a head can be
meaningfully worse and still show no t/s difference if acceptance stays above the point where
the verify step dominates. These are sealed with the files downloaded but the benchmark not
yet started:

| # | prediction | conf |
|---|---|---|
| P5 | unsloth's aggregate draft acceptance exceeds bartowski's | 0.75 |
| P6 | the acceptance gap is >= 5 percentage points | 0.55 |
| P7 | acceptance separates the two files more cleanly than t/s does | 0.70 |
| P8 | acceptance differs by prompt, with `repeat` (highly predictable) highest in both | 0.80 |

P7 is the methodological claim. If it fails — if throughput separates them and acceptance
does not — then acceptance is not the mediating variable it is assumed to be here, and the
mechanism story in this receipt is wrong even if the direction is right.

## RESULTS — the head barely matters, and t/s went the other way

`.73`, `-sm layer -ts 1,1`, 7 of 8 arms (`bart_off_2` pending):

| file | MTP head | off | on | multiplier | **draft acceptance** |
|---|---|---|---|---|---|
| bartowski `Q6_K` | `Q4_0` | 7.87 | 14.48 | 1.840x | **70.70 %** |
| unsloth `Q6_K` | `Q6_K` x7 + `Q8_0` | 7.69 | 13.96 | 1.817x | **71.50 %** |

| # | prediction | conf | outcome |
|---|---|---|---|
| P5 | unsloth acceptance exceeds bartowski's | 0.75 | **CONFIRMED** — 71.50 vs 70.70 |
| P6 | the gap is >= 5 pp | 0.55 | **FALSIFIED** — it is **0.80 pp** |
| P7 | acceptance separates them more cleanly than t/s | 0.70 | **FALSIFIED** — see below |
| P8 | acceptance varies by prompt, `repeat` highest | 0.80 | **CONFIRMED** — repeat 97.6 %, list 91.6 %, reason 80.9 %, code 62.7 %, prose 47.7 % |

**P7 failed in the most useful way available.** Acceptance separates the two files by 1.13 %
relative; throughput separates them by 3.7 % relative — **three times more** — and in the
*opposite direction*: bartowski has the **lower** acceptance and the **higher** throughput.
So acceptance is not the mediating variable between head quality and speed here. Something
else dominates, and the candidate is kernel cost: bartowski ships `Q8_0` x120 against
unsloth's x48, and `Q8_0` is cheaper to dequantise than `Q6_K`.

**What this does to the headline.** A two-bit difference in the draft head moved draft
acceptance by **0.8 percentage points**. Whatever else is true, the `Q4_0` head is not
costing bartowski's users anything visible — which is evidence *for* Mark's original
hypothesis (that a 4-bit MTP head is good enough) and against the concern that motivated
this receipt, even if the imatrix finding stands as the reason the choice was available.

**But this comparison still cannot isolate the head** — the bodies differ too, which is why
`PREREG_HEAD_ISOLATION.md` builds files that differ in `blk.64` alone. That experiment is now
the one that matters: if a hand-built `F16` head also lands within ~1 pp of a `Q4_0` head,
draft-head precision is simply not an important variable and the whole line closes cleanly.

## Limits

- **Header evidence only. No throughput was measured for this receipt.** Everything above is
  what the files contain, not how they behave. No claim is made that a `Q4_0` head drafts
  worse than a `Q6_K` one — only that they differ and that neither was informed by imatrix.
- **unsloth's imatrix coverage is inferred, not read.** They publish no imatrix. The
  inference rests on their head types being exactly the non-imatrix-requiring ones while
  their body uses requiring ones; that is suggestive, not proof.
- **bartowski's intent is not established.** The uniform-override reading is the most
  economical explanation of the observed types, not evidence about his process. He may well
  have validated `Q4_0` heads independently.
- The claim that imatrix generation does not exercise the MTP layer is inferred from the
  absence of `blk.64` in the published imatrix, not from reading `llama-imatrix`.
- Two packagers, one model. Nothing here says what stock `llama-quantize` defaults do, which
  is the third recipe under the same label (`gguf-label-is-not-a-spec`).
- The `blk.64` block was identified as the MTP head by the presence of `.nextn.` tensors in
  it. That matches what `--spec-type draft-mtp` loads (engagement confirmed separately by
  `[spec] estimated memory usage of MTP context is 292.03 MiB`), but the mapping was not
  traced through llama.cpp source for this receipt.
- File sizes are from `Content-Range`, not from a downloaded and hashed file.

## Method note: this cost 96 MiB

GGUF puts its tensor table at the head of the file, so the full recipe of a 27 GiB quant is
readable from its first ~12 MiB. `gguf_librarian.py probe` reads it with HTTP range requests:

```
gguf_librarian.py probe bartowski/Qwen3.8-27B-GGUF --only 'Q6_K\.gguf'
gguf_librarian.py probe unsloth/Qwen3.8-27B-GGUF --manifest /tmp/unsloth.json
```

Auditing a packager's entire 26-quant ladder is a few tens of MiB, which makes
"probe before you download" cheap enough to be routine.
