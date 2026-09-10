Ran this on Pascal (sm_60) since the thread so far covers a 5090 and an M5 Max. Four things,
one good and three worth a look.

**Build/environment:** `d74823a0c`, 4x Tesla P100-PCIE-16GB, CUDA 12.4, gcc 15.2, driver 580.
`cmake -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=60 -DCMAKE_CUDA_FLAGS=-allow-unsupported-compiler`.
Builds clean, no errors; `cuobjdump` confirms real `sm_60` cubins.

---

### 1. qwen4exp works on sm_60

`test-llama-archs`, single GPU:

```
| qwen4exp | Tesla P100-PCIE-16GB  | MoE | OK (3.04e-14) | OK |
| qwen4exp | Xeon E5-2650 v3 (CPU) | MoE | OK (0.00e+00) | OK |
```

Same order as every other passing arch in the run (2.6e-14 – 2.8e-14), roundtrip included.
Since the PR touches no `ggml-cuda` files, op coverage is inherited — and it holds.

Also ran the real weights: `unsloth/Qwen3.8-Flash-Next-GGUF` UD-IQ4_XS (87.2 GiB) at `-ngl 44`,
~9 tok/s decode, correct answers. So it's not just the synthetic models.

---

### 2. `qwen4exp` is the only arch that aborts on the Meta backend

```
ggml-backend-meta.cpp:730: GGML_ASSERT(split_states_equal(src_ss[0], src_ss[2])) failed
  in handle_set_rows

llama_context::decode -> process_ubatch -> ggml_backend_sched_alloc_graph
  -> ggml_gallocr_alloc_graph -> ggml_backend_meta_buffer_init_tensor
  -> ggml_backend_meta_get_split_state -> ggml_abort
```

In the same run, **24 Meta rows passed**, including every other MoE:
`qwen2moe` 2.69e-14, `qwen3moe` 2.63e-14, `qwen3next` 2.74e-14, `qwen3vlmoe` 2.67e-14,
`qwen35moe` 2.73e-14. `qwen4exp` is the only one of ~30 that aborts there.

A `SET_ROWS` op reaches the Meta splitter with sources 0 and 2 carrying mismatched split states.
I'd guess the new `llama-memory-hybrid-idx` / PLE path, but I haven't traced it.

**Caveat I can't resolve:** your M5 Max composes Meta from Metal+CPU, mine from CUDA+CPU. Nothing
I have separates "Pascal" from "CUDA" here — an sm_80+ CUDA box would settle it in one run.

---

### 3. `gguf-py` doesn't import on this branch

```python
>>> import gguf
AttributeError: type object 'MODEL_ARCH' has no attribute 'QWEN4EXP'
```

`constants.py:2459` defines `MODEL_ARCH.QWEN4EXP: [...]`, but the enum member, the
`MODEL_ARCH_NAMES` entry, and **17 of the 48 `MODEL_TENSOR` members it references** were never
declared. All 17 are also missing from `TENSOR_NAMES`:

- hyper-connections (11): `HC_ATTN_{DOWN,INJECT,NORM,UP}`, `HC_FFN_{DOWN,INJECT,NORM,UP}`, `HC_HEAD_{DOWN,NORM,UP}`
- per-layer embeddings (6): `PLE_CONV1D`, `PLE_KEY`, `PLE_VALUE`, `PLE_NORM_{CONV,KEY,QUERY}`

~19 declarations total. Reproduced in a fresh interpreter with `__pycache__` cleared; adding
`MODEL_ARCH.QWEN4EXP` alone just moves the failure to `MODEL_TENSOR.HC_HEAD_NORM`. This takes
`convert_hf_to_gguf.py` down with it. C++ side is unaffected.

(Possibly already caught — `python type-check` and `Lint` were still queued when I looked.)

---

### 4. Two placement controls that don't work for this arch

**`-ot` tensor overrides appear to be ignored.** Five loads, byte-identical device-0 request
(`17665582848`) every time:

| `-ngl` | override | device-0 request |
|---|---|---|
| 99 | none | 16847.21 MiB |
| 99 | `per_layer_token_embd=CPU` | 16847.21 MiB |
| 99 | + 12 layers of `ffn_*_exps` | 16847.21 MiB |
| 99 | + `token_embd`, `output` | 16847.21 MiB |

`llama_model_loader` does print its "tensor overrides to CPU are used with mmap enabled"
warning, so the flags parse. `-ngl` by contrast scales exactly: VRAM ≈ `2650 + 1250*N` MiB,
within 1.6% across N = 8/12/16/24/36/44.

This matters for this model specifically: `per_layer_token_embd.weight` is a **single 26.82 GiB
tensor**, so it can't sit on a 16 GiB card at all, and `-ot` is the only tool for saying so.

**Compute-buffer estimator is off**, at `-ngl 44`:

```
CUDA1 compute buffer size of 146.7911 MiB, does not match expectation of 139.0157 MiB
CUDA2 149.8038 vs 144.0157 | CUDA3 149.8038 vs 144.0159
CUDA_Host  29.7715 vs  14.8692        <- 2x
```

Since that estimate feeds auto-fit, it'll mis-size headroom on this arch. Possibly the same path
that threw `common_fit_params: vector::_M_range_check: __n (which is 1) >= this->size()` when a
relaunch raced partly-occupied VRAM.

---

Happy to re-run anything here, or test a patch — the P100 box is free and I can turn these
around quickly.

*(Environment note, not a PR issue: this node needs `GGML_CUDA_ALLREDUCE=internal` or the suite
dies earlier in `ggml_backend_cuda_comm_allreduce_nccl`. Local NCCL quirk.)*
