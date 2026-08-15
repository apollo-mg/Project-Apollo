# The MTP draft head is invisible to every quant-quality chart, including the best one

**2026-08-15.** Prompted by `AtomicChat/Qwen3.8-27B-GGUF` and its
[discussion #65](https://huggingface.co/Qwen/Qwen3.8-27B/discussions/65) — a KL-divergence
ladder measured against BF16 on held-out text, comparing their files to unsloth,
lmstudio-community and ggml-org.

Method: `probe_head.py`, HTTP range reads of the tensor table only. **16 files, 133 GiB on the
hub, 192 MiB actually transferred** (12 MiB each). No weights downloaded. Raw log:
`raw/ad_head_probe.log`.

## First, the thing this is not

This is the most rigorously documented packager release we have looked at. They publish the
calibration corpus, the held-out eval text, a benchmark contamination scan, a train/eval
crosscheck showing 0 shared lines, and the raw metric logs. They measured competitors' files
themselves rather than copying published figures, they state that `Q8_0` is not lossless and
that measuring against a `Q8_0` reference would flatter every number in their table, and they
name a size band where unsloth beats them. That is a higher standard of disclosure than the
norm, and none of what follows is a contamination or good-faith complaint.

They also **already documented the mechanism below**, in their own model card:

> ### The prediction head collects no calibration data
> The multi token prediction head is never executed during a normal forward pass, so the
> importance matrix has nothing to say about it at any corpus size. Quantize it low and
> llama.cpp refuses partway through rather than guess. It is pinned to `q5_k` in every file
> here.

That is independently the same wall we hit building `PREREG_HEAD_ISOLATION.md`, from the other
direction — `tensor_requires_imatrix()` at `llama-quant.cpp:768` aborts on
IQ3_XXS/IQ2_XXS/IQ2_XS/IQ2_S/IQ1_M/IQ1_S rather than degrade. Two groups, same week, same
finding. Their write-up is the clearest public statement of it we have seen.

## The head map

| file | GiB | head MiB | attn_q | attn_out | ffn_down | ffn_gate | ffn_up | **eh_proj** |
|---|---:|---:|---|---|---|---|---|---|
| AD-IQ1_M | 7.91 | 278.54 | Q5_K | Q5_K | Q5_K | Q5_K | Q5_K | **Q5_K** |
| AD-IQ2_XXS | 8.36 | 278.54 | Q5_K | Q5_K | Q5_K | Q5_K | Q5_K | **Q5_K** |
| AD-IQ2_XS | 9.21 | 278.54 | Q5_K | Q5_K | Q5_K | Q5_K | Q5_K | **Q5_K** |
| AD-IQ2_S-IQ2_XS | 9.52 | 278.54 | Q5_K | Q5_K | Q5_K | Q5_K | Q5_K | **Q5_K** |
| AD-IQ2_S | 10.38 | 278.54 | Q5_K | Q5_K | Q5_K | Q5_K | Q5_K | **Q5_K** |
| AD-IQ3_XXS | 11.25 | 278.54 | Q5_K | Q5_K | Q5_K | Q5_K | Q5_K | **Q5_K** |
| AD-IQ3_S-IQ3_XXS | 12.09 | 278.54 | Q5_K | Q5_K | Q5_K | Q5_K | Q5_K | **Q5_K** |
| **AD-IQ3_S** | 12.89 | **225.92** | IQ4_XS | Q5_K | **IQ3_S** | **IQ3_S** | **IQ3_S** | Q8_0 |
| **AD-IQ4_XS-IQ3_S** | 13.45 | **234.55** | IQ4_XS | Q5_K | IQ4_XS | **IQ3_S** | **IQ3_S** | Q8_0 |
| AD-IQ4_XS | 15.38 | 258.46 | IQ4_XS | Q6_K | Q4_K | IQ4_XS | IQ4_XS | Q8_0 |
| AD-Q4_K | 15.94 | 265.65 | Q4_K | Q6_K | Q4_K | Q4_K | Q4_K | Q8_0 |
| AD-Q5_K-Q4_K | 17.27 | 276.27 | Q4_K | Q6_K | Q5_K | Q4_K | Q4_K | Q8_0 |
| AD-Q5_K | 18.84 | 305.02 | Q5_K | Q6_K | Q5_K | Q5_K | Q5_K | Q8_0 |
| AD-Q6_K-Q5_K | 21.50 | 323.58 | Q5_K | Q8_0 | Q6_K | Q5_K | Q5_K | Q8_0 |
| AD-Q6_K | 23.29 | 354.12 | Q6_K | Q8_0 | Q6_K | Q6_K | Q6_K | Q8_0 |
| **Q8_0** | 26.90 | **278.54** | Q5_K | Q5_K | Q5_K | Q5_K | Q5_K | **Q5_K** |

Eight files share a **byte-identical 278.54 MiB all-`Q5_K` head**. Eight do not. (Q5_K at
5.5 bpw over these shapes reproduces 278.44 MiB + F32 norms — the arithmetic closes, so the
type read is not an artefact.)

## Finding 1 — the recommended 16 GB file has an IQ head built with no importance data

`AD-IQ3_S` is the file the model card recommends for 16 GB cards ("around 8k context"), and
the one quoted in the discussion post ("92.4% top-1"). Its draft head is `IQ4_XS` on `attn_q`
and **`IQ3_S` on all three FFN tensors**.

`IQ3_S` and `IQ4_XS` are not in the `tensor_requires_imatrix()` set, so llama.cpp does not
abort — it assigns them silently. But the importance matrix has no `blk.64` entries to inform
that assignment, which is the exact hazard the `q5_k` pin exists to prevent. The pin caught
every tier where llama.cpp *would* have refused and missed the tiers where it would not.
`AD-IQ4_XS-IQ3_S` has the same shape.

This is the actionable one: it is a two-line `--tensor-type` fix, and it lands on the file
most users of this ladder will actually download.

## Finding 2 — the partition is 15/16 explained by the abort rule

Sort the ladder by whether the head's natural type would have required an imatrix:

| natural head type requires imatrix? | head recipe | files |
|---|---|---|
| yes (IQ1_M, IQ2_XXS, IQ2_XS, IQ2_S, IQ3_XXS) | pinned `Q5_K` | 7 of 7 |
| no (IQ3_S, IQ4_XS, Q4_K, Q5_K, Q6_K) | tracks the body tier | 8 of 8 |
| no (Q8_0) | pinned `Q5_K` | **1 — the exception** |

Fifteen of sixteen files are explained by "pin only where the build would otherwise abort."
`Q8_0` is the one that does not fit: nothing would have aborted, and the pin took a head that
would have been `Q8_0` down to `Q5_K`.

Consequence: **the flagship `Q8_0` carries a lower-precision draft head than `AD-Q6_K`, the
file below it** — 278.54 MiB against 354.12 MiB, and `eh_proj` at `Q5_K` against `Q8_0`. Its
head is byte-identical to the one in `AD-IQ1_M`, a file 3.4× smaller whose top-1 is 22 points
lower. Someone buying the 28.9 GB file for maximum fidelity and running `--spec-type
draft-mtp` gets the ladder's joint-weakest drafter.

**Ruled out:** "half the ladder predates the pin." All 16 files were uploaded in a single
36-minute window on 2026-08-14 (19:19–19:55 UTC), interleaved across both head policies.

## Finding 3 — the model card's claim is exact, and false for half the ladder

> "It is pinned to `q5_k` in every file here."

Eight of sixteen files have a `blk.64` that is not `q5_k`. The charitable reading — *never
below q5_k* — also fails: `AD-IQ3_S` and `AD-IQ4_XS-IQ3_S` carry `IQ3_S` (~3.4 bpw) FFN
tensors, below `Q5_K`'s 5.5.

The direction is not uniform, and saying "worse head" would be wrong. In the eight unpinned
files `eh_proj` is `Q8_0` — **better** than the pinned files' `Q5_K`, on the tensor unique to
the MTP path. `AD-IQ3_S` trades a better `eh_proj` for worse FFN. Only `AD-Q4_K` and up are
unambiguously richer heads than the pin.

## Finding 4 — what a KLD-vs-BF16 chart structurally cannot see

`blk.64` never executes in a normal forward pass. That is *why* the imatrix has no data for
it, and it has a second consequence the write-up does not draw: **KL divergence and top-1
agreement, measured on ordinary decoding, are computed without the draft head participating.**

Every number in that ladder — 0.00064 to 0.34212, 98.92% to 76.34% — would be bit-identical if
`blk.64` were `F16` or `IQ1_S` in every file. The chart cannot move in response to the head.

That is not a flaw in their measurement; it is correct for what it measures. It is a gap in
what the field measures, and it is load-bearing here because the same model card tells you to
use the head:

> The model ships a multi token prediction head. It is inside every file here and needs no
> extra download: `llama-cli -m Qwen3.8-27B-AD-Q4_K.gguf --spec-type draft-mtp`

So the ladder ships a component in every file, documents it as a feature, and the quality
table beside it is blind to it by construction. The metric that *would* see it is draft
acceptance, and nobody publishes it.

## Finding 5 (ours) — our own attempt to price this is underpowered, and we should say so

`headlab` built four files differing in `blk.64` alone (`F16`, `Q6_K`, `IQ4_XS`, `Q4_0`) on an
`UD-IQ3_XXS` body, benched on the RX 9070 XT. The **build** is clean and does what
`PREREG_HEAD_ISOLATION.md` specified. The **bench** cannot resolve the effect.

| head | head bpw | MTP off | MTP on | multiplier | aggregate acceptance |
|---|---|---:|---:|---:|---:|
| F16 | 16 | 26.53 | 48.98 | 1.846× | 66.00 % |
| Q6_K | 6.6 | 27.08 | 49.11 | 1.813× | 64.18 % |
| IQ4_XS | 4.25 | 26.88 | 52.87 | 1.967× | 64.48 % |
| Q4_0 | 4.5 | 27.15 | 53.57 | 1.973× | 64.14 % |

Read only the F16 and Q4_0 rows and it looks like a tidy 1.86 pp cost for a 4-bit head. The
full four arms kill that reading: **acceptance is not monotone in head precision.** `Q6_K`,
the richest quantized head, lands at 64.18 % — *below* `IQ4_XS` at 4.25 bpw, and level with
`Q4_0`. A 2.35 pp precision range produces a 0.34 pp acceptance range in the wrong order.

Why the aggregate cannot be trusted:

- **Effective n = 5, not 3000.** The two reps are deterministic replays — the F16 arm produced
  bit-identical draft counts in rep0 and rep1 on all five prompts. Token counts are not
  independent samples.
- **Within-arm swing exceeds between-arm difference.** The Q4_0 arm was bistable on the `code`
  prompt: rep0 369/196 = 53.1 %, rep1 392/187 = 47.7 %. A **5.4 pp swing between identical
  reps of the same file** against a 1.86 pp difference between files.
- **Per-prompt deltas flip sign.** Q4_0 vs F16: code −4.67, prose −3.42, list +0.77, repeat
  +2.26, reason +2.21 — three up, two down. IQ4_XS vs F16 is 1 up, 2 down, 2 tied. There is no
  consistent direction.
- **Prompt type dominates.** Acceptance ranges 42.6 % (prose) to 93.6 % (repeat) *within* one
  head. Head precision moves it by ≤5 pp.

**Verdict: unresolved.** On this mix, head precision from `F16` down to `Q4_0` produced no
effect distinguishable from replication noise. That is consistent with a small effect and with
no effect; it does not establish either.

This is the `RESULT_2x2.md` trap again — the one `build_screen.py` was written to avoid — and
it was walked into anyway, in a different experiment, three weeks later. Recording that
plainly: a design that isolates the variable correctly still measures nothing if the
instrument is noisier than the effect. Needs many more prompts, or a direct
acceptance-per-position measure rather than an end-to-end mix.

**The throughput result is separate and does survive.** The MTP-off arms sit within 0.62 t/s
of each other (26.53–27.15), so the target model is unchanged across all four builds and any
MTP-on difference is the drafter. There, head *size* orders the results cleanly where
precision did not:

| head | head bpw | MTP-on median t/s |
|---|---|---:|
| Q4_0 | 4.5 | **53.57** |
| IQ4_XS | 4.25 | 52.87 |
| Q6_K | 6.6 | 49.11 |
| F16 | 16 | 48.98 |

A ~4-bit head is worth **+9 %** end to end over `F16`. `Q6_K` is the worst trade in the set —
it buys no measurable acceptance over `Q4_0` and gives back nearly the whole speed advantage,
landing 0.13 t/s from the `F16` head. On this fleet, spending bits on the draft head above
~4 bpw purchased nothing either way.

## What this supports

Mark's hypothesis was that bartowski pins the MTP head at `Q4_0` because he has data showing
4-bit is good enough. Three independent lines now point the same way, none of them conclusive
alone:

1. bartowski `Q6_K` vs unsloth `Q6_K` differ by two bits on the head and 0.80 pp on acceptance
   (`RESULT_MTP_HEAD_QUANT.md`) — confounded, the bodies differ too.
2. head-isolated builds show no resolvable acceptance difference across `F16`→`Q6_K`→
   `IQ4_XS`→`Q4_0`, and the ordering that does appear is not the one precision predicts
   (above).
3. AtomicChat independently concluded the head cannot be calibrated at all and pinned it to a
   fixed mid type rather than scaling it.

Nobody has data showing a 4-bit head is *bad*, and the imatrix that would be needed to build a
better one does not exist for any packager. The upstream gap is that `llama-imatrix` never
executes `blk.64`, so every published MTP head — bartowski's, unsloth's, AtomicChat's, ours —
is quantized blind.

## Limits

- Header reads only. Type assignment is exact; nothing here measures the resulting quality.
- We have not run AD's files. Findings 1–4 are properties of the files and their
  documentation, not of their behaviour.
- Our headlab arms use bartowski's imatrix on an `UD-IQ3_XXS` body with uniform per-type
  heads. AD's heads are per-tensor mixes on different bodies. Our numbers **bound** what head
  precision can do on this fleet; they do not measure AD's files.
- `Q8_0` head being `Q5_K` is stated as an observation. We did not reproduce their build, so
  whether it was an intended pin or an override applied wider than intended is unknown.
- Discussion #65's chart was not re-measured. Finding 4 is about what the metric can see, not
  whether the values are right.
