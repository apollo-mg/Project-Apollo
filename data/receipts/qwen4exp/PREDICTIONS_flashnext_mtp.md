# Pre-registered — MTP speedup on Flash-Next under heavy MoE offload

Registered **2026-09-02**, before the run. buun `7a918624b` (only fork with shared-sidecar support,
`2d5ef7910`, landed 09-01). `Qwen3.8-Flash-Next-UD-Q2_K_XL` + `mtp-...-shared-Q8_0.gguf`.
Flags identical to today's speed pass: `-c 8192 -ngl 99 -fa on --jinja -np 1 -fit off -ncmoe 44
-sm tensor`, `--draft-max 3`.

Baselines already measured today, same flags, same session: **2 dev = 8.16 tok/s, 4 dev = 5.88**.

## Predictions

| # | claim | confidence |
|---|---|---|
| P1 | MTP speedup on Flash-Next **exceeds** the 27B's 1.72x at 2 devices | **0.70** |
| P2 | MTP speedup at 2 dev is **> 2.0x** | 0.55 |
| P3 | 4 devices remains slower than 2 **even with MTP on** | **0.75** |
| P4 | the sidecar loads and MTP engages at all (draft acceptance > 0) | 0.80 |

## Reasoning

**P1/P2 — why MTP should help *more* here, not less.** Flash-Next runs with 44 of 48 MoE layers on
CPU, so decode is bound by host-memory expert reads, not GPU math. Speculative verification
evaluates k drafted tokens in **one** forward pass; if that pass is dominated by a fixed
expert-fetch cost, verifying 3 tokens costs close to verifying 1. The 27B, by contrast, is fully
GPU-resident where the forward pass scales more with token count — so its 1.72x should be the
*floor*, not the ceiling.

**P3 at 0.75.** MTP raises per-pass work, which is exactly what the 4-device arm was starving for
(−28 % measured today, attributed to QPI-crossing reductions with too little compute to hide them).
So the gap should narrow. But the 27B needed to be *fully resident* before 4 devices won, and
Flash-Next still is not — the experts stay on CPU regardless of device count.

**P4 at 0.80 rather than higher** — `nextn_shared_target_tensors = True` means the sidecar shares
target tensors with the main model, and that path is one day old.

## Falsifier

If MTP gives **less** than 1.72x here, the "fixed expert-fetch cost amortises across drafted
tokens" model is wrong and the bottleneck is something that scales with drafted tokens too.
