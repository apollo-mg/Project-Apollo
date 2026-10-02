# Pre-registration: is GLM-5.3-Flash's 4.4 tok/s on .194 a NUMA placement problem? (CPU-resident experts, mainline)

**Registered 2026-10-02, before any row.** Mark: "Yeah let's see about both of those." `NOTE_MAINLINE_BASELINE.md`
(09-30):
- UD-IQ3_XXS (120.4 GB) with mainline's auto-fit puts ~15 GB per GPU and **the remaining experts (~60 GB) on the
  CPU**;
- decode 4.38-4.48 tok/s with `n_threads = 20`;
- cause not established.

**Prior art checked:** `ledger_precheck.py "NUMA interleave CPU expert offload threads decode GLM"` -> receipts found:
- **`battle16gb/DS4_REBASELINE_NUMA.md` (08-02):** DS4-Flash with `-ncmoe 40` on .194: `--numa distribute` +13.6 %
  warm decode, cold first response ~2x worse.
- **Memory `numa-distribute-is-threads-only` (09-14, source-verified):** `distribute` only pins threads. Nothing in
  ggml binds memory, so expert pages land by first touch (87.8 % on one node measured with Flash-Next `-ncmoe 16`).
  Node-local bandwidth is 22.68 GB/s, cross-socket 7.00. Real placement needs `numactl --interleave=all` with
  `--numa numactl`, verified in `numa_maps`.
- **`qwen4exp/split-conc/RESULT_NUMA_PREFILL.md` (today):** the socket is irrelevant for a fully GPU-resident decode.
  This test is the opposite case, a host-bandwidth-bound one.
- **What this adds:** true memory interleave was never measured against `distribute` on a CPU-expert model; and the
  GLM-5.3 slowness is unexplained.

## Arms

Mainline `~/llama.cpp-upstream/build_sm60` (`81ff93e`), the 09-30 model files, auto-fit, `-c 16384 -np 1
-ctk f16 -ctv f16`, 150 W / 1063 MHz.

| arm | memory | NUMA |
|---|---|---|
| **M** | mmap (09-30's config; reference, no prediction) | none |
| **B1**, **B2** | `--no-mmap` (experts in process memory, placed by first touch at load) | none |
| **D** | `--no-mmap` | `--numa distribute` |
| **I** | `--no-mmap` | `numactl --interleave=all` + `--numa numactl` |

- **Order:** M, B1, D, I, B2 (B2 is the drift check: B1 and B2 within 5 %, else flagged).
- **Before every arm:** drop the page cache (`sync; echo 3 > drop_caches`).
- **Every arm, after load:** record `numastat -p` (process memory per node), `numa_maps` per-node totals, the fit
  placement (VRAM per GPU), and `n_threads`.
- **Probe:** `glm_probe.py`. 3 fixed prompts x 2 passes, 256 tokens, `reasoning_effort` low, temp 0, no prompt cache.
- **Metric:** median `predicted_per_second` over the 3 pass-2 requests. Pass 1 is reported alongside.

## Predictions

| # | claim | rule | confidence |
|---|---|---|---|
| G1 | **interleaving the experts' memory speeds decode** | I >= 1.15x mean(B1, B2) | 0.55 |
| G2 | **without a policy the experts pile onto one node** | B1's process memory >= 70 % on one node (`numastat -p`) | 0.6 |
| G3 | **thread pinning alone helps less** | D >= 1.05x mean(B), and I >= D | 0.45 |

**Reported without a prediction:**
- M vs B (mmap vs process memory);
- pass 1 vs pass 2;
- prompt-processing speed;
- cold first-request time per arm (DS4 found `distribute` doubled it).

## Not tested

- Thread-count sweeps.
- `-ot` placement that puts more experts on the GPUs.
- KV types.
- Contexts beyond the probe.
- buun or EXL3 (N15).

## Deviations

Any change after the first row gets a numbered Deviation here before the affected rows run.
- **Deviation 1 (before any row of B1, D, I, B2; 10-02 15:18).**
  - Mainline `81ff93e` rejects `--no-mmap` ("invalid argument"). Its replacement is `-lm none` ("no special loading
    mode", i.e. read into memory rather than mmap).
  - B1, D, I and B2 use `-lm none` in its place. Nothing else changes. Arm M's 6 rows (mmap) were already complete
    and are unaffected.

