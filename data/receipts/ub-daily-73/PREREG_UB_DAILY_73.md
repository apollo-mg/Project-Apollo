# Pre-registration -- physical batch size (`-ub`) on the .73 daily driver: VRAM cost and prefill gain

**2026-10-08, before any run.** `kmic-p100-73/RESULT_KMIC_VS_DAILY_73.md` found that the daily command sets no `-ub`,
so it serves at buun's default of 512 (`common/common.h:590` at `510cbbbfa`). The same build prefilled 219.5 t/s at
`-ub 2048` in that test's matched micro (f16 KV, no MTP, `-c 8192`), against 176.8 served at 2k. Mark: "Let's test
the microbatching on buun's fork and see how much more VRAM that uses."

**Why VRAM is the question.** With `-fit off` under `-sm tensor`, buun derives the auto VBR KV budget from live free
device memory and re-derives it at each boundary. The floor is the floor-layout cost of the full context
(`src/llama-kv-cache.cpp` ~1853-1906 and `vbr_pool_reach` ~4362, at `510cbbbfa`). A larger compute buffer therefore
does not just take VRAM: it shrinks the KV budget, so VBR may drop to lower bits/value at a shallower depth. That
costs quality, not speed.

**Prior art checked:** `ledger_precheck.py "ubatch ub 2048 compute buffer VRAM VBR budget prefill"` -> receipts found:
- `qwen4exp/split-conc/RESULT_RECIPE.md` (10-02): Flash-Next on 4x P100 with tensor split + MTP **failed to load** at
  `-ub` 1024/2048/4096. The drafter's compute buffer lands on GPU 0 and grows with ubatch (~1 GB at 1024).
- `viability/RESULT_MTP_VRAM_COST.md` (09-08): MTP costs 1.2-2.1 GB and up to 41 % of the KV budget.
- `kv-tensor-split/NOTE_FA_F16_POOL_RATCHET_PASCAL.md` (09-11): every Pascal prefill takes the TILE kernel and
  materializes K/V to f16. That scratch scales with context, not ubatch.

**What this adds:** a different model (dense 27B, not an MoE), two cards and the VBR auto budget. Here the cost can
show up as a smaller KV budget and earlier degrades, not only as a load failure. Also the first `-ub` curve for the
daily command, measured against this morning's D1/D2 legs as a same-day replication.

## Arms (one binary, one command; only `-ub` changes)

- **Binary:** buun `510cbbbfa` + `f08683ffa` (local `ccb273321`), `/mnt/HDD/buun-510cb-nohost/build_sm60`. This is the
  daily driver.
- **Command:** the wake proxy's `WP_START_CMD` minus `--resume*`, byte-identical to kmic-p100-73's D1/D2 legs:
  - `-c 262144 -ctk vbr -ctv vbr --vbr-floor t4 --vbr-vram auto -np 2 --kv-unified -fit off -sm tensor -fa on`;
  - `--spec-type draft-mtp --draft-max 3`, mmproj F16, model-card sampling.
- **Cells, in order:**
  - **U512:** the command unchanged (default `-ub 512`, `-b 2048`);
  - **U2048:** plus `-ub 2048`;
  - **U1024:** plus `-ub 1024`.
- `-b` stays at its default of 2048 in every cell. A fresh server for each cell.

## Instrument

- **Node:** .73, both GPUs, 150 W / 1,328 MHz recorded before each leg. The wake proxy is stopped for the duration and
  a busy lock (`/tmp/apollo-busy.ubtest`) holds .73 awake. `run_wrap.sh` restores the proxy on any exit.
- **Requests per cell** (`ubbench.py`): kmic-p100-73's D1 schedule.
  - 2k `[212992:215040]` and 32k `[131072:163840]`, seeds 1 and 2 each; 128k `[0:131072]`, seed 1.
  - `/completion`, raw token ids, `cache_prompt: false`, `ignore_eos`, `n_predict 512`.
  - Temperature 1.0 / top-k 20 / top-p 0.95 / min-p 0.
  - One discarded warmup first.
- **VRAM:**
  - per-GPU `memory.used` from nvidia-smi at three points: after `/health` is ok (before any request), after the
    warmup, and after every completion;
  - a 2 s log of `memory.used`, power and clocks during the leg.
  - **The primary VRAM figure** is the post-load snapshot (sum of both GPUs, and the tighter GPU separately):
    U2048 minus U512, and U1024 minus U512.
- **Speed:** `timings.prompt_per_second` (prefill) and `timings.predicted_per_second` (decode), averaged per cell and
  depth over seeds.
- **KV precision:** `timings.kv_bpv` per completion, plus any "VBR budget ... exceeded" warning in the server log.

## Validity checks (a failed check voids the affected rows; it is reported, not patched)

- **V1 replication:** U512's five completions are byte-identical to D1's from `kmic-p100-73` (same command and binary;
  D1 and D2 were byte-identical to each other). This proves the control is the daily config and nothing drifted.
- **V2 no collapse:** every completion has a longest single-character run < 64 and > 20 distinct characters.
- **V3 clocks:** 150 W and 1,328 MHz application clocks on both GPUs before each leg.
- **V4 survived:** the server is alive at the end, with no abort / `GGML_ASSERT` / out-of-memory line in its log.

## Predictions

| # | claim | confidence |
|---|---|---|
| P1 | All three cells load at `-c 262144` and complete the 128k request | 0.65 |
| P2 | Post-load VRAM, summed over both GPUs: U2048 uses between 1.0 and 5.0 GiB more than U512 | 0.6 |
| P3 | Prefill at 2k and at 32k: U2048 >= 1.15x U512 (both depths must hold) | 0.65 |
| P4 | Prefill at 128k: U2048 >= 1.10x U512 | 0.55 |
| P5 | Mean `kv_bpv` at 32k: U2048 <= U512 (the smaller budget degrades no later) | 0.5 |
| P6 | Mean decode over the four 2k/32k completions: U2048 within +/-5 % of U512 | 0.6 |

P6 is loose because a different ubatch can change prefill numerics. Then the seeded text, and with it MTP acceptance,
can diverge. Acceptance and text agreement against U512 are reported per completion.

## Not tested

- Quality beyond `kv_bpv` (no KLD). A lower `kv_bpv` at depth is the quality cost of the trade.
- `-b` above 2048, `-ub 4096`, the MTP drafter's own ubatch, and concurrent requests on both slots.
- Any change to `WP_START_CMD`. Adopting `-ub N` is Mark's decision after the result. If adopted, it needs the usual
  cold-start verification of the wake proxy.

## Deviations

Any change after the first row gets a numbered Deviation here before the affected rows run.
