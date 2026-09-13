# Campaign — EXL3 on the Pascal nodes

**Opened 2026-09-12**, after `kv-tensor-split/RESULT_EXL3_SM60_INFERENCE.md`. Mark's framing: *work from
ground truth until we run out of reasonable reasons not to use it instead.*

**Scope — widened on 2026-09-13: the whole fleet, not just the P100 nodes.** The campaign opened
"EXL3 on the P100 nodes" because `exl3.cu` was compiled out under HIP. buun's `da458765d` fixed that, and
the 9070 now runs EXL3 on the GPU (`RESULT_EXL3_RDNA4.md`). **But it does not follow that EXL3 should run there:** at matched size on the 9070, a GGUF with MTP is
**2.1–2.4× faster**, because MTP gives EXL3 *nothing* on RDNA4 while giving GGUF 1.7×
(`RESULT_EXL3_RDNA4_MTP.md`). The nodes:

- **`.73`**, which sleeps. It takes 10 s to wake and 77–99 s from a cold request to its first completion.
- **`.194`**, which costs a 216 s cold boot and 218 W at idle.
- **NVIDIA's 580 driver branch**, the last that supports Pascal.

## Method

- **The ledger is a list of objections.** Every reason not to switch is an entry, and each entry has one
  status:
  - **RETIRED:** measured, and the objection does not hold.
  - **CONFIRMED:** measured, and it holds.
  - **OPEN:** the test and its cost are named.
  - **NOT RETIRABLE BY US:** it needs upstream work or money.
- **Each test gets its own prereg**, committed before the data it governs.
- **Match VRAM by choosing the bitrate, on both sides.** EXL3 ships a ladder (2.00–6.00bpw for this
  model) and GGUF ships recipes at many sizes, so comparing two *fixed* points measures whoever chose
  the points, not the formats. Mark caught this on 2026-09-12, when test 3 read EXL3 4.00bpw against a
  GGUF 2 GB larger and I called it a trade-off.
- **The campaign ends when every entry is settled:** retired, or confirmed or not retirable and
  accepted. Then the switch is Mark's call.

## Where we stand (measured)

- **Weights:** turboderp `Qwen3.8-27B-exl3` @ 4.00bpw (`mul1` codebook, `head_bits 6`, `mtp_bits 4`).
- **Baseline:** the daily driver's Q6_K, the withdrawn unsloth upload `db81afd1e1`.
- **Hardware and build:** `.73`'s two P100s, buun `9ae8f0f40` plus our e8m0 guard.

| | EXL3 4.00bpw | Q6_K | ratio |
|---|---|---|---|
| perplexity, wikitext-2, 40 chunks | 5.9520 | 5.9195 | +0.55% |
| decode, `-sm tensor`, **MTP off** | 11.26 t/s | 13.22 t/s | 0.85× |
| **decode, the daily driver's exact flags, served sampling** | **13.08 t/s** | **20.25 t/s** (deployed binary) | **0.646×** |
| MTP gain, greedy | 1.24× | 1.69× | acceptance identical: 0.693 vs 0.688 |
| prefill, ~15k tokens | 153.7 t/s | 150.1 t/s | 1.02× |
| VRAM at the daily driver's config (262k VBR, mmproj) | 17.7 GB | 25.8 GB | −8.1 GB |
| size: nominal bits per weight (quantized linears) | 4.00 | ~6.56 | 61% |
| size: VRAM at load (`-sm tensor`, c 8192, the same f16 KV in both) | 14,238 MiB | 22,342 MiB | **64%** |
| size: on disk | 16.88 GB | 22.88 GB | 74% |

**The VRAM ratio (64%) is the one that matters on a P100.** "61% of the bits," as first written here and
in the inference receipt, is the nominal figure. Disk overstates EXL3's GPU footprint:
- **A 2.54 GB bf16 token-embedding table.** It evidently stays in host memory: VRAM at load matches the
  rest of the weights plus the KV cache.
- **A 0.92 GB bf16 vision tower** that the native `qwen35` loader never loads.
- **The remaining 13.40 GB reaches the GPU:** `layers` 12.23, `lm_head` 0.95 at 6 bits, `mtp` 0.21.

**The deployment number is 0.646×** (`RESULT_EXL3_DROPIN.md`).
- **Most of the gap is MTP.** It buys GGUF 1.69× but EXL3 1.24×, at the same acceptance rate, so the loss
  is in verifying drafts, not in making them.
- **Superseded and still valid:** the charter's earlier ~0.45× estimate is superseded. 0.85× remains the
  MTP-off figure.

## The decision table (2026-09-12)

Speed under the daily driver's flags (tests 1 and 7); KLD against a Q8_0 reference at `-ub 8` under
`-sm layer` (test 3). **Two configurations, one table — read the columns separately.**

