# Result — every MiMo-Distill GGUF tested declares 33 blocks and ships 32, including ggml-org's own

**2026-09-21, RX 9070 XT (gfx1201), buun `38ada0e1b`.** The MTP-head-transfer experiment
(`PREREG_MTP_HEAD_TRANSFER.md`) never reached its first arm: the target model is unloadable.
**P1 FALSIFIED**, and for a reason that is worth more than the experiment was.

## The finding

`holooo/MiMo-V2.6-Distill-Qwen-9B-Q5_K_S-GGUF` fails to load, with or without a draft head:

```
E llama_model_load: error loading model: check_tensor_dims:
  tensor 'blk.32.attn_norm.weight' not found
```

Its metadata declares `qwen35.block_count = 33`. It ships blocks **0..31**, i.e. **32**.

## The positive control makes it a packaging fault, not a loader fault

Same binary, same session, same flags (`-c 4096 -ngl 99 -fa on -ctk f16 -ctv f16 -np 1`), same
architecture, one card:

| file | metadata `block_count` | blocks present | `nextn` tensors | result |
|---|---:|---|---:|---|
| `Ornith-1.5-9B-Q5_K_M` | 33 | **0..32** (33) | 4 | **loads, generates** |
| `mimo-v2.6-distill-qwen-9b-q5_k_s` | 33 | **0..31** (32) | **0** | **fails** |

Ornith proves the convention and the loader: **block 32 is the MTP block**, carrying
`blk.32.nextn.{eh_proj,enorm,hnorm,shared_head_norm}` alongside an ordinary attention/FFN stack.
Launched without `--spec-type draft-mtp`, Ornith logs `model has unused tensor
blk.32.nextn.enorm.weight -- ignoring` and serves normally.

MiMo declares the same 33 and ships none of it. The loader trusts the metadata, looks for
`blk.32.attn_norm.weight`, and stops.

## UPDATE, same day: it is not one packager — ggml-org's own build has it too

Two more quants arrived and were inspected before launching anything.

| file | packager | `block_count` | blocks present | `recurrent_layers` entries | `nextn` | loads? |
|---|---|---:|---|---:|---:|---|
| `mimo-…-q5_k_s` | `holooo` | 33 | **0..31** (32) | **0** (absent) | 0 | **no** |
| `MiMo-…-Q8_0` | **`ggml-org`** | 33 | **0..31** (32) | **33** | 0 | **no** |
| `Ornith-1.5-9B-Q8_0` | ornith-ai | 33 | 0..32 (33) | absent | 4 | **yes** |

**`ggml-org` is the llama.cpp project's own org**, so this is not a community packaging slip.
Two independent conversions, different in other respects — `holooo` dropped
`qwen35.attention.recurrent_layers` entirely, `ggml-org` kept it — and **both** land on
`block_count = 33` with 32 blocks on disk.

**ggml-org's build carries the proof that 33 is intended.** Its
`qwen35.attention.recurrent_layers` is an array **indexed by layer** with **33 entries**
(pattern `[T,T,T,F] x 8` then a final `F`), against 32 blocks in the same file. An array
indexed by layer cannot be longer than the layer stack. Index 32 describes a block that is
not there.

So the file is internally inconsistent by its own metadata, independent of any loader.

## SETTLED — it fails on upstream llama.cpp too, on ggml-org's own loader

Built `ggml-org/llama.cpp` at **`58367713a`** (2026-09-21 14:49 PDT, HEAD on the day) for
gfx1201 and loaded both files on it. Same binary, same session, same flags
(`-c 4096 -ngl 99 -fa on -np 1`):

| file | packager | upstream `58367713a` | buun `38ada0e1b` |
|---|---|---|---|
| `MiMo-V2.6-Distill-Qwen-9B-Q8_0` | **ggml-org** | **fails** — `check_tensor_dims: tensor 'blk.32.attn_norm.weight' not found` | fails, identical error |
| `Ornith-1.5-9B-Q8_0` | ornith-ai | **loads, generates** | loads, generates |

**So it is not a fork divergence.** buun and upstream behave identically, and the positive control
rules out the build: the same upstream binary that rejects the MiMo file serves the Ornith file,
logging `model has unused tensor blk.32.nextn.enorm.weight -- ignoring` and answering normally.

**The llama.cpp project published a GGUF that the llama.cpp reference loader rejects.** That is
the reportable finding, and it is stronger than the packaging story this receipt opened with.

Because upstream and fork agree, the earlier question of "which half is wrong" narrows: the
defect is upstream of both loaders, in the conversion or in the source config, not in anyone's
tensor-dims check.

## Which half is wrong is not determined here

Two candidates, and this run cannot separate them without the upstream safetensors:

1. the conversion **stripped the MTP block** and left `block_count` at 33, or
2. `block_count` was taken from a config that **counts the MTP layer** while the quantiser never
   wrote it.

Either way the artefact is internally inconsistent, which is the reportable part. Note
`qwen38-packagers/RESULT_MTP_HEAD_QUANT.md` already found that **no imatrix covers the MTP head
in either ladder** — heads are quantised blind — so this block is the least-attended part of the
file and an easy one to drop silently.

## What it cost, and why that is the point

Fifteen minutes, because `[[file-identity-is-the-hash-not-the-name]]` discipline meant reading
the tensor list before trusting the label. Someone taking the quant at face value gets a
`check_tensor_dims` error naming a tensor that is *present* in the standalone head file they
may also have downloaded, which points diagnosis in exactly the wrong direction — that was my
own first reading of it.

## Consequence for the transfer experiment

`PREREG_MTP_HEAD_TRANSFER.md` is **blocked, not answered.** Its question — does an MTP head
trained on fine-tune A draft for fine-tune B of the same base — remains open and remains
unpublished as far as I can find. Two further facts from the same inspection sharpen it:

- **`Ornith-1.5-9B-Q5_K_M` already embeds its own MTP head**, so the standalone
  `mtp-Ornith-1.5-9B-head-Q8_0.gguf` is redundant *for Ornith*. The matched-control arm needs no
  separate file.
- The standalone head is a complete, well-formed MTP block (18 tensors: `token_embd`, `output`,
  `output_norm`, and a full `blk.32.*` with the four `nextn` tensors), vocab **248,320** —
  identical to both targets. **It is the transfer target that is broken, not the head.**

To run the experiment, the transfer arm needs either a MiMo GGUF that loads, or the head grafted
into MiMo as `blk.32` — and that graft would itself be the interesting artefact.

## What this does NOT establish

- **Nothing about MiMo-V2.6-Distill-Qwen-9B the model.** This is one third-party quant of it.
  The model may be fine; this file is not.
- ~~**Not confirmed against mainline llama.cpp**~~ — **now confirmed**, see the SETTLED section.
  Upstream `58367713a` fails identically, with a positive control passing on the same binary.
- **The upstream safetensors were still not inspected.** Whether
  `XiaomiMiMo/MiMo-V2.6-Distill-Qwen-9B` ships a 33rd layer that conversion drops, or declares 33
  while shipping 32, remains open — and it decides whether the fix belongs in
  `convert_hf_to_gguf.py` or in the model card. Reporting the inconsistency does not require
  answering it.
- **The upstream repo was not inspected.** Whether `XiaomiMiMo/MiMo-V2.6-Distill-Qwen-9B` ships
  an MTP layer at all is unchecked, and it decides which of the two candidate causes applies.
- **No quality or speed number for either model** — neither ran a benchmark arm.
