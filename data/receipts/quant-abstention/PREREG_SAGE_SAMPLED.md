# Pre-registration -- does Sage's drop in "I don't know" survive sampling? Sage-A1.5 vs its base, matched Q6_K, thinking off, Sage's recommended sampling, three samples per item

**Registered 2026-11-11, before any row.** Mark approved the run on 11-11 ("That sounds like a pretty good idea (Sage
sampled)").

**Why.** At matched precision and greedy decoding, Sage refuses invented M1 items 0.19 less often than its base
(`RESULT_SAGE_MATCHED.md`: 0.48 vs 0.67, [-0.28, -0.11]). An independent replication on HF #23 (Jorge Leon, 6-bit MLX,
his own 30 invented items) found Sage holding its base's rate, and his runs used Sage's recommended sampling (T 1.0,
top_p 0.95, top_k 20, min_p 0, presence 1.5). An outside critique on the same thread (SerialKicked) argued that greedy
is not how any model is meant to run. This run changes only the decoding.

**Prior art checked:** `ledger_precheck.py "Sage sampled greedy temperature abstention matched"` -> INDEX L593 (the
matched greedy result) and L572; plus `sci-distill/RESULT_SCI_DISTILL.md` P11: on Qwen3.5-9B with thinking off, greedy
vs this same sampling moved invented-item refusal by +0.03 [-0.05, +0.11]. **What this adds:** the same check on the
pair in dispute, with three samples per item instead of one.

## Arms

| arm | file | decoding |
|---|---|---|
| Q36BS1, Q36BS2, Q36BS3 | Qwen3.6-35B-A3B Q6_K, sha256 `0e0e2c37...` (the stored Q36B and Q36B2 file) | sampled, seed base 20261111 + r |
| SGQ6S1, SGQ6S2, SGQ6S3 | Sage-A1.5 Q6_K (mradermacher, sha256 `852dffdd...`, the stored SGQ6 file) | the same, the same seeds |

Sampling: `{"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.5}`, per-item seed
`(seed_base + crc32(id)) mod 2^31` (`run_main.py --sampling --seed-base`), so replicate r of both models uses the same
seed per item. Everything else is a procedural copy of `run_sage_matched.sh`: llama.cpp `c7fc509` build_sm60 via
`~/bench/sage/serve_sage.sh` (4x P100 layer split, F16 KV, `-c 16384 -np 1`), weights from `/dev/shm` one model at a
time, thinking off, no system message, 1,024 tokens, R-slot on (greedy, unchanged), the stored Q36B render tail and
UNKNOWN ids enforced, token prompt gate equal on both models. Base first (three replicates on one server load), then
Sage. Chain: `run_sage_sampled.sh`.

## Analysis (`analyze_k.py`, committed and self-tested before this file)

Per item, each metric is the mean over the three replicates; paired by item, bootstrap 10,000 over items (seed
20261111). Primary: invented refused, bare "UNKNOWN" counted (`U_refused_lenient`), Sage - base. Secondary: each model's
sampled mean against its own greedy arm (SGQ6, Q36B2). Reported: hard accuracy, made-up answers, unfinished.

## Predictions

| # | claim | rule | confidence |
|---|---|---|---|
| P1 | **Sage's drop survives sampling** | U refused (lenient) SGQ6S - Q36BS <= -0.10, CI upper < 0 | 0.75 |
| P2 | **Sampling barely moves the base** | \|U refused (lenient) Q36BS - Q36B2\| <= 0.05 | 0.6 |
| P3 | **Sampling barely moves Sage** | \|U refused (lenient) SGQ6S - SGQ6\| <= 0.05 | 0.6 |

If P1 fails with the CI including 0, the greedy result is decoding-specific and Leon's disagreement is explained by
sampling; `RESULT_SAGE_MATCHED.md` and the Arete table get that caveat. If P1 holds, the disagreement lies in the items
or the stack, not the decoding.

## Deviations

Any change to a file, flag, arm or the analysis after the first row gets a numbered Deviation here.
