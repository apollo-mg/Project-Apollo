# Two packagers, one label, a two-bit gap in the MTP draft head

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

## Sealed predictions

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

## Limits

- **Header evidence only. No throughput was measured for this receipt.** Everything above is
  what the files contain, not how they behave.
- `Q4_0` is a legacy type that does not carry imatrix weighting the way the K/IQ types do, so
  bartowski's head differs from his body in method as well as in bit width. Not quantified.
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
