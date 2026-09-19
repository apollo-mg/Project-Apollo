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

## Next action, in order

1. **Run P-L0 gate**: the Q8_0 against `ref.kld`. Pass = mean KLD < 1e-4 AND same-top >= 99.9%.
   If it fails, STOP -- nothing else counts and the reference is not reproducible with this binary.
2. Delete `/mnt/HDD/ladder/Qwen3.8-27B-Q8_0.gguf` (frees 29 GB; panel needs 45.4 GB more).
3. Resume transfer: `/tmp/ladder_xfer.sh` is idempotent (rsync skips matching files) and reads
   `/tmp/ladder_manifest.txt`. **Record its PID at launch**; never search the process list for it.
   Remaining: AD-IQ2_XS 9.89, GSQ-IQ3_XXS 10.44, AD-IQ3_XXS 12.08, AD-IQ3_S-IQ3_XXS 12.98 GB.
4. Run the 5 stock-GGUF cells.
5. Bonsai cells (B-PTQ1 `53107f53...` 5.95 GB, B-PQ2 `3907dc16...` 7.21 GB) need the
   `PrismML-Eng/llama.cpp` fork built -- **not started**, and it is the only build work left.

## Open loops elsewhere (found by grep, 2026-08-05 .. 2026-09-09)

14 receipts state a next step that never happened. Highest-value:
`battle16gb/PARTIAL_HA20_GSQ_INCOMPLETE.md` (5 of 40 scenarios, arm 2 never ran, and its resume
script died with the scratchpad), `kv-fidelity/RESULT_U5CD_PLACEMENT.md`,
`rdna4-moe-cache/RESULT_HIP_VULKAN.md`. A `tools/ledger_open_loops.py` to surface these from
`ledger_health.sh` is agreed but unbuilt.
