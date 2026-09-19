# Finding -- Atlas already has PrismML ternary kernels, and they are already built for gfx1201

**2026-09-18.** Source reading, not a measurement. Prompted by Mark asking whether Atlas has any
ternary codec that would work with PrismML's Ternary-Bonsai, on the guess that Bonsai was probably
never a target given the hardware Avarok works with.

**The guess was half right in an interesting way: the model is not a target, but the codec is
supported, and it is compiled into the binary built in S2.**

## What is there

`kernels/gb10/common/q2_0_gemv.cu`, header comment verbatim:

```
// Atlas native ternary Q2_0 decode GEMV -- keep-packed W2A16 for M=1..8 decode.
//
// The weight NEVER expands to BF16: each 34-byte (group-128) / 18-byte (group-64)
// PrismML `block_q2_0` stays packed in VRAM and is dequantized inside the
// dot-product, exactly like `w4a16_gemv.cu`/`w8a16_gemv.cu` do for NVFP4/FP8.
//
// Q2_0 block layout (PrismML id 42, validated in `dequant_gguf_bf16.cu`):
//   [ fp16 d @ front ][ group/4 bytes of 2-bit codes, low-bits-first ]
//   code = (qs[j>>2] >> (2*(j&3))) & 3;   value = (code - 1) * d
//   -> symbols {-1, 0, +1, +2}. Scale `d` is inline (one per group)
```

And `crates/spark-runtime/src/weights/gguf.rs` names Bonsai directly:

```
//! The PrismML `Q2_0` (id 42) group size is not encoded in the type id. It
//! defaults to group-128 (the shipped Ternary-Bonsai layout); set
//! `AVAROK_GGUF_Q2_GROUP=64` for the fork-master group-64 layout.
```

So Atlas carries a GGUF reader, a `WeightDtype::PackedQ2_0` keep-packed path, and three kernels:
`q2_0_gemv.cu`, `q2_0_gemv_vec.cu`, `q2_0_mmq.cu`.

## They are live on this board, not gb10-only

| kernel | in gb10 | in the r9700 mirror | compiled in S2 |
|---|---|---|---|
| `q2_0_gemv.cu` | yes | **yes** | `t0__q2_0_gemv.o` |
| `q2_0_gemv_vec.cu` | yes | **yes** | `t0__q2_0_gemv_vec.o` |
| `q2_0_mmq.cu` | yes | **yes** | `t0__q2_0_mmq.o` |
| `dequant_gguf_bf16.cu` | yes | **yes** | built |

None appear in the `[kernels] absent` list in `kernels/r9700/HARDWARE.toml`, and all three object
files are present in `target/` from last night's 176-kernel build. **The ternary decode path
compiles for gfx1201 and is sitting in the `spark` binary already on this machine.**

## The precise limits of the claim

1. **This is Q2_0 only.** Ternary-Bonsai 2 ships two packings: `PTQ1_0` (dense trits, ~1.75
   bits/weight, 5.95 GB for the 27B) and `PQ2_0` (2-bit slots, ~2.13 bits/weight, 7.21 GB). Atlas
   implements ggml id 42 at group-128, which matches the `PQ2_0` shape and Bonsai's stated
   "FP16 group-wise scaling per 128 weights". **There are no `q1_0` kernels** anywhere in the
   tree, so the smaller 5.95 GB packing has no decode path here.
2. **"Ternary" is the comment's word, not the symbol set.** The decode is
   `value = (code - 1) * d` over a 2-bit code, giving **{-1, 0, +1, +2}** -- four symbols, not
   three. Worth knowing before assuming bit-exact equivalence with a strict trit format.
3. **Bonsai is not a declared model target.** No `MODEL.toml` under any `kernels/*/` names prism
   or bonsai. The codec exists; the model wiring does not.
4. **Nothing here has been run.** This is a source reading and an object-file listing. No Bonsai
   weights have been loaded, and the group-size default, the GGUF path, and the keep-packed
   residency are all untested on this hardware.

## TESTED 2026-09-18: it does not load. Atlas implements id 42; Bonsai 2 ships id 142

Mark pulled `Ternary-Bonsai-2-27B-PQ2_0.gguf` (7,206,168,928 bytes, sha256
`3907dc1658db1f78a9826bf8d5bcb8dc65db0d466388937af57f2294fae62ec1`, verified
2026-09-18T16:04:34Z). Pointed `spark serve` at a directory containing it:

```
Error: Failed to build ModelConfig from GGUF metadata
    0: failed to parse GGUF metadata: Ternary-Bonsai-2-27B-PQ2_0.gguf
    2: unsupported ggml type id 142
```

Header parse of the file itself:

| property | value |
|---|---|
| GGUF version | 3, 851 tensors, 49 metadata keys |
| `general.architecture` | `qwen35` (Atlas **does** know this string) |
| quantized tensors | **402 of ggml type 142**, plus 353 F32 and 96 BF16 |
| `general.file_type` | 141 |
| Hadamard metadata | `prism.hadamard.{version,block_size=1024,transform,axis,sign_mode,sign_values=128048,...}` |

`crates/spark-runtime/src/weights/gguf/container.rs:127` maps `42 => Q2_0`. **142 appears nowhere
in the weights reader.** The source reading and the empirical failure agree exactly.

**Two corrections to what I wrote above this section.**

1. **I called this potentially "a 20-minute experiment". It is not.** The header claim that Atlas
   supports "the shipped Ternary-Bonsai layout" is true for the id-42 era, which is almost
   certainly **Bonsai v1** -- the release tested on this machine earlier in 2026. Bonsai 2 moved
   the type id.
