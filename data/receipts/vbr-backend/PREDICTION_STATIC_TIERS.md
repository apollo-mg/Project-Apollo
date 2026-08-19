# Predictions — static TCQ tiers vs the VBR controller

**Logged 2026-08-19, before results.** Desktop RX 9070 XT (gfx1201), buun `02f8581c65`,
`Qwen3.8-27B-AD-IQ2_S`, ctx 16384, same 10 tier-2 items + canary as `f16_control.py`.

## Why this run exists

`RESULT_VBR_COLLAPSE_CONTROLLED.md` concluded "the VBR KV path" from an f16-vs-VBR control.
Re-reading the collapsed server log shows the controller had degraded to the **`turbo1_tcq`
floor — 1.25 bits/value** — and reported the degrade order exhausted. Two projection figures
in the log decode to exactly 1.25 bpv plus the 128 KiB fixed per-context overhead measured
in `RESULT_U5E_KVSIZE.md`:

| cells | 1.25 bpv | + 128 KiB | logged |
|---|---|---|---|
| 256 | 1.250 MiB | 1.375 | **1.38** |
| 512 | 2.500 MiB | 2.625 | **2.62** |

So the arm that collapsed was running a **1.25-bit KV cache**. This run asks whether the
tier alone explains it, with no VBR controller involved.

## Predictions

| # | arm | prediction | conf |
|---|---|---|---|
| C1 | `-ctk turbo1_tcq -ctv turbo1_tcq` | **collapse** (`!` spam, same signature) | 0.75 |
| C2 | `-ctk turbo3_tcq -ctv turbo3_tcq` | **clean** | 0.65 |

## What each outcome means

- **C1 collapse + C2 clean** — VBR is exonerated as a codec defect. The finding becomes
  *the auto-fit walks into a floor tier that is unusable at this model size*, which is a
  budget/fit-policy bug, not a kernel bug. The report to buun changes completely.
- **C1 clean** — the tier is fine and the VBR controller does something beyond tier
  selection. The original headline stands and the mechanism is still open.
- **both collapse** — the low-bit TCQ family is unusable on this model/backend generally.
  Largest claim of the three; would need the CUDA arm before going anywhere.

## Validity gate

Arms report measured VRAM allocation. Expected KV @16384 ctx (32,768 values/token):
`turbo1_tcq` ~80 MiB, `turbo3_tcq` ~208 MiB, f16 1024 MiB. **An arm allocating like f16
silently fell back and is reported INVALID, not clean** — the failure mode that voided an
earlier VBR campaign (`INDEX.md` C2).

---

## Result: C1 correct, C2 FALSIFIED

| arm | alloc | first collapse | correct | canary after |
|---|---|---|---|---|
| `turbo1_tcq` | 11,104 MiB | **T2-01** | 0/10 | **DEAD** |
| `turbo3_tcq` | 11,235 MiB | **T2-01** | 0/10 | **DEAD** |

Validity gate passed: 131 MiB measured delta vs 128 MiB predicted between the two tiers,
so both codecs were genuinely engaged. Neither fell back to f16.

**Outcome 3 of the three anticipated** — both tiers collapse. `vbr` is the CLI alias for
`turbo3_tcq`, so the dynamic controller is not implicated at all: the static codec collapses
the same way. `RESULT_VBR_COLLAPSE_CONTROLLED.md`'s "the VBR KV path" needs narrowing to
the TCQ codec itself, and the floor-tier hypothesis from the log is insufficient — the
nominal tier fails too.

As written above, this is the largest of the three claims and **needs the CUDA arm before
going anywhere.**

---

# Round D/E — cross-backend, D=128, no Bug A confound

`Llama-3.2-3B-Instruct-BF16` (28L, 8 kv-heads, **D=128**, BF16 weights), md5-verified
identical on both boxes. buun `02f8581c65` on both. Single GPU. ctx 16384.

Changes two things at once from the 27B run *deliberately*, because both are controls:
D=256→128 removes the Bug A confound, and IQ2_S→BF16 removes the 2-bit-weight hypothesis.

| # | arm | box | prediction | conf |
|---|---|---|---|---|
| D1 | f16 | RDNA4 | clean | 0.95 |
| D2 | `q8_0` | RDNA4 | clean | 0.90 |
| **D3** | **`turbo3_tcq`** | **RDNA4** | **clean** | **0.55** |
| D4 | `turbo1_tcq` | RDNA4 | collapse | 0.65 |
| E1 | f16 | P100/CUDA | clean | 0.95 |
| E2 | `q8_0` | P100/CUDA | clean | 0.90 |
| **E3** | **`turbo3_tcq`** | **P100/CUDA** | **clean** | **0.70** |
| E4 | `turbo1_tcq` | P100/CUDA | collapse | 0.55 |

