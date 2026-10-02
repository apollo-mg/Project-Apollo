# Pre-registration: GLM-5.3-Flash thread-count sweep (CPU experts are compute-bound, not bandwidth-bound)

**Registered 2026-10-02, before any row.** Follows `RESULT_GLM_NUMA.md`:
- memory placement made no difference;
- `--numa distribute` gave +6.7 % (4.68 tok/s at the default 20 threads);
- the CPU side moves ~7 GB/s.

**Prior art checked:** `ledger_precheck.py "thread count sweep CPU expert decode threads"` -> nothing on thread count;
only the GLM baseline and NUMA receipts above. **What this adds:** the thread lever, the cheapest one left.

## Arms

Mainline `81ff93e`, the same files, auto-fit, `-c 16384 -np 1 -ctk f16 -ctv f16`, mmap (default),
`--numa distribute`, `-t N` (batch threads follow).

| | value |
|---|---|
| N, in order | 20, 10, 30, 40, 20 (the repeat is the drift check: within 5 %) |
| CPUs on .194 | 20 cores / 40 threads |
| page cache | not dropped between arms |
| probe | `glm_probe.py` (3 prompts x 2 passes, 256 tokens) |
| metric | median pass-2 `predicted_per_second` |

| # | claim | rule | confidence |
|---|---|---|---|
| T1 | **a better thread count exists** | max(t10, t30, t40) >= 1.10 x mean(t20 runs) | 0.35 |
| T2 | **SMT does not help** | t40 <= 1.02 x mean(t20) | 0.6 |
| T3 | **it scales with cores below 20** | t10 <= 0.90 x mean(t20) | 0.55 |

**Not tested:** `-ot` placement, quant types for the CPU experts, buun.

## Deviations

Any change after the first row gets a numbered Deviation here before the affected rows run.
