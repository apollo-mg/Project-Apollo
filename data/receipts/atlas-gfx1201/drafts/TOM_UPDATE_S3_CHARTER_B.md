# Update for TheTom -- S3 + charter (b)

ASCII only. Covers what he has not seen: S3 and RST charter (b). He already has the S0/S1/S2
gap table. Trim freely; the first section is the part that changes his document.

---

No rush at all, enjoy the visit. Parking this here for whenever you get to it.

**S3 is done and Atlas serves on the 9070 XT.** Ornith-1.0-9B-NVFP4, ready in 6 to 9 seconds,
7.4 GB of weights resident, canary correct ("What is the capital of France" returns Paris,
finish_reason stop), VRAM back to baseline after shutdown with no leak. Charter (b) is done too,
and that one turned up something structural.

**1. Charter (b)'s gate cannot be satisfied as written, on any target.**

The gate asks for "first refusal named with its exact error". Atlas has no refusal to name. I ran
the whole specified matrix (seq 2048/4096/8192 at batch 1, batch 2 and 4 at seq 4096) and every
single config served and answered. So I pushed past the charter's range:

    requested seq 12288 -> granted 12320   full
    requested seq 16384 -> granted 16416   full
    requested seq 32768 -> granted 28816   short by 3952

and at 32768 you get this, which is the actual answer:

    WARN KV OVERCOMMIT: pool fits 0 seq(s) at full --max-seq-len=32768 but
    --max-batch-size=1 requested (2048 block(s)/seq, 1801 block(s) total). Paged KV
    allocates on demand; long-context bursts are back-pressured at the block
    allocator, not refused at boot.

Paged KV admits the request, names the overcommit precisely, and back-pressures during use. The
failure mode the charter anticipates does not exist on this path. If the gate were reworded to
"first overcommit named with its exact warning" this run passes cleanly. That warning is close to
ideal as diagnostics go, by the way: it gives the shortfall in blocks, states the design choice,
and says where the consequence lands.

Suggestion: reword the gate, and raise the seq ladder to 32768, since that is where the
interesting behaviour actually lives on a 16 GB board.

**2. It is the buffer arena that squeezes KV, not the weights.**

    seq  4096: pre-KV 10.19 GB = weights 7.42 + buffer arena 1.36 + other 1.41 -> KV 2.19 GB
    seq 32768: pre-KV 11.44 GB = weights 7.42 + buffer arena 2.61 + other 1.41 -> KV 0.90 GB

Weights are fixed, the arena nearly doubles with sequence length, and it comes straight out of the
KV pool. On 32 GB that is absorbed. On 16 GB it is the whole constraint. At seq 32768 the OOM
watchdog logged 182 MB free against its 2048 MB threshold, a single [1/3] reading so no
termination, but that is the closest this card has been to the edge.

Related: at the PRD's --gpu-memory-utilization 0.85, three separate starts gave two that served
and one that self-terminated (three consecutive readings around 1.5 to 1.6 GB, under the 2048 MB
watchdog). n=3 is not a rate, so I am not claiming a frequency, but 0.85 is marginal on 16 GB
where it is comfortable on 32. Might be worth a lower default for 16 GB parts, or setting
AVAROK_KV_EXTERNAL_RESERVE_GB explicitly when a desktop is co-resident. The right value is a
measurement rather than a guess and I have not made it yet.

**3. Your sysfs workaround is load-bearing here, with receipts.**

    INFO free-memory source: amdgpu sysfs /sys/class/drm/card1/device, SCALE build,
    amdgpu device auto-detected

It engaged automatically. Given the 4.00x over-charge I measured caps honest capacity reporting
at roughly 3.9 GiB on a 16 GB board, a 7.4 GB weight load could not have been sized through the
driver API at all. Without that workaround this model does not serve on this card. Atlas also
correctly excluded my desktop: "Atlas-own 10.2 GB live in the alloc ledger; 2.8 GB of
co-tenant/page-cache use excluded".

**4. A third SCALE gap, new one.**

    rocblaslt error: Cannot read "TensileLibrary_lazy_gfx1201.dat": No such file or directory
    WARN cuBLASLt pre-warm failed (request 1 pays lazy init):
         cuBLASLt AlgoGetHeuristic failed: status 7

SCALE bundles hipBLASLt but ships no gfx1201 Tensile library, so the heuristic lookup fails,
pre-warm is skipped, and request 1 pays lazy init. I will file this with Spectral as a third
ticket. Flagging it because it might be adjacent to #1116, though I want to be careful: your
W4A16 prefill kernel is custom CUDA through SCALE and would not route through hipBLASLt, so I am
NOT claiming this explains the 4 TFLOP/s. Only that whatever does route through it is running
untuned.

**5. Two questions rather than findings.**

At seq 32768 shutdown, right after SIGTERM:

    WARN sweep: 301 allocation(s) totalling 2.36 GB had no owner; largest sites:
    crates/spark-model/src/weight_map/loaders_fp8.rs:229 (1252.5 MB ...)

It only appears at that sequence length and only after SIGTERM, so it may be ordinary teardown
accounting. Is a sweep that size expected, or does it mean allocations are escaping the ledger?

And this one shows up at every config:

    WARN lm_head twin uses a PADDED stride (248192 != vocab 248077): this target's
    w4a16_gemm_t MUST accept the `ldb` argument, or decode at padded_n>=5 will read
    sheared rows.

Same warning presumably appears on the R9700, so it may already be answered. Is r9700's
w4a16_gemm_t known to honour ldb?

**6. One practical note for the charter method.**

My first charter run had RUST_LOG=warn, which suppressed the INFO-level KV budget lines, i.e. the
single most informative output of the exercise. The ladder completed and reported six clean
verdicts while throwing away the data that explains them. Worth pinning RUST_LOG=info in the
charter procedure itself rather than leaving it to whoever types the command.

Next up are charters (a) coherence and (e) REST conformance. (d) and (f) are the long ones and I
need to decide first whether to drive them headless from another machine or just subtract the
desktop's VRAM baseline, since (f) gates on flat VRAM and my compositor lives on the card.