| option | served t/s | mean KLD | VRAM (KLD run) | prefill t/s |
|---|---|---|---|---|
| UD-IQ4_XS | **24.60** | 0.015727 | 13,500 MiB | 134.8 |
| UD-Q4_K_M | 23.13 | 0.007840 | 15,448 MiB | 140.5 |
| **Q6_K, the daily driver** | 20.25 | **0.002770** | 21,276 MiB | 151.2 |
| EXL3 5.00bpw | 14.14 | 0.003994 | 16,372 MiB | **159.9** |
| EXL3 4.00bpw | 13.08 | 0.012002 | 13,468 MiB | 153.7 |

**GGUF is faster at every quality level; EXL3 is smaller at every quality level.** On `.73` the daily
driver is both faster *and* closer than EXL3 5.00bpw, for 4.9 GB more VRAM that this node has to spare —
so **EXL3's advantage is real but currently unpurchasable here.** It becomes purchasable where VRAM binds:
a 16 GB card, long context if VBR needs the freed 8 GB, or any box where Q6_K's 21 GB does not fit.

## The ledger

| # | objection | status | evidence, or the test that settles it |
|---|---|---|---|
| O1 | **Can't serve from the control plane (HIP)** | **RETIRED 2026-09-13** | buun's `da458765d` enables standalone EXL3 on wave32 devices, and it works on the 9070: **0.6B 64.56 t/s (10× yesterday's CPU path), 27B @ 3.00bpw 22.88 t/s on the int8 path, and all 11 of his EXL3 tests pass on gfx1201** (`RESULT_EXL3_RDNA4.md`). `-ngl 99` now beats `-ngl 0` by 8.6×, where yesterday it lost. His implementation matches `NOTE_EXL3_HIP_PORT.md` idiom for idiom. **One build bug for him:** `HIP_ARCHITECTURES is empty for target test-exl3-byte-dot` when tests are enabled. |
| O2 | **Loses MTP** | RETIRED, with a cost | MTP engages on EXL3 at GGUF's acceptance rate but buys 1.24× instead of 1.69×. The cost is carried in O5. |
| O3 | **Loses vision** | RETIRED | The daily driver's existing `mmproj-F16.gguf` attaches to the EXL3 model and reads the probe. |
| O4 | **Doesn't compose with VBR KV** | RETIRED at load · degrade path OPEN | EXL3 and GGUF log the identical VBR controller init. Both stayed at the f16 entry tier through 14,852 tokens, so VBR's degraded tiers were never exercised with EXL3 weights. Test: a long-context run that forces VBR to degrade. |
| O5 | **Slower** | CONFIRMED · **cause identified and now measured on two architectures** | 0.646× the daily driver on `.73`; **0.42–0.48× on RDNA4 at matched size** (`RESULT_EXL3_RDNA4_MTP.md`). **The cause is row-scaling in the int8 GEMV:** a 4-row verify costs EXL3 2.08× a single row on Pascal and **3.15× on RDNA4**, where GGUF's MMVQ pays 1.37× and 1.74×. **Consequence: MTP buys EXL3 1.29× on Pascal and nothing at all on RDNA4** (every depth slower than off), while GGUF gets 1.70× on both. Acceptance is equal in every test, so drafting works and verification is what costs. **Fixable upstream, and it is now the single biggest lever on EXL3's speed.** |
| O6 | **Quality beyond one perplexity number** | **RETIRED for distribution** · task accuracy still OPEN | Tests 3 and 10 put **thirteen points on one Q8_0 reference** (`RESULT_EXL3_KLD.md`, `RESULT_EXL3_COMPRESSION.md`). **EXL3 sits 1.33–1.45× closer to the reference than unsloth's UD GGUF curve at matched VRAM** from 10.6 to 13.5 GB — a GGUF needs **5–10% more VRAM** for the same fidelity there, and **17% more at 5 bpw**. **Flat across the low end, not widening** (test 10's P-C2 confirms only by 0.001), and at ~9 GB EXL3 2.50bpw and UD-Q2_K_XL are about even. **The GGUF packager matters as much as the format:** the AD- and i1- recipes sit far off the curve. The two buun builds give identical KLD. **Perplexity is retired as a fidelity metric here.** Task accuracy (test 11) waits on Mark's call on an ambiguous selection rule. |
| O7 | **Prefill and long context** | PARTIAL | Prefill is at parity at about 15k tokens (153.7 vs 150.1 t/s). Long context is untested. |
| O8 | **We can't make our own quants** | OPEN · no blocker found in source | There is no quantizer in buun's tree, but exllamav3 sets no architecture gate, and its sampled kernels use `half2` intrinsics Pascal has natively (`NOTE_EXL3_QUANTIZER_ON_SM60.md`). **That is 3 of 113 CUDA sources**, and torch's own sm_60 support matters as much. **Decisive test, about an hour:** convert Qwen3-0.6B on `.73` and compare its perplexity against turboderp's own 0.6B (20.2864). |
| O9 | **Supply is limited to what someone else has published** | RETIRED for the models we run | At least 1,000 EXL3 repos exist; every base on this fleet has one, including `turboderp/Qwen3.8-Flash-Next-exl3` (`NOTE_EXL3_SUPPLY.md`). Two caveats: check `quantization_config` for the `mul1` codebook (only those take the int8 path on sm_60), and trust a publisher's calibration no further than a GGUF packager's. Supply binds only for a model nobody has quantized, which is O8. |
| O10 | **Load time breaks wake-on-demand** | CONFIRMED as deployed · OPEN on NVMe | `.73` reloads its model on every wake. EXL3 loaded in 322 s off `/mnt/HDD`, against 36 s for the Q6_K off NVMe. That would turn today's 77–99 s cold start into about 6 minutes. On NVMe it should load faster than the Q6_K (16.88 vs 22.88 GB), but that is untested because `/mnt/models` has 9.9 GB free. **Blocked on Mark's disk decision.** |
| O11 | **Build carries a local patch** | **RETIRED 2026-09-13** | buun's `86eae269c` upstreamed the e8m0 guard: `da458765d` and `c7f114d34` build clean on CUDA 12.4 with no local patch (`RESULT_O11_CLEAN_BUILD.md`). His EXL3 suite passes **34 of 35 on sm_60** with the node's all-reduce setting; the 35th should skip below cc 7.0 and asserts instead. Commits before `86eae269c` still need `kv-tensor-split/PATCH_e8m0_cuda128_guard.diff`. |

