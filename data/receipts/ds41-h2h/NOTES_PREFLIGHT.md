# DeepSeek-V4.1-Flash-1017 head-to-head: preflight notes (2026-11-02, before any prereg or arm)

Procedure facts read from the files and cards; no outcome data. They constrain the prereg.

## The two builds (matched at about 250 GB)

| | ISTA-DASLab GSQ-RCO IQ2_XXS | Unsloth UD-IQ1_M |
|---|---|---|
| revision | `65d53bc8` (10-28) | `2688c0c3` (11-02) |
| backbone | 138.24 GB, shards 1-5 | 139.80 GB, shards 1-4 |
| Engram / PLE tables | 110,595,290,816 B, separate file linked as shard 6 | 110,595,290,592 B, shard 5 (224 B smaller) |
| total | 248.84 GB | 250.40 GB |
| tensors | 1,043 | 1,043 |
| `general.file_type` | 19 | 7 |
| imatrix | 585 entries, 1,000 chunks | 592 entries, 558 chunks (`unsloth_calibration_...`) |
| sampling metadata | none | `temp 1.0`, `top_p 1.0` |
| chat template | 18,401 chars, adapted from Unsloth's | 17,564 chars |
| date variables in template | none | none |

Arch `deepseek41`: 40 blocks, 384 experts, 6 used + 1 shared, PLE ("Engram") on layers 1 and 14, size label 748B-A16B.
Download: `download_ds41.sh` (sha256 per file). Engine: upstream b12063 (`build_b12063_sm60.sh`); DSV4.1 support merged in
ggml-org/llama.cpp #31086 (10-26); ISTA needs b11870+; Unsloth's own PR #30817 was closed 10-27.

## Constraints for the prereg

1. **One template for both arms.** The embedded templates differ, so a run with each file's own template confounds the
   quant with the prompt. Serve both with the same `--chat-template-file` and record `prompt_sha` per row; the arms'
   prompt hashes must be equal item by item.
2. **Every sampler explicit in every request** (temperature, top_p, top_k, min_p): the Unsloth file carries sampling
   defaults and the ISTA file carries none, and llama.cpp falls back to the file's values.
3. **Is the Engram the same?** Sizes differ by 224 bytes and the metadata layouts differ (`engram.token_map` vs
   `engram.compressed_vocab_size`). Hash the PLE tensor data in both before claiming the backbone is the only difference.
4. **Same node, same device scheme, server restarted per arm** (all four P100s on .194; never split arms across
   partition schemes). Set the AllReduce variable explicitly (NCCL aborts on .194).
5. **PLE first-touch faults.** The Engram tables stay mmapped on the SATA SSD and are read one row per token; speed on
   unseen text is lower than on repeated prompts (Flash-Next precedent). Speed numbers need fresh text and a cold/warm note.
6. **Reasoning:** the M1 instrument runs thinking off; ISTA's card numbers are at reasoning effort 50, thinking on.
7. **Prior art** (`ledger_precheck.py`): Flash-Next GSQ-RCO vs UD on M1 (`quant-abstention/RESULT_FLASHNEXT.md`), DS4-Flash
   IQ1_S on BFCL (`bfcl/DS4_FLASH_IQ1S_W3_MATCHED.md`, ~5 t/s warm on .194 when it had 64 GB RAM). New here: V4.1 with
   Engram, and two packagers' builds matched to 1 % in backbone bytes.
8. **Budget:** at ~5 t/s, M1 (240 short answers) is a few hours per arm; AbstentionBench sub1000 is roughly a day per arm.
   Measure speed in a smoke test before fixing the instrument list.

## Checks and smoke tests, 2026-11-03 (procedure only)

- **Downloads:** all 13 files match their published sha256 (`download.log` on .194: ALL OK, 01:04).
- **Engram identical:** both files hold one tensor, `per_layer_token_embd.weight`, IQ4_NL, [256, 768022850],
  110,595,290,400 bytes; sha256 of the tensor data `36ee7d378c25f61a...` in both. The 224-byte gap is the header.
- **Backbone bytes:** routed experts 132.07 GB (GSQ) vs 132.21 GB (Unsloth); other layer tensors 5.25 vs 6.34 GB;
  embeddings/output 0.91 vs 1.25 GB. GSQ varies expert bytes per layer (2.97-3.93 GB); Unsloth uses blocks
  (2.65 / 2.94 / 3.79 / 3.65 / 3.93 GB).
- **Tokenizer identical:** tokens, merges, token types, BOS/EOS/padding ids, add_bos/add_eos, model, pre: all equal.
  " UNKNOWN" is not a single token (" Unknown" 33049, " unknown" 13026).
- **Templates:** differ only in reasoning-effort aliases and tool content_blocks; an M1 prompt renders identically
  under both, thinking off and on.
- **Smoke (`smoke_ds41.sh`, b12063, three neutral prompts, greedy, 160 tokens):**
  - first GSQ try (experts of 0-2, 10-12, 20-22, 30-32 on GPU): loaded in 7 min 16 s, then CUDA0 out of memory on the
    first request. Layer 2 moved to the CPU and layer 33 to the GPU.
  - GSQ: loaded in 377 s, GPUs 13.3 / 11.1 / 10.8 / 11.9 GB; decode 1.07, 1.92, 2.13 t/s; prefill 0.3-1.4 t/s on
    ~20-token prompts; answers coherent.
  - Unsloth: loaded in 467 s, GPUs 12.5 / 11.4 / 12.7 / 12.8 GB; decode 1.11, 1.72, 2.42 t/s; answers coherent.
  - Upstream warns that the fused DeepSeek-V4 HC pre step is disabled (layer 11 on CUDA1, the op on CUDA0) and that
    `kernel.numa_balancing` is on. Neither is changed.
