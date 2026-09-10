# `163517b9a` on 4x P100 — Flash-Next confirmed; DS4 regressed to a load-time failure

**2026-08-28**, `.194`, 4x Tesla P100-PCIE-16GB sm_60, `GGML_CUDA_ALLREDUCE=internal`,
clocks 1063 MHz / 150 W. Tree clean at `163517b9a`, no local patches.

## Check 1 — Flash-Next Q2, `-sm tensor`, 4 devices: PASS

Tom's committed `handle_flash_attn_ext` (`f1a0b0139`) is a **superset** of my local patch: same
all-mirrored early-out, plus a split-Q / mirrored-KV case mine lacked, and stricter asserts on
`src[3]`/`src[4]`.

```
llama-server -m .../Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf \
  -ngl 99 -sm tensor -c 4096 --port 8087 -np 1
```

| | my local patch (`d929da17b`+) | committed (`163517b9a`) |
|---|---|---|
| VRAM/card | 13603 / 13633 / 13603 / 13603 | **13603 / 13633 / 13603 / 13603** |
| output | coherent | **coherent** |
| tok/s | 6.20 | 6.02 |

```
' Paris. Paris is the most populous city in France, with a population of 2.1 million people.
  It is also the most visited city in the world, with over 30 million tourists'
```

Byte-identical VRAM and the same completion — the committed handler matches.

## Check 2 — DS4, even `-ts 1,1,1,1`: FAIL, and **earlier than before**

```
llama-server -m .../DeepSeek-V4-Flash-0731-UD-IQ1_S-00001-of-00003.gguf \
  -ngl 99 -sm tensor -c 8192 --port 8087 -ts 1,1,1,1 -fit off -fa on -ncmoe 40 -np 1
```

**Warm-up does NOT complete.** On `c232282aa` DS4 reached "warming up the model with an empty
run" and died in graph execution; on `163517b9a` it now dies during **weight loading**, before
warm-up. That is a step backwards in how far it gets.

```
ggml-backend.cpp:472: GGML_ASSERT(offset + size <= ggml_nbytes(tensor)
                                  && "tensor write out of bounds") failed
```

Backtrace: `llama_model_load_from_file` -> `load_tensors` -> `llama_model_loader::load_all_data`
-> `ggml_backend_meta_buffer_set_tensor` -> `ggml_backend_tensor_set_2d` -> `ggml_backend_tensor_set`.

Loader state at death:
```
load_tensors: offloaded 44/44 layers to GPU
load_tensors:   CPU_Mapped model buffer size = 46410.60 MiB
load_tensors:   CPU_Mapped model buffer size = 26137.35 MiB
load_tensors:       Meta() model buffer size =  3855.96 MiB
```

### Instrumented — the tensor and the reason

```
OOB write: tensor=blk.0.attn_output_a.weight type=q8_0 ne=[4096,8192,0,1]
           nbytes=0 offset=0 size=35651584 overflow=35651584
```

**`ne[2] = 0`** — the tensor got a **zero-width slice**, so `ggml_nbytes() = 0`. The loader then
tries to write **35,651,584 bytes**, which is the *entire* tensor
(4096 x 8192 elements at q8_0 = 34 bytes / 32 elements = 35,651,584 B exactly).

So allocation and load disagree completely: the split-state gave this device **none** of
`attn_output_a`, while the loader believes it holds **all** of it. `attn_output_a` is matched by
`pattern_attn_out_weight` (`attn_output(_[ab])?\.weight`) and is part of the grouped output
projection handling added in `163517b9a`.

This is the same zero-width-slice family as the qwen4exp/GQA case, surfacing at load time rather
than graph time.

### Uneven `-ts 3,4,4,1` not run

Per Tom's instruction ("even first; if that works, repeat the uneven"), the uneven case was
**not** run because the even case failed.

## Summary for Tom

| check | result |
|---|---|
| Flash-Next Q2 `-sm tensor`, 4 P100s, committed FA handler | ✅ **coherent**, VRAM identical to my patched build |
| DS4 `-ts 1,1,1,1` | ❌ **fails before warm-up** — `blk.0.attn_output_a.weight` gets `ne[2]=0`, loader writes full 34 MiB into a 0-byte allocation |
| DS4 `-ts 3,4,4,1` | not run (gated on the even case) |

## Note on my own instrumentation

Two wasted build cycles: `GGML_LOG_ERROR` from `ggml-backend.cpp` never reached the log (the
server's callback swallowed it — `ggml_abort`'s own raw stderr message did appear), and my first
`str.replace(..., 1)` patched only the **first** of five `"tensor write out of bounds"` asserts,
which lives in `ggml_backend_tensor_set_async` — not the `ggml_backend_tensor_set` that actually
fired. Fixed by using `fprintf(stderr)` + `fflush` and patching all sites. Diagnostics reverted;
tree clean.
