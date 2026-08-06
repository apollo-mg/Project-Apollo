# MTP speculative decoding on Qwen3.6-35B-A3B: +25 % decode, and it breaks determinism

RX 9070 XT 16 GB (gfx1201), 10.0.0.5. Engine `llama_cpp_turboquant` (TheTom). Date 2026-07-29.
Model `Qwen3.6-35B-A3B-UD-IQ2_M` (11.07 GiB, ~2.5 bpw, Unsloth imatrix).
Serving identical across arms: `-c 65536`, f16 KV, `-b 1024 -ub 512`, `-cb -fa on -np 1
-ngl 99 --cache-ram 0 --jinja`. **Arms differ only by `--spec-type draft-mtp
--spec-draft-n-max 2`.** Probe: one fixed prompt, `temperature 0`, `max_tokens 1200`.

The model ships the MTP head: `qwen35moe.nextn_predict_layers = 1`, tensors
`blk.40.nextn.{eh_proj,enorm,hnorm,shared_head_norm}.weight` — 41 blocks vs Ornith's 40,
so block 40 *is* the head.

## Headline

| | decode | VRAM | draft acceptance | reproducible? |
|---|---|---|---|---|
| base | **79.5–79.9 t/s** | 12.46 GiB | — | **YES — 6/6 byte-identical across 3 restarts** |
| **MTP n-max 2** | **98.3–99.5 t/s (+24 %)** | 12.85 GiB (+0.39) | **0.607–0.624** | **NO — 6 draws produced 4 distinct outputs** |

MTP delivers a real, repeatable **~25 % decode speedup for 0.39 GiB**, at ~62 % draft
acceptance. It also makes the server **nondeterministic at temperature 0**.

## Why this needed a paired design (and how the first answer was wrong)

The first run (`mtp_ab.sh`) compared **one** base instance against **one** MTP instance, saw
each produce 3/3 byte-identical draws, and concluded *"each arm is internally deterministic;
MTP gives a different deterministic sequence."* **That conclusion was wrong on both halves.**

It fell apart because an earlier inline probe of the *same base config* had produced a
different hash:

| base instance | sha | chars |
|---|---|---|
| port 8106 (first load of the session) | `6480076f296971b3` | 4770 |
| port 8108 | `5f3fef54edff5279` | 4865 |
| port 8109 | `5f3fef54edff5279` | 4865 |

Base disagreeing with itself meant the base-vs-MTP diff could not be attributed to MTP at
all — it could just as well have been the restart. **A single A vs single B comparison cannot
separate a treatment effect from instance-to-instance noise.**

The fix: alternate the arms across restarts, **2 draws per instance, 3 instances per arm**,
and compare within-arm agreement against between-arm.

```
base  rep1  ['5f3fef54edff5279','5f3fef54edff5279']  stable
base  rep2  ['5f3fef54edff5279','5f3fef54edff5279']  stable
base  rep3  ['5f3fef54edff5279','5f3fef54edff5279']  stable
mtp   rep1  ['ade68ea7f24f6055','f094492c956d8278']  *** UNSTABLE ***
mtp   rep2  ['f094492c956d8278','56f40e8df576eb12']  *** UNSTABLE ***
mtp   rep3  ['1223dbdadc7f13e6','f094492c956d8278']  *** UNSTABLE ***
```

**Base: 1 distinct output across 6 draws. MTP: 4 distinct outputs across 6 draws — and
unstable *within a single server instance*, not merely across restarts.**

The original "3/3 identical" for MTP was luck: three consecutive draws that happened to land
on the same continuation. Two draws × three instances caught what three draws × one instance
missed. The odd base hash on port 8106 was the session's first load of that file and has not
recurred in 6 subsequent draws — most likely a cold-cache artifact, and *not* the restart
noise it was initially taken for.

## Where it diverges — a single low-margin token, then fan-out

All four distinct MTP outputs diverge from base at **exactly char 126**, on the same token:

