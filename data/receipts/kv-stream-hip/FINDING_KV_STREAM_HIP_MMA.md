# kv-stream on HIP (RX 9070 XT, gfx1201): builds and enables, matches the baseline while every page is resident, and fails as soon as pages actually stream (the MMA f16 FA kernel has no RDNA4 device code)

**2026-09-26.** TheTom/llama-cpp-turboquant **`a3d5603d1`** (the #357 "Block KV cache streaming" merge), built for
gfx1201 with `-DGGML_HIP=ON -DGGML_CUDA_FA_ALL_QUANTS=ON -DGGML_HIP_GRAPHS=ON` (Release, 5.5 min). Model:
`Qwen3.8-27B-UD-IQ3_XXS`, `-ngl 99 -fa on -ctk q8_0 -ctv turbo3`. Text: WikiText-2 test (sha256 `173c87a5...`).
Logs: `raw/`.

**Prior art checked:** `ledger_precheck.py "KV cache streaming host RAM spill long context arena"`. INDEX L309, the
9070's 262k VBR deployment that clamped at its floor (60 cache resets, 7/61), is the gap this feature targets.
Nothing on kv-stream itself.

## What happened

| run | arena | KV share vs whole KV (16k: 372 MiB) | result |
|---|---:|---|---|
| baseline, `-c 16384 -b 2048 -ub 512` | off | -- | PPL 5.6914 (2 chunks) |
| `-c 16384 -b 2048 -ub 512` | 512 MiB | -- | **clean refusal at context creation**: "prefill phase does not fit shared CUDA arena: KV space cannot hold one resident page per layer" |
| `-c 16384 -b 2048 -ub 512` | 2048 MiB | exceeds the whole KV | runs; **KLD vs baseline 0.000000**, top-1 100 %. Nothing needed to stream |
| `-c 16384 -b 512 -ub 256` | 640 MiB | prefill KV 387.5 MiB, **exceeds** the whole KV | "experimental block KV streaming enabled"; runs; PPL 3.6479, identical to its baseline |
| `-c 16384 -b 512 -ub 256` | **448 MiB** | prefill KV **195.5 MiB, about half the KV** (33 resident pages/layer + 10 ring) | **fails**: 25x `fattn-mma-f16.cuh:2126: ERROR: HIP kernel flash_attn_ext_f16 has no device code compatible with HIP arch 1300.` No result |

**Reading:**
- On HIP the feature parses, allocates its arena, and computes correctly while every page stays resident.
- The first time attention must consume streamed pages, it dispatches the MMA f16 flash-attention kernel,
  `flash_attn_ext_f16`, which is not compiled for RDNA4. Non-streamed attention on HIP uses other kernels, which is
  why every non-streaming run works.
- So streaming, the feature's actual purpose, does not work on gfx1201 at this commit.

## Also found (tooling, not kv-stream)

`llama-perplexity` at `-c 32768` was **OOM-killed** (20.8 GB RSS on a 32 GB machine). It holds all logits of a
chunk, about 32 GB for a 248k vocabulary at 32k. Long-context correctness checks of a 248k-vocab model need either a
bigger host or a tool that scores positions without keeping every logit.

## Next

- Report upstream (draft for Mark).
- Re-test when the streamed path gets a HIP kernel route (the vec or tile FA kernels that non-streamed attention
  already uses), or when #391's PR lands.
- The planned VBR-vs-kv-stream head-to-head on the 9070 waits on that.
