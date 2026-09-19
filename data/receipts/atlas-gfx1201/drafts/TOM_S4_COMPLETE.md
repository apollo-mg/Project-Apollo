# Consolidated S4 report for TheTom -- all six charters
**S4 is complete. All six RST charters run on the RX 9070 XT, 16 GB, gfx1201.**

**First, a retraction.** I told you to consider a lower `--gpu-memory-utilization` default for
16 GB parts. That is wrong, please ignore it. The knob does nothing here. Ladder at seq 4096,
30 s idle observation each:

    util 0.85 -> min free 1701 MB, KV 4128 tokens, watchdog kill
    util 0.80 -> min free 1761 MB, KV 4128 tokens, watchdog kill
    util 0.75 -> min free 1761 MB, KV 4128 tokens, watchdog kill
    util 0.70 -> min free 1722 MB, KV 4128 tokens, watchdog kill

Identical KV allocation across the range. The pledge is a ceiling that was never binding: at 0.85
the server itself printed "util pledge honored: 11.1 GB tracked live within the 13.5 GB budget
(2.5 GB pledge headroom)". Lowering the ceiling just removes slack.

The real lever is `--max-seq-len`, via the buffer arena: seq 4096 arena 1.36 GB (killed at idle),
seq 3072 arena 1.05 GB (survives idle, dies mid-prefill at 2010 MB against the 2048 threshold),
seq 2560 arena 0.90 GB (survives). Then I closed a browser, freed 1.05 GB, and seq 4096 ran with
2845 MB free. It was a co-tenant problem, not an Atlas one. Your watchdog called it correctly
every time.

## Results

| charter | result |
|---|---|
| (a) coherence | PASS. 40/40 returned, 0 errors, 0 empty, 25.3 s. Canaries 9 of 10; the miss is p08 exactly as predicted, reverse "atlas" -> "stalta" |
| (b) VRAM boundary | done, gate unsatisfiable as written (below) |
| (c) cancel/recovery | PASS. 5 kills in prefill + 5 mid-decode (cut after 129-131 SSE chunks), 10/10 next-requests OK, worst VRAM excursion +1.1% against a 10% gate |
| (d) sustained decode | PASS. 163 requests, 0 errors, drift **+0.17%**, no throttling: sclk held 3203-3302 MHz throughout, junction peaked 76 C, memory 82 C, power median 324 W |
| (e) REST conformance | PASS. 9 PASS / 1 FAIL / 0 WARN / 5 INFO, exactly your documented expectation; the FAIL is #1121 |
| (f) concurrency soak | PASS. 650 requests, 0 non-200, 0 empty, **VRAM band 0 MB across the full 30 minutes** |

On (f)'s flatness: free VRAM sat at exactly 2399 MB for all 180 samples in both phases. Not
within-tolerance, unmoving.

## Charter (f) independently confirms #1118, with a diagnostic lead

| phase | median latency | aggregate |
|---|---|---|
| sequential, 20 min | 2.06 s | 61.71 tok/s |
| batch 8, 10 min | 66.62 s | 17.26 tok/s |

Batch 8 gives **3.6x less aggregate throughput** than sequential. If it merely serialised you
would expect 8 x 2.06 = 16.5 s per request; it takes 66.6 s, **4x worse than naive
serialisation**. Your #1118 title already says "9B collapses at batch 8", so this is the same
collapse on a second board -- not R9700-specific, and not caused by 16 GB.

The part that might be new to you: power and clocks move the opposite way to a compute-bound
explanation.

    sequential: sclk median 3219 MHz, power median 295 W
    batch 8:    sclk median 3284 MHz, power median 257 W

The batch phase runs at higher, steadier clocks and draws 38 W less. A GPU clocked up but pulling
less power is waiting, not saturated. That argues for scheduling, synchronisation or memory
stalls rather than an arithmetic bottleneck.

## Two charter-language problems

**(b) asks for something that cannot happen.** The gate is "first refusal named with its exact
error". There is no refusal. I ran the whole specified matrix (seq 2048/4096/8192 at batch 1,
batch 2 and 4 at seq 4096) and every config served. Pushing past it:

    seq 12288 -> granted 12320   full
    seq 16384 -> granted 16416   full
    seq 32768 -> granted 28816   short by 3952, and warned:

    WARN KV OVERCOMMIT: pool fits 0 seq(s) at full --max-seq-len=32768 but
    --max-batch-size=1 requested (2048 block(s)/seq, 1801 block(s) total). Paged KV
    allocates on demand; long-context bursts are back-pressured at the block
    allocator, not refused at boot.

Reword the gate to "first overcommit named with its exact warning" and the run passes cleanly.
Worth raising the ladder to 32768 too, since that is where the behaviour lives.

**(f) says "the largest batch that boots", which is ambiguous.** Batch 32 boots. It answers
/v1/models, logs "Server live and ready", and is terminated four seconds later:

    19:38:00  OOM watchdog: free 1350 MB (threshold 2048) [1/3]
    19:38:01  Server live and ready at 127.0.0.1:8081
    19:38:04  3 consecutive readings below threshold. Terminating.

Note the first watchdog reading precedes the readiness line. A harness that polls readiness and
proceeds selects 32 and then measures a dead server. Suggest "boots and holds", or a stated dwell
time. Usable answer on this board is 8.

## Smaller things

**Your kit scripts are in your gist**, which resolves the S1 blocker I flagged. Worth linking from
the PRD: kernel-census.sh, probe-lds-fp8.sh, probe-gpu.sh, oracle-run.py, oracle-prompts.jsonl,
oracle-compare.py, rest-conformance.py. I used yours for (a) and (e), so those numbers are
directly comparable to an R9700 run.

**Compute parity.** scaleinfo reports 32 multiprocessors here and your HARDWARE.toml declares
sm_count = 32 for the R9700. Both are Navi 48, 64 CU / 32 WGP, 256-bit GDDR6 at ~640 GB/s. The
9070 XT actually has the higher boost clock (2970 vs 2920 MHz).

**Which makes one number I owe you a caveat on.** My (d) run medians 69.68 tok/s where #1107
reports 78-80. I do not think that is a hardware gap. I re-ran (d) fully headless to test the
co-tenant theory and it came out 68.50, i.e. slightly *slower*, so the desktop was not the cause.
Most likely my harness times a complete non-streaming HTTP round trip while yours reports a
decode-only rate, and separately my (d) run had thinking ON where your kit scripts default it off.
Two different quantities rather than two different speeds. If you can tell me how the 78-80 was
measured I will match it.

## Open questions still outstanding

- The 2.36 GB unowned-allocation sweep at seq 32768 shutdown (`loaders_fp8.rs:229`) -- teardown
  accounting, or allocations escaping the ledger?
- Does r9700's `w4a16_gemm_t` honour `ldb`? The lm_head padded-stride warning (248192 != 248077)
  appears at every config here and presumably on your board too.
- The ternary Q2_0 path: your kernels are in the r9700 mirror and built cleanly in my S2, but
  PrismML's shipped Ternary-Bonsai 2 uses ggml type id **142** where Atlas implements **42**, and
  Atlas reads none of the `prism.hadamard.*` metadata the file carries. Is the id-42 path
  considered working and just unwired, or half-landed?
