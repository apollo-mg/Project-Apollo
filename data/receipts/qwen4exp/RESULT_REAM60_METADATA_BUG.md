# REAM-60Pct GGUF does not load: the pruning pipeline zeroed `compress_ratios`

**2026-09-02.** `mradermacher/Qwen3.8-Flash-Next-REAM-60Pct-i1-GGUF` @ `i1-Q2_K` (56.62 GiB),
base `Akicou/Qwen3.8-Flash-Next-REAM-60Pct`. `.194`, buun `7a918624b`, sm_60.

## Symptom

Load fails in **6 seconds**, before any inference:

```
E llama_model_load: error loading model: error loading model hyperparameters:
    qwen4exp.attention.compress_ratios[3] must be in [1, 64] for attention layers
```

## Cause — a 12-value metadata difference

`qwen4exp.attention.compress_ratios` is a 48-element int32 array, one per block:

```
unpruned UD-Q2_K_XL : [0,0,0,4, 0,0,0,4, 0,0,0,4, ... ]   4 at every 4th index
unpruned UD-IQ4_XS  : [0,0,0,4, 0,0,0,4, 0,0,0,4, ... ]   identical
REAM-60Pct i1-Q2_K  : [0,0,0,0, 0,0,0,0, 0,0,0,0, ... ]   ALL ZERO
```

Differing indices: **12 of 48 — exactly `3, 7, 11 … 47`, the attention layers.** `0` is the
"not an attention layer" sentinel; the loader rejects it on a layer that *is* one.

**Expert pruning has nothing to do with attention compression ratios.** This is collateral damage
in the REAM conversion, and it makes the artifact unloadable on llama.cpp as published. The model
metadata is otherwise coherent — `expert_count = 308` (60.2 % of 512), `expert_used_count = 10`
unchanged.

## Repair

The correct values are known from the unpruned build, so the file can be patched in place —
12 int32 writes, no size change:

```
array data offset 2176, elem_type 5 (int32), n 48
write 4 at offset 2176 + i*4 for i in 3,7,11,...,47      (reversible: write 0 back)
```

After patching, the model loads and initialises normally.

**A guard earned its keep here:** the first patch attempt asserted `elem_type == 4` (uint32),
which was wrong — the array is int32 (type 5). The assert aborted before writing anything. A
silent 12-value write with the wrong pack format into a 56 GiB file would have been unpleasant to
diagnose.

## Worth reporting upstream

Two candidates: `Akicou` (the pruned base, where the ratios were presumably lost) and
`mradermacher` (the GGUF conversion). The diff against the unpruned build makes it a one-line
report, and the artifact is unusable without it.

## Scope

This receipt covers **loadability only**. Whether 40 % expert pruning damages output quality is a
separate question, measured against the unpruned control in the trial alongside this file. The
metadata bug tells us nothing about that either way — it is a packaging fault, not a model fault.
