# Update for TheTom -- charters (a)(c)(e), plus a retraction

ASCII only. The retraction is first on purpose: I sent him a recommendation this morning that
turned out to be wrong, and he may act on it.

---

**Correction first: ignore what I said about lowering --gpu-memory-utilization on 16 GB parts.**
I suggested that this morning off the S3 run. It is wrong. The knob does nothing here. I ran the
ladder at seq 4096, 30 s idle observation each:

    util 0.85 -> min free 1701 MB, KV 4128 tokens, watchdog kill
    util 0.80 -> min free 1761 MB, KV 4128 tokens, watchdog kill
    util 0.75 -> min free 1761 MB, KV 4128 tokens, watchdog kill
    util 0.70 -> min free 1722 MB, KV 4128 tokens, watchdog kill

Identical KV allocation across the whole range. The pledge is a ceiling that was never binding:
at 0.85 the server itself printed "util pledge honored: 11.1 GB tracked live within the 13.5 GB
budget (2.5 GB pledge headroom)". Actual usage is 11.1 GB whatever the ceiling says, so lowering
the ceiling just removes slack without changing anything.

**The real lever is --max-seq-len, through the buffer arena:**

    seq 4096: arena 1.36 GB, min free ~1700 MB -> killed at idle, before any request
    seq 3072: arena 1.05 GB, min free  2092 MB -> survives idle, dies during a 2272-token prefill
    seq 2560: arena 0.90 GB, min free  2259 MB -> survives everything

The seq-3072 failure is worth seeing because of how narrow it is:

    16:25:05  Session: 2272 prompt tokens, chunked prefill start
    16:25:08  OOM watchdog: free 2010 MB (threshold 2048) [1/3]
    16:25:10                     2023 MB [2/3]
    16:25:12                     2025 MB [3/3] -> Terminating

A prefill that size costs about 80 MB of transient headroom, which lands seq 3072 twenty-three to
thirty-eight MB under the line. Not a design margin, a rounding error. I later closed a browser
and freed 1.05 GB of desktop VRAM, and seq 4096 now runs with 2845 MB free. So the whole thing
was a co-tenant problem, not an Atlas one. Your watchdog made the right call every time.

**Charter results, all with your kit scripts** (found them in your gist -- worth linking that from
the PRD, it is the S1 blocker I mentioned):

- **(a) coherence: PASS.** 40 of 40 returned, 0 errors, 0 empty, 25.3 s. Canaries 9 of 10, and the
  miss is p08 exactly as your charter predicts: reverse "atlas" gave "stalta". Scored with your
  oracle-compare.py so it is directly comparable to an R9700 run.
- **(c) cancel/recovery: PASS.** 5 client kills during prefill, 5 mid-stream in decode (cut after
  129-131 SSE chunks each). 10 of 10 next-requests OK, worst VRAM excursion +1.1% against a 10%
  gate, server alive at the end. Clean. Run at seq 2560, before I freed the desktop memory.
- **(e) REST conformance: PASS.** 9 PASS, 1 FAIL, 0 WARN, 5 INFO -- exactly your documented
  expectation, and the FAIL is the #1121 unknown-model-returns-200.

**(b) needs a gate reword**, which I sent earlier: there is no refusal to name, because paged KV
admits the request and back-pressures at the block allocator. Your KV OVERCOMMIT warning is the
thing to gate on.

**One incidental worth having:** scaleinfo reports 32 multiprocessors on the 9070 XT, and your
HARDWARE.toml declares sm_count = 32 for the R9700. Both are 64 CU / 32 WGP, so the two boards are
compute-identical and differ only in VRAM and bandwidth. Charter (e)'s TTFT of 8.521 s on ~2973
tokens sits in the same band as your 8.6 s on 2494 tokens, which is what that predicts. Different
prompts and I did not run yours, so I am calling it consistent-with rather than a measurement.

(d) sustained decode is running now at seq 4096. (f) needs the desktop fully headless for its flat
VRAM gate, which I am setting up.
