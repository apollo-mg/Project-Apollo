# Where Qwen3.8-Flash-Next's 180B actually lives, and why it will not place on 4x16 GiB

**2026-08-28**, `.194`, 4x Tesla P100-PCIE-16GB (64 GiB VRAM), 60 GiB RAM (~51 free),
`TheTom/llama-cpp-turboquant` PR #324 @ `d74823a0c`, weights
`Qwen3.8-Flash-Next-UD-IQ4_XS` (87.2 GiB, 3 shards, 1224 tensors).

Tensor table read with a **direct GGUF header parser**, not `gguf-py` — that package does not
import on this branch (see `RESULT_SM60_ARCH_TEST.md`), and a header parser has no opinion
about architectures anyway.

## The map

| GiB | count | tensor family | splittable? |
|---:|---:|---|---|
| **26.82** | **1** | `per_layer_token_embd.weight` | **NO — single tensor** |
| 23.05 | 48 | `blk.N.ffn_down_exps.weight` | by layer |
| 16.19 | 48 | `blk.N.ffn_gate_exps.weight` | by layer |
| 16.19 | 48 | `blk.N.ffn_up_exps.weight` | by layer |
| 0.93 | 36 | `blk.N.attn_qkv.weight` | by layer |
| 0.63 | 1 | `token_embd.weight` | no |
| 0.56 | 36 | `blk.N.attn_gate.weight` / `ssm_out.weight` | by layer |
| 0.49 | 1 | `output.weight` | no |
| ~0.9 | 192 | `blk.N.hc_{attn,ffn}_{up,down}.weight` (hyper-connections) | by layer |
| ~0.24 | 48+ | `ffn_*_shexp` (shared expert), `indexer.*`, `ple_*` | by layer |

Quantisation is mixed: **45.72 GiB IQ4_NL, 31.56 GiB IQ3_S, 8.32 GiB Q8_0**, plus small
IQ4_XS / Q6_K / F32 / BF16. Unsloth dynamic, not a uniform tier.

**Three structural facts fall out of this:**

1. **The n-gram / per-layer-embedding table is 26.82 GiB in ONE tensor.** A single tensor lives
   on a single device. On 16 GiB cards it cannot be placed on a GPU at all — it is CPU or
   nothing. This is the concrete form of the card's claim that embedding-based scaling is
   "more amenable to offloading than MoE": it is one enormous, sparsely-read lookup.
2. **Experts are 55.4 GiB across 48 layers** and split cleanly. They are the streamed,
   bandwidth-bound half.
3. Everything else — attention, SSM, hyper-connections, shared experts, indexer — is **~5 GiB**.
   The compute path is tiny; the parameters are almost entirely table + experts.

So the arithmetic that *should* work here is: PLE (26.8) on CPU, experts + attention (~60.4) on
64 GiB of VRAM. It does not.

## The unresolved part

Four load attempts, all failing at **byte-identical** allocation:

```
allocating 16847.21 MiB on device 0: cudaMalloc failed: out of memory
failed to allocate CUDA0 buffer of size 17665582848
```

| attempt | placement | result |
|---|---|---|
| 1 | `-ngl 99`, no overrides | 16847.21 MiB on dev 0 |
| 2 | `+ -ot per_layer_token_embd=CPU` | **identical** |
| 3 | `+ -ot` 12 layers of experts to CPU as well | **identical** |
| 4 | `-ngl 0` (everything on CPU) | **LOADS AND GENERATES** |

**Identical to the byte across radically different placement instructions.** That is the finding:
whatever is allocating 16.45 GiB on device 0 is not responding to `-ot` or to the layer budget.
`llama_model_loader` does emit its "tensor overrides to CPU are used with mmap enabled" warning,
so the flags are parsed — but the failing allocation does not change size.

Candidate explanations, none yet confirmed:
- the `-ot` regexes do not match these tensor names (escaping through ssh, or pattern syntax)
- the PLE / indexer buffer is allocated by the new `llama-memory-hybrid-idx` path, which may not
  consult tensor overrides
- the allocation is a fixed device-0 buffer unrelated to weight placement

**Attempt 4 answers it: the allocation is NOT unconditional.** With `-ngl 0` the model loads
cleanly and serves.

## Qwen3.8-Flash-Next runs on this box — CPU-only baseline

```
model loaded; listening on http://127.0.0.1:8087
prompt: "What is 17 times 23? Reply with only the number."
-> content "391"  (correct)   49 completion tokens   66.6 s   ~0.74 tok/s
```

**First confirmation that the architecture executes correctly with real weights**, not just the
synthetic models in `test-llama-archs`. 180B params, IQ4_XS, entirely on DDR4-2133 with zero GPU
participation. **0.74 tok/s is the floor** every GPU configuration must be measured against —
useful precisely because it isolates the memory-bandwidth term with no accelerator involved.

So the device-0 buffer appears **only when GPU layers are requested**, and did not shrink when
`-ot` moved the 26.8 GiB PLE table (and later 12 layers of experts) to CPU. The flags parse; the
buffer does not respond. Remaining candidates:
- the `-ot` patterns do not match these tensor names as written
- device 0 receives a fixed share that ignores the override

An `-ngl` sweep (8 / 16 / 24 layers, PLE pinned to CPU) discriminates: if the requested device-0
buffer **scales with the layer count**, the split is working and this is ordinary capacity
pressure. If it stays pinned at exactly 16847.21 MiB, something allocates irrespective of the
layer budget — which would be a genuine defect worth reporting alongside the Meta assert.

**P1/P2/P3 remain unmeasured** — they need the model on GPUs, which is the open problem.
