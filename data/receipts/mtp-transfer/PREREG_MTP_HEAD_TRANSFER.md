# Prereg — does an MTP head transfer across fine-tunes of the same base?

> **OUTCOME 2026-09-21: BLOCKED. P1 falsified.** The MiMo Q5_K_S target does not load — it
> declares `block_count = 33` and ships 32 blocks. No arm ran. See
> `RESULT_MIMO_Q5KS_BROKEN.md`. The question below is still open and still unpublished.

**Written 2026-09-21, before any measurement.** Follows
`spec-protocol/SPEC_DECODE_PROTOCOL_v1.md` (standing method).

**Prior art checked:** `ledger_precheck.py "MTP draft head transfer across fine-tunes shared base
acceptance" --deep` -> `SPEC_DECODE_PROTOCOL_v1.md`, `qwen38-packagers/RESULT_MTP_HEAD_QUANT.md`
(heads are quantised blind, no imatrix covers them), `qwen35-drafters/RESULT_MTP_VS_DFLASH.md`,
`battle16gb/MTP_DETERMINISM.md`, `mtp-sm60/SUMMARY.md`.
**What this adds:** every MTP number this project holds used a head shipped **with its own
target**. None asks whether a head trained against fine-tune A drafts for fine-tune B of the same
base. That is the question here, and I can find no published answer to it.

## The question

`mtp-Ornith-1.5-9B-head-Q8_0.gguf` was trained against Ornith-1.5-9B. MiMo-V2.6-Distill-Qwen-9B
is a *different* fine-tune of the same `qwen35` 9B base. The three files agree on every
structural field that would have to match:

| | MiMo-Distill Q5_K_S | Ornith-1.5 Q5_K_M | Ornith MTP head Q8_0 |
|---|---|---|---|
| architecture | qwen35 | qwen35 | qwen35 |
| block_count | 33 | 33 | 33 |
| embedding_length | 4096 | 4096 | 4096 |
| head_count / kv | 16 / 4 | 16 / 4 | 16 / 4 |
| **vocab tokens** | **248,320** | **248,320** | **248,320** |
| tensors | 427 | 442 | 18 |

So it should **load**. Acceptance is an empirical question about how far two fine-tunes drifted
from shared base representations.

## Why the quant mismatch does not confound the headline

MiMo is `Q5_K_S` (5.9 GB) and Ornith is `Q5_K_M` (6.2 GB) — different recipes, ~5 % different
bytes, and `[[gguf-label-is-not-a-spec]]` forbids treating those as equivalent. **The comparison
here is within-model** (head-on vs head-off on the same file, same session), so each target is
its own control. **No model-vs-model quality claim is made or permitted from this run.**

## Arms

Target x head, all on the RX 9070 XT (gfx1201), buun `38ada0e1b`, `-ngl 99 -fa on -ctk f16
-ctv f16 -np 1`, same session, VRAM verified free before each launch.

| arm | target | draft head |
|---|---|---|
| `ORN-off` | Ornith-1.5-9B Q5_K_M | none (baseline) |
| `ORN-mtp` | Ornith-1.5-9B Q5_K_M | Ornith head Q8_0 — **matched control** |
| `MIMO-off` | MiMo-Distill Q5_K_S | none (baseline) |
| `MIMO-mtp` | MiMo-Distill Q5_K_S | Ornith head Q8_0 — **the transfer arm** |

`n ∈ {3, 7}`. Three prompt domains per the protocol: `P-PROSE`, `P-CODE`, `P-STRUCT`. 3 reps per
cell, best reported. Per-item flush+fsync.

## Predictions, committed before data

| id | prediction | confidence | falsifier |
|---|---|---|---|
| **P1** | the Ornith head loads against MiMo and the server reaches `listening` | 0.80 | load abort, or `draft acceptance` never appears |
| **P2** | acceptance(MIMO-mtp) < acceptance(ORN-mtp) on all three domains | 0.85 | transfer >= matched on any domain |
| **P3** | **at temp 0, output is byte-identical head-on vs head-off, for BOTH targets** | 0.90 | any differing generation |
| **P4** | acceptance rises PROSE < CODE < STRUCT in both mtp arms | 0.70 | any inversion |
| **P5** | `MIMO-mtp` is **slower than `MIMO-off`** on at least one domain (net-negative speculation) | 0.50 | transfer faster than baseline everywhere |

**P3 is the one that matters.** Speculative decoding is distribution-preserving *by
construction* — the verify step rejects bad drafts — so a mismatched drafter should be **slow but
correct**. If it is not, that is a correctness bug and outranks every speed number here.

**P5 is the useful one.** `S2` measured that at ~29 % acceptance one architecture is at its
fastest and another is *slower than not speculating*. A cross-tune head is the natural way to
land below break-even, and "a drafter that costs you throughput" is a more useful published
result than "it worked".

## What this cannot establish

- **Nothing about MiMo's or Ornith's quality.** Different quant recipes; see above.
- **One head, one base family, one card.** No claim that MTP heads transfer in general.
- **Acceptance is quant-sensitive** (65.7 % at IQ2/IQ3 vs 70.7-71.5 % at Q6_K per the protocol),
  so these absolute numbers do not transfer to other quants of the same pair.

---

# AMENDMENT 2026-09-22 — unblocked, on better files, with two predictions revised

