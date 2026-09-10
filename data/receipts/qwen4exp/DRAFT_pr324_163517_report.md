# DRAFT — PR #324 reply for `163517b9a`. For Mark to review. NOT POSTED.

---

Synced to `163517b9a`, clean tree, no local patches. 4x P100 sm_60,
`GGML_CUDA_ALLREDUCE=internal`, clocks 1063 MHz / 150 W.

## 1. Flash-Next Q2, `-sm tensor`, 4 P100s — confirmed

```
llama-server -m Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf \
  -ngl 99 -sm tensor -c 4096 --port 8087 -np 1
```

```
' Paris. Paris is the most populous city in France, with a population of 2.1 million people.
  It is also the most visited city in the world, with over 30 million tourists'
```

VRAM **13603 / 13633 / 13603 / 13603 MiB** — byte-identical to my local-patch build, same
completion, 6.02 tok/s. Your committed handler is a superset of what I had (the split-Q /
mirrored-KV branch and the `src[3]`/`src[4]` asserts are additions), and it behaves the same on
the all-mirrored path. Confirmed.

## 2. DS4, even `-ts 1,1,1,1` — still fails, and now **earlier**

```
llama-server -m DeepSeek-V4-Flash-0731-UD-IQ1_S-00001-of-00003.gguf \
  -ngl 99 -sm tensor -c 8192 --port 8087 -ts 1,1,1,1 -fit off -fa on -ncmoe 40 -np 1
```

**Warm-up does not complete.** On `c232282aa` it reached "warming up the model with an empty run"
and died in graph execution; on `163517b9a` it dies during **weight loading**, before warm-up.

```
ggml-backend.cpp:472: GGML_ASSERT(offset + size <= ggml_nbytes(tensor)
                                  && "tensor write out of bounds") failed
```

`llama_model_load_from_file` -> `load_tensors` -> `load_all_data` ->
`ggml_backend_meta_buffer_set_tensor` -> `ggml_backend_tensor_set_2d` -> `ggml_backend_tensor_set`

Loader state at death:

```
load_tensors: offloaded 44/44 layers to GPU
load_tensors:   CPU_Mapped model buffer size = 46410.60 MiB
load_tensors:   CPU_Mapped model buffer size = 26137.35 MiB
load_tensors:       Meta() model buffer size =  3855.96 MiB
```

I instrumented the assert to name the tensor:

```
OOB write: tensor=blk.0.attn_output_a.weight type=q8_0 ne=[4096,8192,0,1]
           nbytes=0 offset=0 size=35651584 overflow=35651584
```

**`ne[2] = 0`** — zero-width slice, so `ggml_nbytes() = 0`, and the loader then writes
**35,651,584 bytes**, which is the *whole* tensor (4096 x 8192 at q8_0 = 34 B / 32 elem
= 35,651,584 exactly).

So allocation and load disagree completely: the split-state gives this device **none** of
`attn_output_a` while the loader believes it holds **all** of it. `attn_output_a` matches
`pattern_attn_out_weight` (`attn_output(_[ab])?\.weight`) and is part of the grouped output
projection work in this commit. Same zero-width-slice family as the GQA case, just surfacing at
load time instead of graph time.

Did not run `-ts 3,4,4,1`, since you asked to gate it on the even case passing. Happy to run it
anyway if the failure mode would be useful to compare.

## 3. On the performance recommendation

Flagging this because I think my earlier number led you somewhere I no longer stand behind — I
posted a correction around the same time you commented, so it may have crossed.

The 6.20 vs 15.85 tok/s result is real, but it is a property of **Flash-Next**, not of the
topology. Same box, same day, same build, `Qwen3.8-27B-Q6_K` via `llama-bench`:

| arm | tg128 |
|---|---|
| 2 GPU, `-sm layer` | 7.83 |
| 2 GPU, `-sm tensor` | **13.20** |
| 4 GPU, `-sm tensor` | **15.8** (best of 4; see below) |

Tensor split is ~**1.7x faster** than layer split on dense 27B on exactly this PCIe/NUMA machine,
and that matches an independent run from a week earlier (13.00 / 15.34) on a different build — so
no regression either.

Flash-Next loses because it has ~6B active parameters and `n_ff_exp = 640`; split 4 ways that is
a 160-wide expert matmul per card, far too little to keep a P100 busy while still paying an
all-reduce on each of 48 layers. Dense 27B has ~4.5x the active parameters and `n_embd = 5120`,
so its split matmuls stay large enough to win.

One caveat on my own numbers: the 4-GPU arm is **bistable** unbound — 12.80, 12.56, 15.83, 15.75
across four runs, two clean modes. `numactl --cpunodebind=0 --membind=0` or `--interleave=all`
removes the slow mode (4/4 bound runs >= 14.68). Worth binding for any 4-way number on a
dual-socket box.

So I'd suggest the guidance is **"tensor split is a win when there is enough per-layer compute to
amortise the all-reduce — dense models yes, small-active-parameter MoE no"**, rather than a
blanket warning about machines without peer links.
