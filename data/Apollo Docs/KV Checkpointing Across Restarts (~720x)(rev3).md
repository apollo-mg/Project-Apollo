# Achieving ~720x Speedup in KV Checkpointing Across Restarts

## Introduction

I watched 2.49 GB of state restore from disk in 1.23 seconds — and then get thrown away. llama-server's slot save/restore promises exactly what long-context work on budget hardware needs: park a session on disk, bring it back later without paying the prefill tax again. And the restore itself works perfectly. But across a process restart, the feature was functionally useless: the first query after restoring discarded the entire rehydrated state and re-prefilled from scratch. The reason turned out to be a single piece of metadata that lived only in process memory.

Testbed: Qwopus3.6-27B Q6_K (hybrid architecture), 2× Tesla P100 layer-split, turbo4 KV quantization.

## The Discovery

During high-context benchmarking, restores looked mechanically perfect — 2.49 GB back in VRAM in 1.23 seconds — yet the next `/completion` request logged `forcing full prompt re-processing due to lack of cache data` and ran a full re-prefill (about 17.5 minutes at 100K context). Save fast, restore fast, throw it all away.

(That discovery run used a slightly different config than the verification runs; all headline numbers below are from the controlled verification run on the patched build.)

## The Root Cause

`llama_state_seq_save_file` serializes the tokens and the physical KV cells — but not `slot.prompt.checkpoints`, the checkpoint metadata list, which exists only in process memory. After a cold restart, the first request always needs a small rollback: re-tokenizing the prompt tail can shift BPE boundaries, and at least one token must be reprocessed to produce logits. The reuse path will only roll back via a *covering checkpoint* — one at or before the rollback target. With the checkpoint list empty, the server finds nothing, gives up, and recomputes everything.

## The Fix That Didn't Work (v1)

The obvious fix: synthesize a checkpoint from the restored state at restore time. It failed, and the failure is instructive. A synthesized checkpoint sits at the *tip* — the final position (100,042 in the 100K run) — while the rollback targets an earlier position (100,034). A checkpoint can only serve rollbacks at or after its own position, so the tip checkpoint is useless for exactly the rollback that always happens. The invariant: you need checkpoints from *before* the tip, and those only exist at save time.

## The Fix That Worked (v2: the sidecar)

117 lines in `tools/server/server-context.cpp`: at `SLOT_SAVE`, persist the checkpoint list to a versioned sidecar file (`<state>.ckpt`); at `SLOT_RESTORE`, reload it. The rollback now lands on a real persisted checkpoint and only the few tail tokens get reprocessed. If the sidecar is missing — say, a state file saved by an older build — the server falls back to v1-style tip synthesis, which still covers exact-append resumes and otherwise degrades gracefully to pre-patch behavior: full re-prefill, correct output, no crash.

## Key Results

| Metric | Performance Data |
| ----- | ----- |
| 100K baseline full prefill | 722.4 s wall / 719,975 ms API (138.9 t/s) |
| Save | 1,777 ms (2.56 GB state + 299.3 MB sidecar) |
| Cold restart → restore | 100,043 tokens in 1,592 ms |
| Delta query after restore | **1,000 ms API / 2.72 s wall** — canary fact at 95% depth recalled |
| Same-build A/B (sidecar hidden) | 720.1 s full re-prefill; correct output, no crash |
| **Headline** | **~720x delta prefill / ~167x end-to-end resume** |

The A/B row is the receipt that matters: identical binary, identical state file, only the sidecar removed — 720.1 seconds without it, 1.0 second with it. The sidecar is the entire effect.

Live regression also passed across the board: live prefix reuse is unchanged (no sidecar files are written unless `action=save` is explicitly called), a restored session held a fully-cached multi-turn conversation with correct recall, and a park-and-resume with a *divergent* continuation was still served from a sidecar checkpoint.

## Conclusion & Nuance

The fix is live as a PR against the *llama-cpp-turboquant* fork (commit `eaf98e612`, +117 lines): [LINK TO PR]. The underlying bug also exists on upstream llama.cpp master — verified on both dense and SWA models — and remains unfixed there.

On this hybrid architecture the sidecar size is context-independent: ~149.6 MiB per checkpoint of recurrent state, two checkpoints → 299.3 MB at both 1K and 100K context. Pure-SWA checkpoint payloads may scale differently and remain unmeasured. Separately: dual-slot cache drops under `-np 2 --kv-unified` on hybrid models turned out to be pre-existing behavior, reproduced on an unpatched build, and are unrelated to this patch.
