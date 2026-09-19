# Result -- RST charter (b), VRAM boundary: there is no refusal to name, by design

**2026-09-18.** Charter (b) of S4 in Avarok-Cybersecurity/atlas#1126, on the RX 9070 XT (16 GB,
desktop co-resident), Ornith-1.0-9B-NVFP4, SCALE 1.7.1.

Charter text: *"one flag at a time: seq 2048, 4096, 8192; batch 1, 2, 4; record
`mem_info_vram_used` before and after each."* Gate: *"first refusal named with its exact error;
server always handed back on the last good config."*

## The charter's specified range produces no refusal at all

| config | VRAM before | peak | after | verdict |
|---|---:|---:|---:|---|
| seq 2048, batch 1 | 2.11 | 13.41 | 2.11 | SERVED |
| seq 4096, batch 1 | 2.11 | 14.13 | 2.18 | SERVED |
| seq 8192, batch 1 | 2.18 | 15.51 | 2.18 | SERVED |
| seq 4096, batch 2 | 2.18 | 14.37 | 2.16 | SERVED |
| seq 4096, batch 4 | 2.16 | 14.69 | 2.57 | SERVED |
| recovery: seq 4096, batch 4 | 2.57 | 14.98 | 2.45 | SERVED |

All GB. Every config served and answered a canary correctly; VRAM returned to baseline after each.
The recovery leg is trivially satisfied because nothing ever failed.

Extending past the charter's range to find the boundary:

| requested seq | granted KV tokens | peak VRAM | verdict |
|---:|---:|---:|---|
| 12288 | 12320 | 15.79 | SERVED, full request |
| 16384 | 16416 | 15.75 | SERVED, full request |
| **32768** | **28816** | 15.74 | SERVED, **overcommitted and warned** |

## The finding: Atlas back-pressures, it does not refuse

At seq 32768 the granted pool fell 3952 tokens short of the request, and Atlas said so explicitly:

```
WARN KV OVERCOMMIT: pool fits 0 seq(s) at full --max-seq-len=32768 but --max-batch-size=1
requested (2048 block(s)/seq, 1801 block(s) total). Paged KV allocates on demand;
long-context bursts are back-pressured at the block allocator, not refused at boot.
```

That is the charter's answer, and it is a statement about the charter rather than about the card:
**the gate asks for "first refusal named with its exact error", and this architecture has no
refusal to name.** Paged KV allocates on demand, so an over-large request is admitted at boot with
a named overcommit warning and then back-pressured at the block allocator during use. The failure
mode the charter anticipates does not exist on this path.

The warning itself is close to ideal: it names the shortfall in blocks, states the design choice,
and says where the consequence lands. If the gate were reworded to "first overcommit named with
its exact warning", this run passes it cleanly.

What would still be worth measuring, and is not answered here: what back-pressure actually *does*
to a long-context request at runtime. That is a request-level test, not a startup ladder, and it
belongs with charter (c) or (d) rather than here.

## Why KV shrinks: the buffer arena, not the weights

```
seq  4096: pre-KV 10.19 GB = weights 7.42 + buffer arena 1.36 + other 1.41  -> KV 2.19 GB
seq 32768: pre-KV 11.44 GB = weights 7.42 + buffer arena 2.61 + other 1.41  -> KV 0.90 GB
```

Weights are fixed. The **buffer arena** nearly doubles with sequence length and takes the space
out of the KV pool, so the budget squeezes from both ends at once. On a 32 GB board that is
absorbed; on 16 GB it is what turns an overcommit into a live constraint.

At seq 32768 the OOM watchdog logged **182 MB free** against its 2048 MB threshold -- a single
`[1/3]` reading, so no termination, but that is the closest this card has come to the edge.

## Two corrections to my own earlier receipts

**1. `RESULT_S3_SERVE.md` claimed the board "fits by 32 tokens" at seq 4096.** Wrong. The `+32` is
block padding that scales with the request (2048 -> 2080, 8192 -> 8224); it is not headroom and
4128 was never a ceiling. Corrected in place with the original left visible.

**2. My first reading of the 32768 result was "silent clamp".** Also wrong -- the `KV OVERCOMMIT`
warning above is explicit and detailed. The clamp is announced, not silent. I found this only
because I went looking for a warning rather than assuming its absence, which is the only reason
this receipt does not contain a false accusation of silent data loss.

Both errors ran the same direction: reading a number without reading the configuration that
produced it. The PRD's own instruction covers it exactly -- *"a number without its configuration
is not a result."*

## Instrument defect

The first charter run set `RUST_LOG=warn`, which suppressed the INFO-level KV budget lines --
the single most informative output of the whole exercise. The ladder completed and reported six
SERVED verdicts while discarding the data that explains them. Re-run at `info`. Any future charter
run should pin `RUST_LOG=info` as part of the method rather than leaving it to the invocation.

## Open question for TheTom

At shutdown, seq 32768 logged:

```
WARN sweep: 301 allocation(s) totalling 2.36 GB had no owner; largest sites:
     crates/spark-model/src/weight_map/loaders_fp8.rs:229 (1252.5 MB ...)
```

This appears immediately after `Shutdown requested (SIGTERM)`, so it may be ordinary teardown
accounting rather than a leak. Raising it as a question rather than a finding: is an unowned
sweep of that size expected at shutdown, or does it indicate allocations escaping the ledger?
It did not appear at the smaller sequence lengths.

## Verdict against the charter

- **Range as written: no refusal reachable.** Passes vacuously; the specified matrix is well
  inside this board's capability.
- **Extended range: boundary found and named**, as an overcommit warning rather than a refusal.
- **Recovery: satisfied**, though untested in spirit since nothing failed.
- **Recommendation:** reword the gate to admit a back-pressure architecture, and raise the
  charter's seq ladder to reach 32768 where the interesting behaviour actually lives.
