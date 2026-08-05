# A community TurboQuant GGUF is unloadable because the type-id enum drifted inside the fork

**Node `.73`, 2× Tesla P100-PCIE-16GB (sm_60), 150 W cap. 2026-08-03.**
Builds: `TheTom/llama-cpp-turboquant` `d0e2a8b64` (v10281, pre-#256) and `6aa97d810` (v116, post-#256).

## Summary

`Qwen3.6-35B-A3B-UD-Q8_K_XL-TQ4_1S.gguf` (MarcelloG, HF) **fails to load on both builds**, 0.2 s in,
before any GPU work. The file is neither corrupt nor mislabeled: it contains **genuine TQ4_1S data**
declared under tensor type id **45**, which current builds read as **TQ3_1S**. The two types have
different block sizes, so the loader walks off the data region.

This is **intra-fork enum drift**, not a cross-fork collision — and nothing in the file records which
fork version produced it.

## The failure

Identical on both builds (`-ngl 99`, `-c 4096`):

```
E gguf_init_from_reader: tensor 'blk.2.ffn_gate_inp.weight' has offset 3221374464, expected 3187820032
E gguf_init_from_reader: failed to read tensor data
E llama_model_load: error loading model: llama_model_loader: failed to load model
```

Shortfall = 3221374464 − 3187820032 = **33,554,432 B = exactly 32 MiB**.

## Root cause, from the file's own tensor offsets

Header-only probe (`~/tensor_bpb.py` — parses metadata + tensor-info block, never reads the tensor
region), deriving actual on-disk bytes per block from consecutive tensor offsets:

| declared type | example tensor | elements | bytes | **B per 32 vals** | bpw |
|---|---|---|---|---|---|
| `?45` | `blk.2.ffn_gate_exps.weight` | 268,435,456 | 167,772,160 | **20.000** | **5.00** |
| `Q4_K` | `blk.2.ffn_down_exps.weight` | 268,435,456 | 150,994,944 | 18.000 | 4.50 |
| `Q8_0` | `blk.0.ffn_down_exps.weight` | 268,435,456 | 285,212,672 | 34.000 | 8.50 |

Against the current definitions in `ggml/src/ggml-common.h` (both `blck_size = 32`):

| type | struct | bytes/block | bpw |
|---|---|---|---|
| `TQ3_1S` | `block_tq3_1s` (`static_assert(sizeof == 16)`) | **16** | 4.00 |
| `TQ4_1S` | `d0` fp16 + `d1` fp16 + 16 B packed 4-bit indices | **20** | 5.00 |

The on-disk payload is **20 B/block → TQ4_1S**. The loader assumes 16 B/block → a **4 B per block**
deficit.

**The arithmetic closes exactly.** Exactly one type-45 tensor (268,435,456 elements) precedes
`blk.2.ffn_gate_inp`:

```
268,435,456 / 32 = 8,388,608 blocks
8,388,608 × 4 B  = 33,554,432 B = 32 MiB   ← the reported offset delta, to the byte
```

## Where id 45 came from — drift in TheTom's own history

Every historical assignment of these ids, over the 400 most recent commits touching
`ggml/include/ggml.h`:

| assignment | commits |
|---|---|
| `TQ3_1S = 45`, `TQ4_1S = 46` | 18 (**current**) |
| `TQ3_1S = 44` | 10 |
| **`TQ4_1S = 45`** | **2** |

The `TQ4_1S = 45` window is two commits wide:

```
74f2160de  2026-04-01  feat: TQ3_1S + TQ4_1S weight quantization with V2.1 fused Metal kernels
e9c54d557  2026-04-03  fix: remove redundant extern from GGML_API macro (GCC 13.3 hard error)
```

i.e. the feature-introduction commit itself. A file quantized in that window declares TQ4_1S as 45;
every build since reads 45 as TQ3_1S.

## The file carries no TQ provenance at all

`general.*` metadata on both community TQ files:

| key | MarcelloG MoE | MidnightPhreaker dense |
|---|---|---|
| `general.quantized_by` | **Unsloth** | **Unsloth** |
| `general.file_type` | **7** (= Q8_0) | **7** (= Q8_0) |
| `general.quantization_version` | 2 | 2 |
| `quantize.imatrix.file` | `imatrix_unsloth.gguf` | — |

Both are Unsloth base quants that a third party re-quantized to TQ afterward. **The TQ step stamped
nothing** — it did not set `quantized_by`, did not update `file_type` (still claims Q8_0), and left
no tool or version field. So a TQ GGUF cannot be attributed to a fork or a build date from its own
metadata. The type id is the only signal, and it is exactly the thing that drifted.

## Control: the dense file is consistent

`Qwen3.6-27B-MTP-TQ4_1S.gguf` (MidnightPhreaker) declares type **46** and its payload measures
**20.000 B per 32 vals** — matching current `TQ4_1S`. It loads.

So the two files carry **byte-identical block layouts under two different declared ids**. That is
what isolates the cause to the fork version at quantization time rather than to the data.

## Consequences

1. **Filenames are not authoritative for TQ interchange, and neither is metadata.** Both files are
   named `TQ4_1S`; one is id 45, the other 46. Read the type id and, if it matters, verify the
   bytes-per-block from tensor offsets — that check is header-only and takes under a second.
2. **A user hitting this sees only "failed to read tensor data"** — an error that reads like a
   corrupt download. The natural response is to re-download, which cannot help.
3. **Recovery looks possible without re-quantizing**: rewrite the declared id 45 → 46 in the
   tensor-info block (108 `u32` fields), which reproduces exactly the dense file's working
   configuration. This is only valid if TQ4_1S block *semantics* (WHT rotation, Lloyd-Max centroids)
   are unchanged since April, which equal block size suggests but does not prove — so a patched file
   must be coherence-checked, not assumed good. **Tested separately; see `TQ_ENUM_DRIFT_RECOVERY.md`.**
4. A `general.quantization.tool` / version stamp written at TQ quantization time would make this
   diagnosable from the file alone.

## Scoring against pre-registration

`TQ_WEIGHT_TYPE_PREDICTIONS.md` framed a 2×2 coherence gate over {OLD, NEW} × {garbage, coherent}.
The actual outcome is **off that grid**: the model never loads on either build, so the fused-kernel
question this file was meant to probe is untested by it.

- **P-TQ1 (0.55, MoE garbage on OLD) — UNSCORABLE.** No load, no kernel, no output.
- **P-TQ2 (0.85, MoE coherent on NEW) — UNSCORABLE.** Same.
- **P-TQ3 (0.7, NEW slower than OLD on the MoE) — UNSCORABLE.** Same.

The pre-registered table did anticipate "garbage on BOTH builds → the file is not Tom-format
TQ3_1S; type 45 means something else in the producing fork." That reading was **right about the
cause and wrong about the symptom** — the mismatch is caught by offset arithmetic at load, and never
reaches the point where it could produce garbage. Predicting a *runtime* failure mode for what is a
*structural* one is the error worth keeping: a block-size difference between two candidate types is
checkable statically, and I should have checked it before designing a coherence gate around it.

`c29f0d1cd` (disable fused TQ3_1S `mul_mat`) is therefore **irrelevant to this file** — it was never
TQ3_1S data. Testing that fix needs a real TQ3_1S model, which is not on disk.
