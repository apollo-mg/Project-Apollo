# Prereg — the MTP speed delta on RDNA4, EXL3 against GGUF at matched size (EXL3 campaign, test 9, ledger O5)

**Written 2026-09-13 ~10:05, before any data.** Mark's question: *"What's the MTP enabled speed delta on
RDNA4 between EXL3 and GGUF at roughly equal BPW?"*

## Why it is not just a repeat of Pascal

On `.73`, MTP buys **EXL3 1.29× and GGUF 1.70×** at each format's best depth, and test 4 located the cause:
EXL3's int8 GEMV pays **2.08×** for a 4-row verify batch where GGUF's MMVQ pays **1.37×**. On Pascal that
kernel is **compute-bound on trellis decode** — 7 t/s over 13.4 GB is ~94 GB/s against the P100's 732 GB/s.

**RDNA4 has a different compute-to-bandwidth balance**, so the same measurement is a real experiment:
- **If the penalty is intrinsic to the kernel**, EXL3's MTP gain stays well below GGUF's here too.
- **If it was a Pascal artefact**, the gap closes, and EXL3 becomes far more attractive on this card —
  which matters because the 9070 is the box where EXL3's size advantage is purchasable (test 8).

Our own prior for the GGUF side: `KNOWN_GOOD_STATE_20260909.md` recorded this exact GGUF at **27.4 t/s
without MTP and 43–60 t/s with it** on the 9070, at buun `3823c9eb6` — a different build, so it is
context, not a baseline.

## Setup

- **Hardware:** the control plane's RX 9070 XT (gfx1201). **Build:** buun `da458765d` for ROCm.
- **Flags, matched across every arm:** `-ngl 99 -c 8192 -ctk q8_0 -ctv q8_0 -fa on -np 1 --jinja`, plus
  `--spec-type draft-mtp --draft-max k` at depths ≥ 1. Depth 0 omits the MTP flags entirely.
- **Depth needs a server restart per point** — per-request `speculative.n_max` is ignored under
  draft-mtp (`RESULT_EXL3_DEPTH.md`). Loads here cost ~13 s, so this is cheap.
- **Depths:** 0, 1, 2, 3. **Three reps of 128 greedy tokens** per point, same prompt as every other test.

| pair | EXL3 | GGUF | resident sizes |
|---|---|---|---|
| **A, ~10 GB** | 3.00bpw (`mul1`, int8 path) | `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp` | ~10.3 vs 10.02 GB |
| **B, ~12 GB** | 3.50bpw | `Qwen3.8-27B.i1-IQ3_M` | ~11.8 vs 12.21 GB |

Both GGUFs are base Qwen3.8-27B (`general.basename`, no `general.finetune`) and both carry the MTP head
(`qwen35.nextn_predict_layers: 1`, 4 nextn tensors).

**Second stage — the mechanism.** llama-bench `-p 64 -n 8 -ub 1,2,4,8,16,1 -r 3` on pair A, one load per
model, exactly test 4's instrument including its warm-baseline amendment.

## Predictions

| id | prediction |
|---|---|
| P-N1 | **Gate.** MTP engages on both formats on RDNA4: drafted tokens per predicted token rise with depth in every arm |
| P-N2 | Both formats gain from MTP: best-depth decode exceeds depth 0 |
| P-N3 | **EXL3's best-depth MTP gain is below the GGUF's** — the Pascal pattern transfers |
| P-N4 | EXL3's best depth is ≤ the GGUF's, in both pairs |
| P-N5 | At best depth, EXL3 decodes slower than its size-matched GGUF |
| P-N6 | The EXL3 ÷ GGUF speed ratio at best depth is **within ±0.15 of Pascal's 0.648** |
| P-N7 | The micro-batch curve transfers: A_EXL3(4) < A_GGUF(4) on RDNA4 |

## Declared in advance

- **Provenance gap on the GSQ-RCO file.** It has been on this box since 2026-09-03 and appears in our
  receipts, but **we have no published sha256 recorded for it**, so it is used as-is and named as an
  exception to verify-before-use. The `i1-IQ3_M` and both EXL3 snapshots are hash-verified.
- **"Roughly equal bpw" is matched on GPU-resident bytes**, not nominal bits per weight: EXL3 keeps a
  bf16 embedding table and a vision tower off the card, so its disk size overstates its footprint.
- **Different quantization recipes.** IQ3_XXS, i1-IQ3_M and EXL3 trellis quants are not the same
  algorithm; this test measures speed at matched footprint, not quality. Quality at these sizes is the
  natural follow-up on `.73`, where the Q8_0 reference lives.
- **q8_0 KV at 8192, not the daily driver's VBR at 262k** — the 9070 has ~13.2 GB usable after the
  compositor, so a large KV would not fit beside a 10–12 GB model. Speeds here are therefore not
  comparable to `.73`'s served figures, only within this test.
- **One card, three reps per point.**

**Driver:** `exl3_rdna4_mtp.py` (`depths`, `bench`, `score`). Results in `rdna4_mtp/`.
