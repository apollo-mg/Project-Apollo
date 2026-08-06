# Achieving \~720x Speedup in KV Checkpointing Across Restarts

## Introduction

I watched 2.49 GB of state restore in 1.23 seconds only to be immediately discarded. In modern LLM serving, the ability to save and restore KV cache state is critical for long-context efficiency, particularly on my testbed (Qwopus3.6-27B Q6\_K hybrid, 2× Tesla P100 layer-split, turbo4 KV quantization). However, a significant bottleneck was identified in llama-server: while the slot save/restore mechanism appeared mechanically sound, it was functionally useless across process restarts. Although the data was persisted, critical checkpoint metadata lived only in volatile process memory, leading to the immediate discarding of restored states upon their first use.

## The Discovery

The issue came to light during high-context benchmarking. Observation showed that 2.49 GB of state could be successfully restored from disk in a mere 1.23 seconds. Despite this rapid restoration, the server would immediately throw away the entire state and initiate a full re-prefill as soon as a new query arrived, negating any benefit of the checkpointing system. In the original discovery run, 2.49 GB restored in 1.23 s and was then thrown away; all headline numbers below are from the controlled verification run.

## The Root Cause

The failure occurs within the mechanism of *llama\_state\_seq\_save\_file*. While the function serialized the raw cache data, it failed to serialize *slot.prompt.checkpoints*. Tip-synthesis at position 100,042 failing to serve rollback target 100,034 teaches the invariant: a checkpoint only serves rollbacks at or after its position. For a proof-of-work piece, this initial failure and the resulting insight are the core credibility engine. Following a cold restart, a BPE-boundary rollback is typically required for the first query; because the checkpoint metadata was missing, the system could find no covering checkpoint (which must strictly precede or be at the rollback target). Finding no valid reference point, the server defaulted to a full re-computation.

## The Solution

The resolution is a targeted 117-line "sidecar" fix. This patch ensures that the necessary checkpoint metadata is persisted alongside the primary state file. The sidecar does not identify BPE boundaries; it provides persisted checkpoints so the rollback has somewhere to land, allowing only the few tail tokens to be reprocessed. By recovering this metadata during the restore phase, the system can correctly identify valid BPE boundaries and serve rollback targets, allowing the LLM to resume from the persisted state without discarding it.

## 

## Key Results

The performance gains on 100K-context resumes are transformative, as detailed in the table below:

| Metric | Performance Data |
| ----- | ----- |
| 100K baseline full prefill | 722.4 s wall / 719,975 ms API (138.9 t/s) |
| Save | 1,777 ms (2.56 GB state \+ 299.3 MB sidecar) |
| Cold restart → restore | 100,043 tokens in 1,592 ms |
| **Headline Gains** | **\~720x delta prefill / \~167x end-to-end resume** |
| Same-build A/B (sidecar hidden) | 720.1 s full re-prefill |

## Conclusion & Nuance

This fix is currently live for the *llama-cpp-turboquant* fork (PR *eaf98e612*). It is important to note that while the underlying bug has been verified on the upstream llama.cpp master branch, it remains unfixed there. On this specific hybrid architecture, the sidecar size remains context-independent: \~149.6 MiB per checkpoint of recurrent state (two checkpoints → 299.3 MB). Pure-SWA payloads remain unmeasured. Additionally, users may observe dual-slot cache drops when using *\--kv-unified*; this behavior was found to be pre-existing and unrelated to the checkpointing patch.  
