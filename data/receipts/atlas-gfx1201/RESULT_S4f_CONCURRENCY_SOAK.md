# Result -- RST charter (f) concurrency soak: PASS, and batch 8 collapses exactly as atlas#1118 says

**2026-09-18.** Charter (f) of S4 in Avarok-Cybersecurity/atlas#1126. RX 9070 XT (16 GB),
**headless** (`plasmalogin` stopped), Ornith-1.0-9B-NVFP4, SCALE 1.7.1, seq 4096, server
`--max-batch-size 8`.

Charter: *"20 minutes sequential, then 10 minutes at the largest batch that boots."*
Gate: *"0 errors, 0 empty replies, VRAM flat."*

## Gate: PASS on all three

| | |
|---|---|
| total requests | **650** |
| non-200 responses | **0** |
| empty replies (`content_len == 0`) | **0** |
| bad `finish_reason` | **0** |
| **VRAM band across the full 30 min** | **0 MB** |

VRAM free sat at exactly 2399 MB for every one of the 180 samples, in both phases. Not "flat
within tolerance" -- literally unmoving. That is what a paged KV allocator that reserves its pool
up front looks like from the outside, and it is the strongest possible reading of the gate.

## The finding: concurrency makes this board slower, not faster

| phase | requests | median latency | aggregate throughput |
|---|---:|---:|---:|
| sequential (20 min) | 578 | **2.06 s** | **61.71 tok/s** |
| batch 8 (10 min) | 72 | **66.62 s** | **17.26 tok/s** |

Eight concurrent requests deliver **3.6x less aggregate throughput** than one at a time, and
per-request latency rises 32x. If batch 8 merely serialised, each request should land near
8 x 2.06 = 16.5 s. It takes 66.6 s -- **four times worse than naive serialisation**. Concurrency
here is not failing to help; it is actively destructive.

**This is independent confirmation of atlas#1118**, whose title already states it:
*"Batching on 32 GB discrete board (27B batch 1; 9B collapses at batch 8)"*. The same 9B model
collapses at the same batch size on a different board. So the defect is not specific to the
R9700, and a 16 GB part is not the cause.

### A diagnostic detail worth passing on

Power and clocks move the *opposite* way to what a compute-bound explanation predicts:

| | sequential | batch 8 |
|---|---:|---:|
| sclk median | 3219 MHz | **3284 MHz** |
| sclk min | 797 MHz | **3188 MHz** |
| power median | **295 W** | **257 W** |
| junction max | 76 C | 74 C |

The batch phase runs at *higher, steadier clocks* and draws *less power*. A GPU that is clocked up
but pulling 38 W less is not saturated -- it is waiting. Whatever batch 8 is doing, the shader
array is idling through it rather than grinding. That points at scheduling, synchronisation or
memory stalls rather than an arithmetic bottleneck, which should narrow the search in #1118.

(The 797 MHz sclk minimum in the sequential phase is the idle dip between requests, not a throttle
-- median is 3219 MHz.)

## Two instrument defects, both mine, both caught before publication

**1. A bare `wait` wedged the first attempt.** The batch loop used:

```bash
for b in $(seq 1 "$BATCH"); do fire batch "$N" & done
wait
```

`wait` with no arguments waits on *every* background job, including the hwmon sampler, which is a
`while :;` infinite loop. After the first batch of 8 completed it blocked forever. The sequential
phase was unaffected because it does not use `wait`, so the run looked healthy -- 580 rows on disk
-- while the GPU sat at 19 W for two and a half minutes. Mark spotted it from the outside:
"VRAM has residence, but no load on the core anymore." Fixed by collecting the batch PIDs and
waiting only on those.

**2. Thinking was left on, and it looked like a server defect.** The first attempt recorded
**315 empty replies out of 580** -- all HTTP 200, all with valid `finish_reason`. That reads as
charter (f) failing its "0 empty replies" gate.

It was the harness. TheTom's kit scripts send `"chat_template_kwargs": {"enable_thinking": false}`
and default it to off; my requests sent no thinking control, so reasoning was **on**. Measured on
one probe at `max_tokens=128`: 115 tokens went to `reasoning_content`, leaving 48 characters of
content, and many requests emitted none at all. With thinking off the same prompt returns 719
characters and zero reasoning tokens.

**Had this not been checked, the report to TheTom would have been "Atlas returns empty 200s under
sustained load" -- a defect that does not exist.** Recorded in memory as a standing rule.

Consequence for an earlier receipt: **charter (d) also ran with thinking on.** Decode rate is
unaffected (a token is a token), but it is one further axis on which that run's 69.68 tok/s may
not be comparable to #1107's 78-80, since theirs was most likely measured with thinking off.

## S4 complete

| charter | status |
|---|---|
| (a) coherence | **PASS** -- 9 of 10 canaries, the known exception |
| (b) VRAM boundary | **done** -- gate unsatisfiable as written; no refusal exists to name |
| (c) cancel/recovery | **PASS** -- 10 of 10, +1.0% VRAM |
| (d) sustained decode | **PASS** -- +0.17% drift, no throttling, 0 errors |
| (e) REST conformance | **PASS** -- 9 PASS / 1 FAIL, the known #1121 defect |
| (f) concurrency soak | **PASS** -- 0 errors, 0 empty, VRAM band 0 MB |

All six charters run. Five pass outright; (b) cannot pass as written because the architecture
back-pressures instead of refusing, and its gate needs rewording rather than the board needing a
fix.

Data: `logs/charter-f2/requests.tsv` (650 rows), `logs/charter-f2/hwmon.tsv` (180 rows).
Superseded first attempt preserved at `logs/charter-f/`.
