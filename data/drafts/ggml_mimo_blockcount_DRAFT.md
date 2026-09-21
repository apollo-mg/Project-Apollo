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

**Root cause.** The source declares an MTP block it does not ship, and the converter trusts the
declaration. From `XiaomiMiMo/MiMo-V2.6-Distill-Qwen-9B` -- config and tensor index only, no
weights downloaded:

```
config.json    num_hidden_layers     : 32
               layer_types entries   : 32
               mtp_num_hidden_layers : 1      <-- declared
safetensors    layer indices         : 0..31 (32)
               mtp.* / nextn tensors : 0      <-- absent
```

`conversion/qwen.py:298-305`, `_QwenMtpMixin.__init__`:

```python
self.block_count = self.hparams["num_hidden_layers"]        # 32
if not self.no_mtp:
    n_mtp = self.hparams.get("mtp_num_hidden_layers", 0)    # 1
    ...
    self.block_count += n_mtp                               # 33
```

`n_mtp` comes from the config and is added **unconditionally** -- nothing checks that the `mtp.*`
tensors are present in the checkpoint. For a model that declares the block and ships no weights
for it, `block_count` ends up one higher than the blocks emitted, and `recurrent_layers`, sized
from the same count, inherits the extra entry.

**Workaround, untested.** `--no-nextn` sets `no_mtp`, which skips the increment, so converting
this repo with that flag should yield a loadable GGUF at `block_count = 32`. I have not run it --
that needs the ~18 GB of safetensors -- so it is a reading of the code, not a measurement.

**Fix directions:** gate the increment on the `mtp.*` tensors actually being indexed, or warn
when `mtp_num_hidden_layers > 0` and none are found. Either beats emitting a file whose own
`recurrent_layers` array contradicts its tensor list.

Happy to test a patch -- the hardware and both files are here.