```
base: **Key Aspects to Cover:** Node structure, splits, range scans
mtp : **Key Areas   to Cover:** Node structure, splits, range scans
```

They then fan out into four different continuations of differing lengths (4812–4919 chars vs
base 4865).

Greedy speculative decoding is supposed to be **exactly lossless** — a drafted token is
accepted only if it matches the target model's argmax, so the emitted sequence should equal
the non-speculative one token for token. It does not here. The mechanism is consistent with
batched verification changing float reduction order: on a 2-bit MoE the top-1/top-2 margin at
"Aspects"/"Areas" is small enough that the reordering flips it. Once flipped, the trajectory
diverges and subsequent flips compound — which is why one deterministic-looking flip produces
four different endings.

This is the concrete, reproducible version of the Battle16GB note that MTP is
"lossless-in-distribution, not bit-identical" — measured here on a different architecture,
with the divergence localised to a specific token.

## What this means for benchmarking

- **K=1 is not legitimate under MTP.** This campaign's K=1 practice rests on verified
  determinism (`RDNA4_ARCHITECT_DETERMINISM.md`); it holds for base and fails for MTP. Any
  MTP arm needs K≥3 and inherits the ~15 % per-scenario flip floor measured in
  `HA20_SAMPLING_ARMS.md`.
- **"Lossless" claims for speculative decoding should be checked, not assumed** — and checked
  with repeated draws *within* one instance, since a handful of consecutive identical draws
  proves nothing.
- The speedup is real and cheap: **+24 % decode for 0.39 GiB and ~62 % acceptance**. For
  interactive use that is an easy win. For *measurement*, it costs reproducibility.

## Scope limit — this is NOT an MTP-vs-Ornith comparison

`Qwen3.6-35B-A3B` (Qwen, Apache-2.0) and `Ornith-1.0-35B` (deepreinforce-ai, MIT) are
**different models**, not a base/fine-tune pair. Both declare `general.architecture:
qwen35moe` — the Qwen3.5 MoE architecture; Qwen3.6's own tags say `qwen3_5_moe` — so the arch
string does not distinguish them. They differ concretely: **40 blocks (Ornith) vs 41
(Qwen3.6)**, and Ornith has **no `nextn_predict_layers`** (hence no MTP head, which is why
this leg runs on Qwen3.6). Ornith's only declared parent is
`deepreinforce-ai/Ornith-1.0-35B`; nothing in the file names Qwen3.6.

An earlier version of this receipt called Ornith "deepreinforce-ai's fine-tune of Qwen3.6".
**That was inferred from the shared architecture and parameter count, not read from the
metadata, and Mark corrected it.** Same lineage (Qwen3.5 family); exact parentage not
establishable from disk.

The A/B remains valid as a **within-model** comparison on Qwen3.6 — both arms are the same
file, differing only by the spec flags. What the correction kills is any cross-model
inference: Qwen3.6's HA-20 scores cannot be compared to Ornith's to attribute a difference to
fine-tuning, because they are not the same model to begin with.

## Limits

- One prompt, 1200 tokens, one `n-max` value (2). Acceptance and stability may vary with
  `--spec-draft-n-max`, prompt, and length.
- 6 draws per arm establishes that MTP is unstable and base is stable **on this probe**; it
  does not quantify a flip *rate*.
- Base's 6/6 stability is strong but was measured after the anomalous first load; the
  cold-cache explanation for instance 1 is inferred, not proven.
- Task-level impact not yet measured — whether the 15 % flip floor shows up in HA-20 scores
  under MTP is a separate run.

## Provenance

- `~/projects/HermesAgent-20/mtp_paired.sh` → `mtp_paired/` (the valid, paired measurement)
- `~/projects/HermesAgent-20/mtp_ab.sh` → `mtp_ab/` (the superseded single-instance run,
  kept because its wrong conclusion is the reason the paired design exists)
