# Flash-Next structural-tensor audit: full quants all clean, the shared MTP head is not

**Date:** 2026-09-07 · **Node:** `.194` (files already on disk; no downloads)
**Prompted by:** TheTom/llama-cpp-turboquant **PR #362** (Jas Strong, opened 2026-09-07)
**Raw:** `.194:~/structcheck.log`, script `~/structcheck.sh`

## What PR #362 claims

Patch 2 of #362 adds an unconditional quantizer guard in `src/llama-quant.cpp` for five
qwen4exp tensor classes:

```
ssm_alpha.weight   ssm_beta.weight            state-space gains — set the decay of the recurrence
hc_attn_inject.weight   hc_ffn_inject.weight  hyper-connection injection — how the token embedding enters each layer
ple_conv1d.weight                             n-gram conv kernel
```

His stated failure mode, verbatim: *"A 4-bit copy of them leaves a model that loads, runs at
full speed and answers every prompt with the same text, because its input never reaches the
residual."* Silent and total — no crash, no slowdown, no warning.

## Audit of what we hold

`gguf_dump.py` (metadata only, no weight loading) over every shard of every Flash-Next
artifact on `.194`.

| artifact | structural tensors | types |
|---|---:|---|
| `Qwen3.8-Flash-Next-UD-IQ4_XS` (3 shards) | 169 | **all F32** |
| `Qwen3.8-Flash-Next-UD-Q2_K_XL` (3 shards) | 169 | **all F32** |
| `Qwen3.8-Flash-Next-UD-IQ1_S` (3 shards) | 169 | **all F32** |
| `mtp-Qwen3.8-Flash-Next-shared-Q8_0` | 2 of the five classes | **Q8_0** |

**The full quants are clean, including `UD-IQ1_S`** — a 1-bit quant that still keeps all 169
structural tensors at full precision. Whatever recipe unsloth is using already protects these
without the guard existing.

Shard 1 of each split reports `tensor_count = 0`: those are metadata-only shards, not a
read failure. See the method note below on why that distinction had to be established.

## The MTP head

```
blk.48.hc_attn_inject.weight        40960 | 10240,4      Q8_0   <- protect list
blk.48.hc_ffn_inject.weight         40960 | 10240,4      Q8_0   <- protect list
blk.48.nextn.eh_proj.weight      13107200 |  5120,2560   Q8_0
blk.48.nextn.hc_head_down.weight  3276800 | 10240,320    Q8_0
blk.48.nextn.hc_head_up.weight    3276800 |   320,10240  Q8_0
blk.48.nextn.enorm/hnorm/hc_head_norm.weight             F32
```

Two of the five protected classes are quantized here where every full-model quant keeps them
F32. `qwen4exp.nextn_shared_target_tensors = True`, and it carries its own
`blk.48.nextn.hc_head_*` — the tensors patch 3 of #362 teaches `graph_mtp` to prefer.

**This is not a demonstrated defect, and should not be reported as one:**

- #362's failure mode is stated for a **4-bit** copy. Q8_0 is 8-bit. Nothing here establishes
  harm at that precision; the guard is simply unconditional.
- The saving is negligible — 40,960-element tensors, ~120 KB each against a 2.6 GiB file.
  The argument is the **asymmetry** (no upside, unquantified downside), not a measurement.
- **Provenance is not established.** Metadata carries only `general.name = 'Ckpt_Q38'`,
  `general.size_label = '512x95M'`, `general.file_type = 7`. No repo, no URL, no
  `quantized_by`. Attribution to any publisher would be a guess.

**Untested, and testable:** whether a draft head with Q8_0 injection matrices drafts worse
than one with F32. Acceptance rate against the same target would answer it directly. #362
reports 86.4% acceptance with "the published head" — if that is this file, the guard's
protection is worth less than its wording implies, at least at 8-bit.

## Method note — a null was nearly published

The first run of this audit returned **zero hits across all four artifacts in three seconds**
and would have been reported as "everything is clean". It was a silent failure: the script
passed `--no-metadata`, which `gguf_dump.py` does not accept, so every invocation exited on
an argparse error into a `2>/dev/null`. The grep then found nothing, as it must.

Three seconds for four multi-shard 70–90 GB models is the tell. The rerun captures `rc`,
captures stderr, and prints a per-file tensor-line count as a positive control, so a genuine
null is distinguishable from a broken pipeline. That distinction is what turned "shard 1 has
no tensors" from a suspected bug into a confirmed property of the split format.

Cross-ref `FAILURE_MODES.md` **AFM-7** (silent partial failure behind a success exit code).