**What EXL3 buys, so far: VRAM at equal quality.** Matched by bitrate, its KLD curve sits below GGUF's at
every size measured, and the gap grows with fidelity — ~790 MiB at KLD 0.012, **~2.9 GB at 0.004**. At the
daily driver's config that shows up as 8.1 GB freed, which is room for context or a second model.
**What it costs: 30-40% of decode speed at matched quality**, most of it a kernel property (O5) rather than the format. **Whether the trade is worth making depends on which resource is scarce** — on `.73`, VRAM is not.

## Design notes

- **KLD (O6, test 3).**
  - **Reference:** the Q8_0, pinned at `unsloth/Qwen3.8-27B-GGUF@4ca72078` (29,047,086,048 B, sha256
    `a680f44a…b67e348`).
  - **It is a reference, not ground truth.** Every KLD is a distance from Q8_0, so the comparisons that
    matter are differences between distances.
  - **Everything runs on `.73`, with one binary, at `-ub 8`.** The small-batch kernels avoid the fp16
    dequant pool that OOM'd the Q6_K there, and that is what lets the 29 GB Q8_0 fit two P100s.
  - **One machine, one backend,** so there is no cross-backend floor to measure.
  - **Why not bf16:** bf16 is 55 GB and fits only on `.194`.
- **Supply (O9).** Check what exists per model before designing around it.

## Order

1. ~~Test 1, drop-in.~~ **DONE** (`RESULT_EXL3_DROPIN.md`): 7 confirmed, 3 falsified.
2. ~~Test 2, O1 on RDNA4.~~ **DONE** (`RESULT_EXL3_HIP.md`): loads, but CPU only. A port looks tractable
   (`NOTE_EXL3_HIP_PORT.md`).
3. ~~Test 3, O6 KLD.~~ **DONE** (`RESULT_EXL3_KLD.md`): EXL3 dominates the GGUF at its own size;
   perplexity is retired as a fidelity metric.
4. ~~Test 6, MTP depth.~~ **DONE, gate failed** (`RESULT_EXL3_DEPTH.md`): per-request depth is ignored
   for MTP, so the curve is unmeasured — but depth 7 makes MTP a **net loss** for EXL3 (0.78×) where
   Q6_K still gains (1.10×).
5. ~~Test 3, Amendment 2 (EXL3 5.00bpw).~~ **DONE:** EXL3's curve is below GGUF's at both sizes.
6. ~~Test 4, the micro-batch cost curve.~~ **DONE** (`RESULT_EXL3_MTP_SWEEP.md`): 2.08x vs 1.37x for a 4-row batch — the MTP gap is a kernel property.
6b. ~~Test 7, the ladder's served speed.~~ **DONE** (`RESULT_EXL3_LADDER_SPEED.md`): the decision table above.
7. ~~O8: read exllamav3's conversion requirements.~~ **DONE, nothing blocks sm_60 in what was read**
   (`NOTE_EXL3_QUANTIZER_ON_SM60.md`). What remains is a real conversion on `.73`.
8. ~~O9 supply.~~ **RETIRED** (`NOTE_EXL3_SUPPLY.md`).
9. ~~The depth curve, properly.~~ **DONE** (`RESULT_EXL3_DEPTH.md`, Amendment 3): EXL3 wants `--draft-max 1`, Q6_K wants 2.
10. **O6 task accuracy** — the verdict metric. KLD settles distribution, not whether answers get worse.
11. **O4 degrade path and O7 long context,** one long-context run (`PREREG_EXL3_LONGCTX.md`, written and
    awaiting Mark).
12. **O10 on NVMe,** after Mark's disk decision.
