# RDNA4 Architect determinism — 9070 XT, and the compatibility-hack question

Control plane, AMD Radeon RX 9070 XT (gfx1201, 16 GB). Model
`Qwopus3.5-27B-v3-Q2_K.gguf`. Date 2026-07-28.

First determinism measurement ever taken on the control-plane GPU. All prior determinism work
in this campaign was CUDA sm_60 (P100). This is the HIP/RDNA4 path.

## Why it matters here specifically

The 9070 XT serves the **Architect** role. Nondeterminism here propagates into every agent
decision Apollo makes, which is a stronger consequence than the worker-node case.

## Two of three known channels are already closed in production

`scripts/startup/start_architect.sh` already sets:

| flag | closes |
|---|---|
| `-np 1` | concurrent batched decoding + slot-order asymmetry |
| `--cache-ram 0` | prefix-cache reuse across requests |

So the open question was narrower than usual: **is the HIP/RDNA4 compute path itself
deterministic at temperature 0**, with `GGML_HIP_FORCE_MMQ=1` forcing quantized matmul over
Q2_K weights and asymmetric `q8_0`/`q4_0` KV.

## Result

5 sequential draws, temperature 0, top_k 1, seed 1234, 600 tokens, `cache_prompt` inert
(server cache disabled).

| arm | engine | hacks | verdict | sha | s/draw |
|---|---|---|---|---|---|
| **A** | `llama_cpp_gemma4` (commit 2026-04-05) | full `HSA_*` stack + forced MMQ + MMVQ source patch | **DETERMINISTIC** 1/5 distinct | `00e45b56debf` | 23.1 |
| **B** | `llama_cpp_turboquant` (TheTom, v9971 `c26cbdffc`) | **none** | **DETERMINISTIC** 1/5 distinct | `b3ecd1c7b6dc` | 21.1 |

Both arms: 5 of 5 draws byte-identical, zero divergence.

**The HIP/RDNA4 backend is deterministic at temperature 0 on both engines.** No AMD-side
equivalent of the sm_60 problem appears in this configuration.

## The compatibility hacks are not needed on TheTom's fork

Arm B set **no** `HSA_OVERRIDE_GFX_VERSION`, **no** `GGML_HIP_FORCE_MMQ`, **no**
`HSA_ENABLE_SDMA=0`, **no** `AMDGPU_CWSR_ENABLE=0`, **no** `HSA_XNACK=0`, and ran on a tree
without the MMVQ source patch. It came up healthy, detected the card natively
(`ROCm0 : AMD Radeon RX 9070 XT (16304 MiB, 16182 MiB free)`), served correctly, and was
deterministic.

Secondary observation: **~8.7 % faster** per draw (21.1 s vs 23.1 s for 600 tokens, ≈28.4 vs
26.0 tok/s). Consistent with dropping `HSA_ENABLE_SDMA=0` (DMA engines re-enabled) and no
longer forcing a specific matmul kernel — but not isolated, see limits.

## Outputs differ BETWEEN arms — expected, and not a defect

`00e45b56debf` (2452 chars) vs `b3ecd1c7b6dc` (2295 chars). Different engine builds, four
months of kernel changes apart, one with forced MMQ and a MMVQ patch. Determinism means
*repeatable within a configuration*, not identical across configurations. Each arm is
internally byte-exact, which is the property that matters.

## Limits

- **The hack removal is a bundle, not a variable.** Arm B dropped five env vars and a source
  patch simultaneously. It proves the bundle is unnecessary on this fork; it does not say
  which member was doing what, nor that any individual one was ever load-bearing.
- **Context 8192, not the production 65536.** Reduced to leave desktop headroom on a 16 GB
  card in active use. KV-quantization behaviour at depth is untested here — and the KV panel
  work on `.73` showed depth matters.
- **N=5, one prompt.** Establishes repeatability, not absence of rare divergence.
- **The speed delta is n=5 on one prompt**, and Arm B benefited from a warm page cache for
  the model file (Arm A had just been unloaded). Load time is therefore not comparable at all
  (3 s vs 53 s is page cache, not engine). Per-draw decode time is less affected but the
  figure should be treated as indicative.
- MoE kernel correctness was not specifically exercised; the MMVQ patch in Arm A exists to
  dodge a `MUL_MAT_ID` bug, and a 600-token greedy completion may not hit that path hard.

## Recommendation

Migrating the Architect to `llama_cpp_turboquant` looks justified: same determinism, no
workaround stack, modestly faster, four months of upstream fixes, plus native turbo KV types
that the current engine lacks. Before switching, re-run this probe at the production
`-c 65536` and exercise a real multi-turn tool-calling workload, since neither is covered
above.

## Provenance

- `~/projects/HermesAgent-20/start_architect_probe.sh` (Arm A, port 8095)
- `~/projects/HermesAgent-20/start_architect_probe_tq.sh` (Arm B, port 8096)
- `~/projects/HermesAgent-20/determinism_probe.py`
- Raw draws under `~/projects/HermesAgent-20/determinism/`
