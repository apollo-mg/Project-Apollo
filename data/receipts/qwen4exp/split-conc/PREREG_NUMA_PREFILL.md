# Pre-registration: split-conc round 2 -- is the layer-split 2-stream "bistability" NUMA placement (AFM-28), and how do split mode and ubatch set Flash-Next prefill on 4x P100?

**Registered 2026-10-02, before any row.** Mark: "Yeah let's see about both of those." Follows `RESULT_SPLIT_CONC.md`
(10-01), where layer split at 2 streams measured 30.3 tok/s total in pass 1 and 18.7 in pass 2 of the same server, and
prefill was not captured.

**Prior art checked:** `ledger_precheck.py "prefill ubatch tensor split layer split Flash-Next prompt processing"` ->
receipts found:
- **FAILURE_MODES AFM-28 (08-28):** unbound 4-GPU runs on .194 are bistable (tg128 12.80 / 12.56 / 15.83 / 15.75).
  - The 4 GPUs span both sockets (GPU0-1 on node 0, GPU2-3 on node 1, `SYS` between them).
  - `--interleave=all` (15.35, 14.68) and `--cpunodebind=0 --membind=0` (15.88, 15.21) were stable.
  - The rule it set: multi-GPU numbers on .194 are `numactl`-bound and repeated >= 3 times.
  - **None of this week's .194 runs were bound** (split-conc, coder-prune, HC_Q8, mmvf B5). That is the
    hypothesis under test.
- **`.73` 27B prefill by split** (INDEX L123): a dense model on 2 GPUs, one socket.
- **The 09-28 MTP clock study:** Flash-Next 6k cold prefill 123-128 tok/s (layer split, default ubatch, unbound,
  1063 MHz).
- **What this adds:**
  - AFM-28 tested on decode streams *within* one server (the 10-01 flip was within a server, not across starts);
  - Flash-Next prefill by split mode and ubatch, measured for the first time;
  - Jabba's DeepSeek result (chunk width 1.54x at 8k, fading with context) as an outside reference.

## Common setup

- **Hardware:** .194, 4x P100, 150 W / 1063 MHz (read back).
- **Model and binary:**
  - buun `0b2789f23` (`~/buun-0b278`, the binary of 10-01's run).
  - Flash-Next UD-Q2_K_XL fully resident (`-ngl 99`, 49/49 checked), f16 KV, `-fa on -fit off -lv 4`.
  - `GGML_CUDA_ALLREDUCE=internal`.
- **Page-cache placement held constant:**
  - Once, before any arm: drop caches, then read shards 2 and 3 (79 GB, which includes the 28.8 GB per-layer
    embedding table) under `numactl --interleave=all`.
  - `numastat -m` FilePages per node is recorded before and after.
  - Arms then vary only thread and allocation binding.
- **Binding prefixes:**
  - **U:** none;
  - **C0:** `numactl --cpunodebind=0 --preferred=0`;
  - **C1:** `numactl --cpunodebind=1 --preferred=1`.
  - `--preferred`, not `--membind`, so a full node falls back instead of reclaiming the interleaved file pages.
- **Per server:** `numastat -p` after load, and a 0.5 s sampler of the CPU (`psr`) of the server's running threads
  for every probe.

## Part N -- the 2-stream bistability

- **Config:** 10-01's L0 cell exactly (`-sm layer -ts 1,1,1,0.6 -c 16384 -np 4`, no MTP).
- **Probe:** `conc_probe.py ... run`, unchanged (1, 2, then 4 parallel 256-token streams per pass, 2 passes). It runs
  twice per server, so 4 passes.
- **Server starts, in this order:** U1, C0a, U2, C1a, U3, C0b, C1b (7 starts).
- **Metric:** the 2-stream `agg_tps` per pass (4 per start).

| # | claim | rule | confidence |
|---|---|---|---|
| N1 | **bound arms are stable** | every 2-stream pass of C0 and of C1 is within +/-5 % of its arm's median (8 passes each) | 0.6 |
| N2 | **unbound reproduces the instability** | over U's 12 passes, max/min of the 2-stream total >= 1.15 | 0.5 |
| N3 | **the socket matters** | C0 and C1 2-stream medians differ by >= 10 % | 0.4 |

**Reported without a prediction:**
- the 1- and 4-stream totals per arm;
- for U, each pass's total against the fraction of running-thread samples on node 0;
- `numastat -p` per server.

## Part P -- prefill by split mode and ubatch

- **Binding:** C0 for every cell (AFM-28's best; fixed now, not chosen from Part N).
- **Config:** `-np 1 -c 16384`.
- **Cells:** split {layer `-ts 1,1,1,0.6`, tensor} x `-ub` {512, 2048, 4096}, with `-b max(2048, ub)`. One fresh
  server per cell (6). An OOM at load is recorded as that cell's result.
- **Probe:** `pf_probe.py`. Exact-length token prompts from wikitext-2 test via `/completion` (a token-id list, no
  template), `n_predict 1`, `cache_prompt false`, after one unrecorded 64-token warm-up request. 2,048 and 8,192 tokens, 3 reps each, each rep at a different text
  offset.
- **Metric:** median `prompt_per_second` over the 3 reps. The "pipeline parallelism enabled" log line is recorded per
  cell.

| # | claim | rule | confidence |
|---|---|---|---|
| P1 | **tensor split wins prefill** at the default ubatch | ub=512, 8k: tensor > layer | 0.5 |
| P2 | **tensor split gains from a wider ubatch** | tensor, 8k: ub2048 >= 1.15x ub512 | 0.6 |
| P3 | **layer split does not** (ub = b removes its 4-ubatch pipeline) | layer, 8k: ub2048 < 1.15x ub512 | 0.5 |
| P4 | **the best cell beats the 09-28 reference by 30 %** | max over cells at 8k >= 163 tok/s (1.3 x 125) | 0.5 |

**Reported without a prediction:** 2k vs 8k for every cell, ub 4096, and VRAM per GPU.

## Not tested

- Decode under binding for tensor split.
- MTP.
- Contexts above 8k.
- GLM-5.3 (a separate prereg, after this).
- Whether the 10-01 flip had the same cause: this tests whether one exists that matches it.

## Deviations

Any change after the first row gets a numbered Deviation here before the affected rows run.