**Written before any acceptance data was collected for the matrix below.** The 09-21 block is
lifted: `bartowski/MiMo-V2.6-Distill-Qwen-9B-GGUF` **Q8_0** declares `block_count 32` and ships 32
blocks (`RESULT_MIMO_TOOLCALL_DIALECT.md` verifies it). P1's falsifier was a broken target file,
not the hypothesis.

## What changed, and why the experiment is now stronger

| | prereg as written (blocked) | this amendment |
|---|---|---|
| MiMo target | Q5_K_S, `block_count 33` / 32 blocks -- **will not load** | **Q8_0 bartowski**, 9,545,979,424 B, 427 tensors, 32 blocks |
| Ornith target | Q5_K_M, a **different packager and recipe** | **Q8_0 bartowski**, 9,545,982,848 B, 427 tensors, 32 blocks |
| gap between targets | ~5 % of bytes, recipes differ | **3,424 bytes**, same packager, same recipe |
| head | Ornith Q8_0 standalone | unchanged |

**The prereg's largest self-imposed limit is now mostly lifted.** It disclaimed:
*"Nothing about MiMo's or Ornith's quality. Different quant recipes."* The two targets are now the
same packager at the same quant, 3,424 bytes apart, both with `ssm_alpha`/`ssm_beta` at F32. A
careful within-quant comparison is defensible, though acceptance is still not a quality metric.

**And both `mtp` arms now use the same head file.** bartowski's Ornith ships **no** MTP head (427
tensors, no `nextn.*`), unlike the other packager's build (442 tensors, head at `blk.32`). So the
standalone head is the drafter for *both* arms, and the only variable across them is the target.
That is a cleaner contrast than the original plan, where the matched arm would have used Ornith's
own embedded head and the transfer arm a different file.

## Host and runtime, corrected

The prereg specified buun `38ada0e1b`. Not needed: **upstream llama.cpp build 11095
(`58367713a`), `build_rocm`, already supports `--spec-type draft-mtp` with `-md`**, and reports
acceptance natively as `draft_n` / `draft_n_accepted` in `timings` plus a
`draft acceptance = ...` log line. Running on upstream removes a fork variable.

RX 9070 XT, `-ngl 99 -ngld 99 -fa on -ctk f16 -ctv f16 -np 1 -c 4096`. Context reduced from the
protocol default because target (9.55 GB) + head (2.42 GB) = 11.97 GB against ~13.1 GiB free.
**Measured after load: 12.43 GiB used, 3.49 GiB free.** The head is 2.42 GB only because it
bundles `token_embd` (1.08 GB) and `output` (1.08 GB) that duplicate the target's; the MTP block
itself is 258 MB.

`temperature 0`, `cache_prompt: false` on every request (`[[prompt-cache-breaks-determinism]]`),
one warmup generation discarded per arm (`[[server-uptime-is-a-variable]]`).

## Revised predictions

**P1 — RESOLVED CONFIRMED before this amendment was written.** The head loads against bartowski's
Ornith and the server reaches `listening`;
`common_speculative_init_result: loading draft model` appears and a request returns
`draft acceptance = 0.50355 (71 accepted / 141 generated), mean len = 2.51`. That single warmup
probe is the only acceptance figure seen before the predictions below were committed, and it
informed P-A1's range. Recording that rather than pretending otherwise.

**P3 is withdrawn and replaced. It contradicted a receipt this project already holds.**
The prereg predicted at 0.90 that *"at temp 0, output is byte-identical head-on vs head-off"*.
`spec-decode-determinism/RESULT_SPECULATION_IS_NOT_BIT_EXACT.md` (08-18, resolved with
`cache_prompt` swept both ways) establishes the opposite on this stack: at `cache_prompt=0`,
`off` and `mtp_n3` each produce **one** stable output and those outputs **differ**. P3 as written
was already falsified by prior art and should never have been carried at 0.90.

| id | prediction | conf | falsifier |
|---|---|---|---|
| **P3'** | head-on vs head-off at temp 0 / `cache_prompt=0` gives **stable but DIFFERENT** output per arm (matching the 08-18 result on a new architecture) | 0.80 | identical text, or either arm unstable across reps |
| **P-A1** | matched acceptance (`ORN-mtp`) lands 0.45-0.65 on prose | 0.70 | outside that band |
| **P2** | acceptance(`MIMO-mtp`) < acceptance(`ORN-mtp`) on all three domains | 0.85 | transfer >= matched on any domain |
| **P4** | acceptance rises PROSE < CODE < STRUCT in both mtp arms | 0.70 | any inversion |
| **P5** | `MIMO-mtp` is slower than `MIMO-off` on at least one domain | 0.50 | transfer faster everywhere |
| **P6** | the transfer arm still **loads** (same base, same vocab 248,320) | 0.85 | load abort |

## A structural caveat the original prereg could not have known

The standalone head's `blk.32` is **not** byte-identical to the head embedded in the other
packager's Ornith build, though all 15 tensors match on type and size. Q8_0 is deterministic
round-to-nearest with no imatrix (`qwen38-packagers/RESULT_MTP_HEAD_QUANT.md`: heads are
quantised blind), so identical source weights should give identical bytes. **Different bytes imply
the two files were quantised from different source weights or different source precision.**

Consequence: `ORN-mtp` is the matched arm in the sense that head and target come from the same
*model*, not necessarily from the same *conversion*. It remains the correct control for the
transfer question; it is not a claim that this is the head Ornith ships with.
