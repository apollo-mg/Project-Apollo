**Correction to my point 4 above, plus new Pascal data.**

### Correction: I was wrong about `-ot`

I reported that tensor overrides "appear to be ignored" because five loads produced a
byte-identical device-0 request. The observation was right; **my diagnosis was wrong.**

The tensor I was targeting is **already CPU-side by default**, so the override was a no-op, not
a failure. Arithmetic on `UD-Q2_K_XL`:

```
model total          73.4 GiB
backbone (non-PLE)   46.6 GiB
per_layer_token_embd 26.8 GiB
VRAM measured        48.2 GiB   = backbone + ~1.6 GiB overhead
llama-server RSS     10.8 GiB   (PLE is mmap-paged, 57 GiB in page cache)
```

The PLE is not in VRAM with or without `-ot`, including with the anchored
`-ot "^per_layer_token_embd.weight$=CPU"` form. 48.8 GiB without, 48.2 GiB with — allocator
noise, not a 26.8 GiB tensor moving.

So the OOM I was chasing was never about the PLE. It was **backbone distribution**: at
`UD-IQ4_XS` the backbone is 60.4 GiB, so device 0 wants `60.4/4 + 1.1` GiB of non-layer tensors
(`token_embd` + `output`) = ~16.2 GiB against a 16.0 GiB card. That is the 16847.21 MiB request,
and it is ordinary capacity pressure on 16 GiB cards, not an override bug.

**Please disregard point 4.** I have no evidence either way on whether `-ot` binds — the test I
ran could not have shown it.

### New: it runs well on sm_60 at a lower quant

`UD-Q2_K_XL`, **all 48 layers resident**, 4× Tesla P100 (sm_60), `-ngl 99`, ctx 4096:

| | |
|---|---|
| VRAM | **48.8 GiB** (13419 / 12389 / 12389 / 11757 MiB) |
| decode | **~15–16 tok/s** (server `eval time`: 14.14 / 17.57 / 14.39 / 17.57) |
| output | coherent, correct, `finish=stop` |

For scale on the same fleet, `Qwen3.8-27B-Q6_K` runs 13.8 tok/s on 2× P100. `UD-IQ4_XS` cannot
fit all layers (max `-ngl 44`) and does ~9 tok/s.

### New: where the quant floor is

`UD-IQ1_S` produces token soup on this box — raw `/completion`, no chat template, no parser:

```
"The capital city of France is" -> "SCRIPT弄SCRIPT]:=ovowire为王 -, -:WithPath bulletinideaul)binude..."
```

That is worth locating precisely, because unsloth's dynamic quant makes it a clean
single-variable comparison. Measured from the GGUF headers:

| | IQ1_S | Q2_K_XL | IQ4_XS |
|---|---:|---:|---:|
| `per_layer_token_embd` | 26.82 | 26.82 | 26.82 | ← byte-identical at every tier
| `ffn_down_exps` | 21.09 | 21.09 | 23.05 | ← identical IQ1_S vs Q2
| `ffn_gate/up_exps` (each) | 8.01 | 10.91 | 16.19 | ← **the only difference**

The PLE and the down-projections are bit-for-bit the same between IQ1_S and Q2_K_XL. The entire
delta is gate/up expert projections at **1.71 vs 2.32 bpw** — soup at 1.71, fully coherent at
2.32. Might be useful for anyone sizing this arch to constrained VRAM.

### Cross-reference that bears on MTP

HF discussion
[unsloth/Qwen3.8-Flash-Next-GGUF#40](https://huggingface.co/unsloth/Qwen3.8-Flash-Next-GGUF/discussions/40)
reports a deep-context decode slowdown (= `ggml-org/llama.cpp#27856`) that is **host-CPU-bound**:
on 3× RTX 3090 at 140K depth, GPU util reads 0%/0%/0% while llama-server pins 81–85% CPU, and
decode falls 59 → 14 tok/s from 2K to 140K. On that box **MTP measured −20…0%**, DFlash2 ±0%,
ngram-cache −24%.

So wiring MTP into `qwen4exp` may not pay until that lands, which might affect how you prioritise
it. (For reference, `LLM_ARCH_QWEN4EXP` already declares the full NEXTN tensor set in
`llama-arch.cpp`, identical to `QWEN3NEXT`; `src/models/qwen4exp.cpp` just doesn't reference any
of it, where `qwen3next.cpp` reads `LLM_KV_NEXTN_PREDICT_LAYERS` and sets `mtp_flags`.)

Points 1–3 of my earlier comment stand as written.
