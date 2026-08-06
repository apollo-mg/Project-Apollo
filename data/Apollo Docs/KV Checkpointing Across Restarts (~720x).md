# Achieving \~720x Speedup in KV Checkpointing Across Restarts Mark Galyan

## Introduction

In modern LLM serving, the ability to save and restore KV cache state is critical for long-context efficiency. However, a significant bottleneck was identified in llama-server: while the slot save/restore mechanism appeared mechanically sound, it was functionally useless across process restarts. Although the data was persisted, critical checkpoint metadata lived only in volatile process memory, leading to the immediate discarding of restored states upon their first use.

## The Discovery

The issue came to light during high-context benchmarking. Observation showed that 2.49 GB of state could be successfully restored from disk in a mere 1.23 seconds. Despite this rapid restoration, the server would immediately throw away the entire state and initiate a full re-prefill as soon as a new query arrived, negating any benefit of the checkpointing system.

## The Root Cause

The failure occurs within the mechanism of *llama\_state\_seq\_save\_file*. While the function serialized the raw cache data, it failed to serialize *slot.prompt.checkpoints*. Following a cold restart, a BPE-boundary rollback is typically required for the first query; because the checkpoint metadata was missing, the system could find no covering checkpoint (which must strictly precede the rollback target). Finding no valid reference point, the server defaulted to a full re-computation.

## The Solution

The resolution is a targeted 117-line "sidecar" fix. This patch ensures that the necessary checkpoint metadata is persisted alongside the primary state file. By recovering this metadata during the restore phase, the system can correctly identify valid BPE boundaries and serve rollback targets, allowing the LLM to resume from the persisted state without discarding it.

## 

## Key Results

The performance gains on 100K-context resumes are transformative, as detailed in the table below:

| Metric | Performance Data |
| ----- | ----- |
| 100K baseline full prefill | 722.4 s wall / 719,975 ms API (138.9 t/s) |
| Save | 1,777 ms (2.56 GB state \+ 299.3 MB sidecar) |
| Cold restart → restore | 100,043 tokens in 1,592 ms |
| **Headline Gains** | **\~720x delta prefill / \~167x end-to-end resume** |

## Conclusion & Nuance

This fix is currently live for the *llama-cpp-turboquant* fork (PR *eaf98e612*). It is important to note that while the underlying bug has been verified on the upstream llama.cpp master branch, it remains unfixed there. On this specific hybrid architecture, the sidecar size remains context-independent (\~149.6 MiB per recurrent state). Additionally, users may observe dual-slot cache drops when using *\--kv-unified*; this behavior was found to be pre-existing and unrelated to the checkpointing patch.

\#\# Writeup 2 — KV Checkpointing Across Restarts (\~720x) — publish FIRST (PR is live, Discord thread warm)

\*\*Thesis:\*\* llama-server's slot save/restore was mechanically perfect but functionally useless across restarts — the restored state was discarded on first use because checkpoint \*metadata\* lives only in process memory. A 117-line sidecar fix recovers a \~720x speedup on 100K-context resume.

\*\*Verified numbers (all receipts in \`scripts/experiments/\` unless noted):\*\*  
| Fact | Number | Receipt |  
|---|---|---|  
| 100K baseline full prefill | 722.4 s wall / 719,975 ms API (138.9 t/s) | \`save\_receipt\_tom\_100k\_100000.json\`, \`slot\_benchmark\_tom\_100k\_100000.log\` |  
| Save | 1,777 ms → 2.56 GB state \+ 299.3 MB sidecar | same |  
| Cold restart → restore | n\_restored \= 100,043 in 1,592 ms | \`restore\_receipt\_tom\_100k\_100000.json\` |  
| Delta query after restore | 1,000 ms API / 2.72 s wall; 95%-depth canary recalled | same |  
| Headline | \*\*\~720x delta prefill; \~167x end-to-end resume\*\* | derived from above |  
| Same-build A/B (sidecar hidden) | 720.1 s full re-prefill, correct answer, no crash | \`restore\_receipt\_fallback\_nosidecar\_100000.json\`, \`slot\_benchmark\_fallback\_nosidecar.log\` |  
| 1K acceptance | 807 ms vs 7,704 ms | size-stamped 1K receipts |  
| Live regression (all legs) | PASSED, zero invalidation warnings on patched paths | \`live\_multiturn\_regression\_tom\_1k.log\` |  
| Server log (100K restore leg) | preserved | \`.194:/home/mark/slots/server\_log\_100k\_restore\_leg.log\` |

\*\*Narrative beats:\*\* discovery (2.49 GB restores in 1.23 s then gets thrown away) → mechanism (\`llama\_state\_seq\_save\_file\` doesn't serialize \`slot.prompt.checkpoints\`; post-restore BPE-boundary rollback finds no covering checkpoint) → \*\*v1 failure is the best teaching moment\*\* (tip-synthesis at pos 100,042 can't serve rollback target 100,034 — checkpoint must \*precede\* the target) → sidecar fix → same-build A/B proves the sidecar is the entire effect → PR \`eaf98e612\` (+117 lines) live on llama-cpp-turboquant.

\*\*Overclaim guards:\*\*  
\- This is a \*\*fork PR\*\* (TheTom's llama-cpp-turboquant), not upstream llama.cpp. The underlying bug \*does\* exist on upstream master (verified on dense \+ SWA), but don't claim upstream is fixed.  
\- Sidecar size is context-independent \*\*on this hybrid arch\*\* (313,788,804 bytes at 1K and 100K \= 2 × \~149.6 MiB recurrent state). Pure-SWA payloads may scale differently — one unmeasured case, say so.  
\- The dual-slot cache drop (\`-np 2 \--kv-unified\`) is \*\*pre-existing\*\* — reproduced byte-for-byte on unpatched buun (\`dualslot\_control\_buun.log\`). Mention only as "found, unrelated, flagged separately."  
\- Per-turn \~250-token reprocess on the chat endpoint is inherent to think-stripping templates, not a patch regression (see Writeup 4).