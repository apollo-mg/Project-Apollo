# Ladder operational state -- resume point

**Written 2026-09-19 before a context compaction.** Everything needed to resume without
re-deriving. Prereg: `PREREG_CODEC_LADDER.md` (6 predictions, committed before any cell ran).

## Where things are

**Node: `.73`** (dual P100, 32 GB VRAM, 15 GB RAM). Wake via the proxy at `127.0.0.1:8099` on the
desktop -- POST `/wake`, then poll; sshd serves ~84 s after. **Ping and an open port 22 do NOT
mean it is awake** (the NIC answers in S3); trust `curl 127.0.0.1:8099/status` -> `"state"`.

| item | path on `.73` | identity |
|---|---|---|
| reference | `/mnt/HDD/kld/ref.kld` | 5,065,891,540 B, the ORIGINAL from the EXL3 campaign |
| corpus | `/mnt/HDD/exl3/wiki.test.raw` | sha256 `173c87a53759e020...` |
| binary | `~/buun-sm60-qual/build_sm60qual/bin/llama-perplexity` | buun `9ae8f0f4` + e8m0 guard; **the build that wrote ref.kld**; verified running |
| gate model | `/mnt/HDD/ladder/Qwen3.8-27B-Q8_0.gguf` | 29.05 GB, transferred |
| G-IQ2XS | `/mnt/HDD/ladder/Qwen3.8-27B-GSQ-RCO-IQ2_XS-mtp.gguf` | 8.77 GB, **hash-verified** `f3369f8d...` |

**`/mnt/HDD` is a DIFFERENT filesystem per node** -- local ext4 on `.73`, CIFS NAS on the desktop.
See [[mnt-hdd-is-per-node]]. 46 GB free on `.73` right now.

## Frozen invocation (from `exl3_kld_arm.py`, do not vary)

```
$BIN -m <model> -f /mnt/HDD/exl3/wiki.test.raw \
  -ngl 99 -sm layer -c 512 -b 512 -ub 8 --chunks 40 -fa on -ctk f16 -ctv f16 \
  --kl-divergence-base /mnt/HDD/kld/ref.kld --kl-divergence
```

Parse with: `Mean KLD:\s+NUM`, `Median\s+KLD:\s+NUM`, `99\.0%\s+KLD:\s+NUM`, same-top %.
**`llama-perplexity` exits 0 on failure** -- verify parsed output, never the return code.

## Progress as of 2026-09-19 11:52

1. ~~Run P-L0 gate~~ **DONE, PASS** -- mean KLD `0.000000 +/- 0.000000`, same-top `100.000%` on
   all 40 chunks. `RESULT_PL0_GATE.md`. The measured floor is below 1e-6, which makes P-L5's
   1e-4 threshold a real discriminator rather than noise.
2. ~~Delete the Q8_0~~ **DONE** (73 GB free at the time; 31 GB now that the panel has landed).
3. ~~Transfer the four remaining models~~ **DONE**, every one hash-verified on BOTH ends.
4. **Five stock cells RUNNING**, serial, ~16 min each, started 11:36. G-IQ2XS done:
   mean KLD `0.202243`, same-top `81.471%`. Results append to `~/ladder/cells/results.jsonl`
   on `.73`, one line per cell, fsynced before the next starts.
5. Bonsai cells: **both models now on the desktop and hash-verified** -- B-PTQ1
   `53107f530aa52eb0...`, B-PQ2 `3907dc1658db1f78...` (matches the hash the prereg recorded in
   advance). Still to do: transfer them to `.73`, build the fork, run `C-XBIN` then the two cells.

## Remaining, in order

1. Wait for the stock batch (`BATCH_DONE` in `~/ladder/cells/batch.log`; ETA ~12:56).
2. Transfer B-PTQ1 + B-PQ2 to `/mnt/HDD/ladder/` (13.2 GB, 31 GB free).
3. `scripts/build_prism.sh` on `.73`. **Host compiler is pinned to gcc-13 on purpose**: CUDA
   12.4's `host_config.h:143` hard-errors above gcc 13 and this box defaults to gcc 15.2.
   The local `engines/prism_llama_cpp` checkout is useless here -- `GGML_TYPE_COUNT = 42`, it
   cannot represent types 142/143. `origin/prism` is ~2520 commits ahead and has them.
4. `scripts/run_prism_cells.sh` -- runs **C-XBIN first** and skips the Bonsai cells entirely if
   it yields no KLD block, so a `.kld` format incompatibility cannot be misread as a Bonsai
   defect.
5. Score everything: `tools/score_ladder.py <results.jsonl...> --floor <measured P-L0 mean>`.

## Operational state, must not be forgotten

- **The wake proxy is STOPPED** (`systemctl --user stop apollo-wake-proxy`, approved by Mark for
  the duration of the batch) and the keepalive loop is killed. With the proxy down, `.73` cannot
  suspend and cannot serve. **Restart it when the ladder is done** -- it restores the daily
  driver itself via `WP_START_CMD`.
- Earlier in this session I wrongly concluded the proxy could not restart llama-server, from
  reading only the first 20 lines of its unit. `WP_START_CMD` is set on line 28. The proxy
  restarted the driver automatically 2 s after the gate released VRAM.

## Open loops elsewhere (found by grep, 2026-08-05 .. 2026-09-09)

14 receipts state a next step that never happened. Highest-value:
`battle16gb/PARTIAL_HA20_GSQ_INCOMPLETE.md` (5 of 40 scenarios, arm 2 never ran, and its resume
script died with the scratchpad), `kv-fidelity/RESULT_U5CD_PLACEMENT.md`,
`rdna4-moe-cache/RESULT_HIP_VULKAN.md`. A `tools/ledger_open_loops.py` to surface these from
`ledger_health.sh` is agreed but unbuilt.
