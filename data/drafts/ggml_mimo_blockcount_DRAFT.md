`MiMo-V2.6-Distill-Qwen-9B-GGUF` declares 33 blocks and ships 32, so it will not load

The GGUFs under `ggml-org/MiMo-V2.6-Distill-Qwen-9B-GGUF` fail to load on current
`llama.cpp`, including on a build of HEAD from the same day:

```
llama_model_load: error loading model: check_tensor_dims:
  tensor 'blk.32.attn_norm.weight' not found
```

**Cause.** The file sets `qwen35.block_count = 33` but contains blocks **0..31**, i.e. 32. The
loader trusts the metadata, looks for `blk.32`, and stops.

The same file also carries `qwen35.attention.recurrent_layers`, an array **indexed by layer**,
with **33 entries** (`[true,true,true,false]` x8 then a final `false`). An array indexed by layer
cannot be longer than the layer stack, so the file is internally inconsistent by its own
metadata, independent of any loader.

**Reproduced on both a fork and upstream, with a positive control.** RX 9070 XT (gfx1201),
`-c 4096 -ngl 99 -fa on -np 1`:

| file | `ggml-org/llama.cpp` 58367713a | buun-llama-cpp 38ada0e1b |
|---|---|---|
| `MiMo-V2.6-Distill-Qwen-9B-Q8_0` (ggml-org) | fails, above error | fails, identical |
| `Ornith-1.5-9B-Q8_0` (a different qwen35 9B) | **loads and generates** | loads and generates |

The control matters: the same binary that rejects the MiMo file serves Ornith, which declares
`block_count = 33` and actually ships blocks 0..32 -- including `blk.32.nextn.{eh_proj, enorm,
hnorm, shared_head_norm}`. On that file the server logs `model has unused tensor
blk.32.nextn.enorm.weight -- ignoring` and runs normally. So block 32 is the MTP block by
convention, and the MiMo conversion has it declared but absent.

A third-party quant of the same model (`holooo/...-Q5_K_S-GGUF`) shows the same 33-declared /
32-shipped split, and additionally drops `recurrent_layers` entirely -- so the two conversions
differ in other respects while agreeing on this one, which points at the shared conversion path
or the source config rather than at either packager.

**What I have not checked:** whether `XiaomiMiMo/MiMo-V2.6-Distill-Qwen-9B` ships a 33rd layer
that conversion drops, or declares 33 while shipping 32. That decides whether the fix belongs in
`convert_hf_to_gguf.py` or in the source config, and I did not want to hold the report for it.

Happy to test a fix -- the hardware and both files are here.
