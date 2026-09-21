# Prereg — does an MTP head transfer across fine-tunes of the same base?

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