2. **I implied the Hadamard machinery in the tree might be the matching support. It is not.**
   `wht_bf16.cu` is *"applied per-head to Q before turbo paged decode"* -- KV cache, not weights.
   `tq_plus_signs.cuh` is *"TurboQuant+ Rademacher sign arrays"*, from the Google TurboQuant
   line, also KV-side. **TQ there is TurboQuant, not Ternary Quant.** Atlas parses **no**
   `prism.*` metadata key at all, so the weight-space rotation Bonsai requires is unaddressed.

## What the gap actually is

**Encouraging:** the block arithmetic matches. Atlas describes a 34-byte group-128 `block_q2_0`
(2-byte fp16 scale + 32 bytes of 2-bit codes), which is 34*8/128 = **2.125 bits/weight**. Bonsai
2's card states PQ2_0 is **2.13 bits/weight** at "FP16 group-wise scaling per 128 weights". Those
are the same layout to the digit.

**So the type id may be the only container-level difference.** That is a hypothesis consistent
with the arithmetic, not a tested claim, and it is cheap for someone to check by decoding one
tensor both ways.

**Unresolved and larger:** Bonsai applies a blockwise Hadamard rotation before quantization and
requires the matching transform on activations at runtime. The file carries the parameters to do
it (block size 1024, sylvester-walsh-hadamard, explicit sign mode, 128048 sign values). Atlas
reads none of them. Either Bonsai v1 did not use this rotation, or Atlas's id-42 path has an
assumption about it somewhere I did not find. **Until that is answered, adding `142` to the type
map would produce a model that loads and emits garbage**, which is a worse outcome than the clean
refusal we get today.

## The two packings need separate plumbing, not a shared path

Header-only comparison, fetched by HTTP range request without downloading either file whole
(PTQ1_0 header read from the first 32 MB):

| | PQ2_0 | PTQ1_0 |
|---|---|---|
| ggml tensor type id | **142** | **143** |
| `general.file_type` | 141 | 143 |
| quantized tensors | 402 | 402 |
| other tensors | 353 F32 + 96 BF16 | 353 F32 + 96 BF16 |
| `general.architecture` | `qwen35` | `qwen35` |
| bits/weight (card) | 2.13 | 1.75 |
| size | 7.21 GB | 5.95 GB |

Same architecture, same tensor census, same Hadamard metadata schema. **Different type ids and
different packing.**

The packing difference is the part that matters, and it is not cosmetic:

- **PQ2_0** is 2-bit slots: 34 bytes per group-128 (2-byte fp16 scale + 32 bytes of codes),
  4 codes per byte, unpacked with `(qs[j>>2] >> (2*(j&3))) & 3`. That is a shift and a mask.
  **Atlas already implements exactly this** in `q2_0_gemv.cu` at id 42.
- **PTQ1_0** is dense trits: 1.75 bits/weight means 28 bytes per group-128, so 26 bytes of codes
  for 128 trits. 26 bytes at 5 trits/byte gives 130 slots for 128 values, which is base-3 packing
  (3^5 = 243 fits in a byte). Unpacking needs repeated divide/modulo by 3 or a 256-entry lookup
  table per byte. **Atlas has no kernel of that shape anywhere**, and it is not a small edit to
  the existing one -- the inner loop changes.

So the two are not "the same codec at two sizes". PQ2_0 is a type-id bump away from Atlas's
existing decode math; PTQ1_0 needs a new kernel written.

**Correction to my earlier PQ2_0 parse:** I reported `prism.hadamard.sign_values = 128048`. That
was a bug in my first header parser (it printed a file offset, not the value). The PTQ1_0 read,
done with a corrected parser, shows `sign_values = <28672 values, elem type 5>` alongside
`weight_names = <401 strings>` and `sign_widths = <3 values>`. Both files carry the same metadata
schema; the 128048 figure should be disregarded.

**The model card confirms the rotation is mandatory**, in PrismML's own words: *"the packed model
declares its rotation as metadata, so a runtime either applies the matching transform or refuses
to load the file."* That is the exact failure mode I flagged above. A runtime that ignores
`prism.hadamard.*` and decodes the weights anyway gets a rotated basis it never un-rotates.

## Why it matters

Atlas's own 27B target, `Qwen3.8-27B-NVFP4`, is 19.4 GB resident and **does not fit this 16 GB
board** -- that is why the PRD makes it a non-goal and targets the 9B instead.

Ternary-Bonsai 2 is **the same base model**, Qwen3.8-27B, at 7.21 GB in the `PQ2_0` packing Atlas
appears to support. If the path works, the 27B that this card cannot serve as NVFP4 becomes a
model it could serve, on a stack that already compiles the kernels for it.

That is a hypothesis with a clear test, not a result. The cheapest next step is to pull the
`PQ2_0` GGUF and see whether `spark` loads it at all -- which would also be the first exercise of
Atlas's GGUF reader on this board, a path S0-S4 has not touched.

## Prior art on this machine

Bonsai v1 was tested here earlier in 2026 via a llama.cpp fork and performed well;
`engines/llama_cpp_bonsai` is that checkout. Bonsai 2 needs `PrismML-Eng/llama.cpp` because stock
llama.cpp rejects `PQ2_0`/`PTQ1_0` as unknown types. So a llama.cpp-vs-Atlas comparison on the
same ternary weights is available if wanted, which would be a genuinely novel measurement: nobody
has published ternary decode throughput on RDNA 4 through two different engines.

## Suggested question for TheTom

The codec is in the tree and builds for gfx1201, but no model declares it. Is the Q2_0 path
considered working and just unwired, or is it half-landed? That determines whether trying
Ternary-Bonsai on this board is a 20-minute experiment or a project.