**D3 is the pivot.** Clean → the 27B collapse requires D=256 or 2-bit weights, and the
codec is not broken in general. Collapse → TCQ is broken on RDNA4 across models.

**D3 vs E3 answers Mark's question.** Divergence = ROCm-specific, which is the outcome his
prior predicts (buun develops primarily on CUDA).

Standing caveat: `RESULT_U5B_BUUN.md` measured `turbo3_tcq` as ~2× better than `turbo3` on
CUDA/P100 — but by **teacher-forced KLD**, which cannot observe a free-generation collapse.
"Works on CUDA" is therefore not established by that receipt, and E3 is a real question.

---

## Round D/E result — NOT ROCm-specific

| KV | RDNA4 alloc | RDNA4 | P100/CUDA alloc | P100/CUDA |
|---|---:|---|---:|---|
| f16 | 8,289 | clean 9/10 | 8,291 | clean 9/10 |
| `q8_0` | 7,480 | clean 9/10 | 7,477 | clean 9/10 |
| `turbo3_tcq` | 6,880 | **clean 9/10** | 6,869 | **clean 9/10** |
| `turbo1_tcq` | 6,625 | wrong-answer | 6,645 | wrong-answer |

D3 correct (0.55), E3 correct (0.70). Backends agree within 22 MiB on every arm.

## Round F result — D=256 is NOT the trigger

`Qwen3.5-9B-Q8_0`, D=256, 8-bit weights, RDNA4: f16 / `turbo3_tcq` / `turbo1_tcq` all
**clean 10/10**. Even the 1.25 bpv floor tier is fine at D=256 when weights are 8-bit.

Remaining difference between this and the collapsing 27B: **weight quantization**
(Q8_0 vs IQ2_S), model size (32 vs 65 blocks), and packager/checkpoint.

---

# Round G — is it TCQ, or quantized KV generally?

**Never tested:** stock `q8_0` and `q4_0` KV against `Qwen3.8-27B-AD-IQ2_S` on RDNA4. Every
collapsing arm so far has been a TCQ codec; f16 is the only clean arm. If stock quantized KV
also collapses, the finding is **"quantized KV + 2-bit weights"**, which is far broader than
a turboquant issue and would not be buun's bug at all.

| # | arm | prediction | conf |
|---|---|---|---|
| G1 | `q8_0` KV, 27B IQ2_S, RDNA4 | **collapse** | 0.60 |
| G2 | `q4_0` KV, 27B IQ2_S, RDNA4 | **collapse** | 0.70 |

G1 clean → the defect is specific to the TCQ family and buun owns it.
G1 collapse → it is quantized KV generally on 2-bit weights; upstream territory, and the
whole "VBR is dangerous" framing from last night has to be rewritten as something much larger.

## Round G result — BOTH stock quant arms clean; G1 and G2 falsified

27B `AD-IQ2_S`, RDNA4: `q8_0` KV **clean 9/10**, `q4_0` KV **clean 9/10**, both `fin=stop`
throughout, canary alive after. G1 (0.60) and G2 (0.70) both falsified. Stock quantized KV
handles 2-bit weights fine; only TCQ codecs collapse.

## Round H — the last two variables, separated

`.194` ran the 27B **`UD-IQ2_M`** (unsloth, 2-bit) on a single P100/CUDA:
f16 clean 10/10, `q8_0` clean 10/10, `turbo3_tcq` **clean**.

So TCQ + 2-bit weights is fine on CUDA but collapses on RDNA4 — except the two runs differ
in **backend AND quant recipe**. `UD-IQ2_M` is now on the desktop, so one run separates them.

| # | arm | prediction | conf |
|---|---|---|---|
| H1 | `UD-IQ2_M` + `turbo3_tcq`, RDNA4 | **collapse** (→ ROCm-specific after all) | 0.60 |

H1 collapse → backend-specific; Mark's original hypothesis is reinstated for the 2-bit path.
H1 clean → the AtomicChat `AD-IQ2_S` checkpoint is uniquely implicated, not 2-bit generally,
and `gguf-label-is-not-a-spec` applies to the collapse itself.

**Note for the Bug A record:** `q8_0` symmetric at D=256 on sm_60 was **clean 10/10** here.
`RESULT_OWNERSHIP.md` recorded that arm as *collapse 3/3* on buun `a8e5b5a38`. Differences:
single GPU (vs dual), buun `02f8581c65` (vs `a8e5b5a38`), IQ2_M (vs Q6_K). Bug A may be
multi-GPU-only or may be fixed in current buun — **untested, and it needs a 2-GPU arm to say.**
