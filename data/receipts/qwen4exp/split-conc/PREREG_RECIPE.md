# Pre-registration: do today's Flash-Next wins stack in one server? (tensor split + MTP + `-ub 4096` + `--kv-unified`)

**Registered 2026-10-02, before any row.** Mark: "Sure let's knock em out."

**Prior art checked:** `ledger_precheck.py "tensor split MTP ubatch kv-unified combined serving recipe Flash-Next"` ->
receipts found, each measured in a separate config:
- `RESULT_SPLIT_CONC.md` (10-01): tensor + MTP 27.4 tok/s single stream (`-ts 1,1,1,0.75`, ub 512); tensor no MTP
  48.8 total at 4 streams; tensor + MTP at 4 streams = HTTP 500;
- `RESULT_NUMA_PREFILL.md` (10-02): tensor prefill 430 tok/s at 8k with ub 4096; `--kv-unified` removes the
  slot-adjacency penalty (layer split);
- INDEX L36 (09-20): buun fixed tensor split's prompt-cache bug, so 10-01's "tensor split disables prompt-cache
  reuse" caveat may be stale. That is not re-tested here.

**What this adds:** whether the configs combine (VRAM, interactions), and `--kv-unified` under tensor split.

## Servers

Both use: .194, buun `0b2789f23`, Flash-Next UD-Q2_K_XL fully resident, f16 KV, `-c 16384 -fa on -fit off -lv 4`,
`-ub 4096 -b 4096 --kv-unified`, binding C0 (`numactl --cpunodebind=0 --preferred=0`), file pages interleaved
once.

| server | for | config |
|---|---|---|
| **R1** | one or two users | `-sm tensor -ts 1,1,1,0.75` + MTP (shared Q8_0 head, draft 3), `-np 2` |
| **R2** | several users | `-sm tensor`, no MTP, `-np 4` |

- **Probes, per server:** G0 gate, `pf_probe.py` (2k and 8k, 3 reps), then `conc_probe.py run` twice (1/2/4 streams,
  4 passes).
- **R1 at 4 streams:** with `-np 2`, two requests queue. The total is reported, not scored.
- **An OOM at load or an HTTP 500 is the server's result.**

| # | claim | rule | confidence |
|---|---|---|---|
| Q1 | **R1 fits and keeps most of the prefill** | R1 loads; 8k prefill median >= 365 tok/s (0.85 x 430) | 0.5 |
| Q2 | **R1 keeps MTP's single-stream decode** | 1-stream median >= 25 tok/s (T3: 27.4) | 0.6 |
| Q3 | **R2 keeps multi-stream throughput** | 4-stream median total >= 46 (T0: 48.8); 2-stream per-stream >= 13 (T0: 14.5) | 0.6 |
| Q4 | **no slot bistability with `--kv-unified`** | in R1 and R2, every 2-stream pass >= 0.9 x that server's median | 0.7 |

**Not tested:** prompt-cache reuse, contexts beyond 8k, layer split.

## Deviations

Any change after the first row gets a numbered Deviation here before the affected rows run.
