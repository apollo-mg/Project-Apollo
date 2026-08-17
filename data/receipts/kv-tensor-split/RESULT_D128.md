# N1 — the silent collapse is head-dim-dependent; the loud abort is not

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

## The confound, stated plainly

**This is a model swap, not a head-dim swap.** Llama-3.2-3B differs from Qwen3.8-27B in
architecture, GQA ratio (3:1 vs 6:1), weight format (BF16 vs Q6_K), parameter count, and MTP
presence. Head dim is the leading explanation because the dispatch table is explicitly
D=256-gated, but this ladder cannot exclude the alternatives on its own.

**The clean experiment is not available on this fleet.** It needs either a D=128 Qwen or a
D=256 Llama, and every Qwen here is D=256 (3.5-9B, 3.5-4B, 3.6-28B-REAP, 3.8-27B) while the
only D=128 model is this Llama. Closing that gap requires fetching a model, and until then
the claim is **"clean at D=128 on a different model"**, not **"clean at D=128"**.

The GQA alternative is the one worth naming specifically: 6:1 vs 3:1 is exactly the axis
Tom's auto-asymmetric guard keys on, and his own comment reports turbo3 K degrading
catastrophically at high GQA. A GQA-driven explanation is therefore not far-fetched, though
it would not explain why `q8_0` — which the guard treats as the *safe* target — is the codec
that collapses.

## What this does NOT establish

- **Not a fidelity claim.** "Clean" means not degenerate. The detector cannot see quality,
  so D=128 `q8_0` KV being clean here says nothing about how good it is.
- **Not upstream.** Still no genuine upstream binary on the node (**C3**), so whether this is
  inherited from `ggml-org/llama.cpp` or introduced in the shared fork ancestry is open —
  and that is the question that decides whether this is a two-maintainer report or an
  upstream one.
- **One node, one GPU generation.** sm_60 throughout. No claim about other architectures,
  though `RESULT_GFX1201.md` shows RDNA4 has its own D=256 troubles in the same kernels.
