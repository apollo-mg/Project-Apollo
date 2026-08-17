# N1 — the silent collapse is head-dim-dependent; the loud abort is not

> **VALIDITY CONFIRMED 2026-08-17.** The clean `q8_0`/`q4_0` arms below were checked
> for a silent f16 fallback (the failure that voided a VBR campaign, `INDEX.md` C2).
> VRAM deltas confirm quantization engaged: f16 9390 MiB, `q8_0` 8650, `q4_0` 8202.
> See `RESULT_KV_VALIDITY.md`.

**2026-08-17**, `.73`, dual P100 (sm_60). Binary **TheTom `f6124e9`**.
Model **`Llama-3.2-3B-Instruct-BF16`**, **D=128**, 24 heads / 8 KV (GQA 3:1).
`TURBO_AUTO_ASYMMETRIC=0` throughout (and 3:1 is below the 6:1 gate, so it could not fire
either way). Raw `~/xfork_d128/`, log `~/kv_d128.log`, script `kv_d128.sh`.

## D=128 against D=256, same binary, same node, same flags

| K | V | **D=256** (Qwen3.8-27B) | **D=128** (Llama-3.2-3B) |
|---|---|---|---|
| f16 | f16 | clean | **clean 3/3** |
| `q8_0` | `q8_0` | **collapse 3/3** | **clean 3/3** |
| `q4_0` | `q4_0` | **collapse 3/3** | **clean 3/3** |
| `q8_0` | `q4_0` | abort `:535` | **crash** in `ggml_backend_sched_alloc_graph` |
| turbo3 | turbo3 | abort `:535` | **abort `:535`** |
| `iq4_nl` | `iq4_nl` | abort `:535` | **crash** in `ggml_backend_sched_alloc_graph` |

L0 (f16) is the admissibility gate and passed 3/3 — BF16 weights run fine on sm_60 under
tensor split, so every arm below it is interpretable.

## The result

**The collapse — the silent one — does not occur at D=128.** Both codecs that collapse
deterministically at D=256 (`q8_0` and `q4_0` symmetric, 512 `/` on the first request, every
time, on both forks) produce normal output here, 3/3 each.

**The abort does occur at D=128.** Every configuration that fails to start at D=256 also
fails to start at D=128. The *form* varies — turbo3 symmetric hits the same
`ggml-backend-meta.cpp:535` assert at both head dims, while mixed `q8_0`/`q4_0` and
`iq4_nl` crash inside `ggml_backend_sched_alloc_graph` during `llama_decode` rather than
asserting — but nothing that was broken becomes usable.

So the two defects separate on a **third** independent axis, after split mode and fork:

| | shared across forks | needs `-sm tensor` | head-dim dependent |
|---|---|---|---|
| **collapse** | yes | **no** | **yes — D=256 only** |
| **abort** | yes | **yes** | **no** |

Three orthogonal separations is strong evidence these are genuinely two bugs rather than one
defect with two presentations, which is how `RESULT_TWO_KV_BUGS.md` originally framed it.

## Why this one matters most

The collapse is the dangerous bug: it is **silent at the API level**. The server starts,
reports healthy, accepts requests, returns HTTP 200 with `finish_reason: length` — and the
content is 512 identical characters. The abort at least announces itself.

**Its scope is now bounded: head_dim 256.** That covers the Qwen3.5 / 3.6 / 3.8 families —
every Qwen GGUF on this fleet is D=256, including the 4B — and spares the D=128 mainstream
(Llama, Mistral, and most others). That is a precise, checkable scope statement to hand two
maintainers, and it explains why a bug this total has not been widely reported: the affected
configuration is a specific and relatively recent model family, not the common case.

It also fits the mechanism that has survived: `fattn.cu` carries a **D=256-specific**
type-pair dispatch table, and the fused path it guards is gated on
`turing_mma_available() || amd_wmma_available()`, **neither true on sm_60**.

## The confound — mostly eliminated by a matched pair

The first version of this receipt compared Qwen3.8-27B-Q6_K against Llama-3.2-3B-BF16 and
had to concede that architecture, GQA (6:1 vs 3:1), weight format, parameter count and MTP
all moved together with head dim. It also claimed the clean experiment "is not available on
this fleet." **That was wrong** — `Qwen3.5-4B-BF16` was already on `.73`, D=256, and makes a
far tighter pair.

**Matched pair, same binary, same node, same flags, same detector:**

| | Llama-3.2-3B-BF16 | **Qwen3.5-4B-BF16** |
|---|---|---|
| head dim | **128** | **256** |
| heads / KV heads | 24 / 8 (GQA 3:1) | 16 / 4 (GQA 4:1) |
| weights | BF16 | BF16 |
| size | 6.4 GB | 8.4 GB |
| MTP | none | none |
| f16 KV | clean 3/3 | **clean 3/3** |
| **`q8_0` K+V** | **clean 3/3** | **COLLAPSE 3/3** (512 `/`) |
| **`q4_0` K+V** | **clean 3/3** | **COLLAPSE 3/3** |

**Four explanations die at once.** Weight format (both BF16), parameter count (both small),
MTP (neither has it), and GQA — 4:1 against 3:1, both far below Tom's 6:1 threshold and far
from the 6:1 of the original 27B. The GQA story was the most plausible alternative and it is
now dead: the collapsing model has *lower* GQA than the original collapsing model and *higher*
than the clean one, with no threshold in between that separates collapse from clean.

**What still moves with head dim: Qwen-vs-Llama architecture.** Every D=256 model tested is a
Qwen and the only D=128 model is a Llama, so "D=256" and "Qwen" remain perfectly confounded
on this fleet. Separating them needs a non-Qwen D=256 model or a Qwen D=128 model, and
neither exists here.

Head dim remains the better-supported of the two because the mechanism is explicit in the
source — `fattn.cu` gates a D=256-specific dispatch table on
`turing_mma_available() || amd_wmma_available()` — whereas no comparable Qwen-specific path
exists in the KV cache code. But on the evidence alone, **"D=256" and "Qwen" are not yet
distinguishable**, and the honest claim is that one of the two is the variable.

## What this does NOT establish

- **Not a fidelity claim.** "Clean" means not degenerate. The detector cannot see quality,
  so D=128 `q8_0` KV being clean here says nothing about how good it is.
- **Not upstream.** Still no genuine upstream binary on the node (**C3**), so whether this is
  inherited from `ggml-org/llama.cpp` or introduced in the shared fork ancestry is open —
  and that is the question that decides whether this is a two-maintainer report or an
  upstream one.
- **One node, one GPU generation.** sm_60 throughout. No claim about other architectures,
  though `RESULT_GFX1201.md` shows RDNA4 has its own D=256 troubles in the same kernels.
