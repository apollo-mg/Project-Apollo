# Campaign — EXL3 on the Pascal nodes

**Opened 2026-09-12**, after `kv-tensor-split/RESULT_EXL3_SM60_INFERENCE.md`. Mark's framing: *work from
ground truth until we run out of reasonable reasons not to use it instead.*

**Scope — this is "EXL3 on the P100 nodes", not "EXL3 instead of GGUF."** In buun's fork, all of
`exl3.cu` is compiled out under HIP. On RDNA4, EXL3 loads, but every EXL3 matmul runs on the CPU
(`RESULT_EXL3_HIP.md`). So the control plane, the only always-on box, cannot serve EXL3 at GPU speed.
Every EXL3 deployment on this fleet runs on:

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

## The ledger

| # | objection | status | evidence, or the test that settles it |
|---|---|---|---|
| O1 | **Can't serve from the control plane (HIP)** | CONFIRMED on hardware · NOT RETIRABLE BY US · **port looks tractable** | RDNA4 loads EXL3 and answers correctly, but no EXL3 weight reaches VRAM. A 0.6B decodes at 6.47 t/s, and `-ngl 99` is slower than `-ngl 0` (`RESULT_EXL3_HIP.md`). **A port is smaller than it looks:** every Ampere-only construct already falls back for sm_60, and HIP takes those same branches; what blocks a compile is three unguarded PTX idioms in the trellis decoder, the Ampere GEMV needing exclusion, and the two HIP gates (`NOTE_EXL3_HIP_PORT.md`). Only upstream can do it; Mark offered buun RDNA4 testing and the build tree is standing. |
| O2 | **Loses MTP** | RETIRED, with a cost | MTP engages on EXL3 at GGUF's acceptance rate but buys 1.24× instead of 1.69×. The cost is carried in O5. |
| O3 | **Loses vision** | RETIRED | The daily driver's existing `mmproj-F16.gguf` attaches to the EXL3 model and reads the probe. |
| O4 | **Doesn't compose with VBR KV** | RETIRED at load · degrade path OPEN | EXL3 and GGUF log the identical VBR controller init. Both stayed at the f16 entry tier through 14,852 tokens, so VBR's degraded tiers were never exercised with EXL3 weights. Test: a long-context run that forces VBR to degrade. |
| O5 | **Slower** | CONFIRMED | 0.646× the daily driver as served; 0.627× matched with MTP on; 0.85× with MTP off. **Possibly fixable upstream:** see "Order", item 4. |
| O6 | **Quality beyond one perplexity number** | **RETIRED for distribution** · task accuracy still OPEN | At matched VRAM, EXL3 is **24% closer** to a Q8_0 reference than UD-IQ4_XS while using 32 MiB less, and a GGUF needs **~790 MiB more VRAM** to match its fidelity (`RESULT_EXL3_KLD.md`). **Perplexity is retired as a fidelity metric here:** it ranks the same files the other way and scores two quants *better than the reference they approximate*. Still open: task accuracy, and the like-for-like comparison at larger sizes (Amendment 2 adds EXL3 5.00bpw, since matching VRAM means choosing the bitrate on both sides). |
| O7 | **Prefill and long context** | PARTIAL | Prefill is at parity at about 15k tokens (153.7 vs 150.1 t/s). Long context is untested. |
| O8 | **We can't make our own quants** | OPEN · no blocker found in source | There is no quantizer in buun's tree, but exllamav3 sets no architecture gate, and its sampled kernels use `half2` intrinsics Pascal has natively (`NOTE_EXL3_QUANTIZER_ON_SM60.md`). **That is 3 of 113 CUDA sources**, and torch's own sm_60 support matters as much. **Decisive test, about an hour:** convert Qwen3-0.6B on `.73` and compare its perplexity against turboderp's own 0.6B (20.2864). |
| O9 | **Supply is limited to what someone else has published** | RETIRED for the models we run | At least 1,000 EXL3 repos exist; every base on this fleet has one, including `turboderp/Qwen3.8-Flash-Next-exl3` (`NOTE_EXL3_SUPPLY.md`). Two caveats: check `quantization_config` for the `mul1` codebook (only those take the int8 path on sm_60), and trust a publisher's calibration no further than a GGUF packager's. Supply binds only for a model nobody has quantized, which is O8. |
| O10 | **Load time breaks wake-on-demand** | CONFIRMED as deployed · OPEN on NVMe | `.73` reloads its model on every wake. EXL3 loaded in 322 s off `/mnt/HDD`, against 36 s for the Q6_K off NVMe. That would turn today's 77–99 s cold start into about 6 minutes. On NVMe it should load faster than the Q6_K (16.88 vs 22.88 GB), but that is untested because `/mnt/models` has 9.9 GB free. **Blocked on Mark's disk decision.** |
| O11 | **Build carries a local patch** | OPEN upstream | Any CUDA below 12.8 needs our 2-line e8m0 guard (`kv-tensor-split/PATCH_e8m0_cuda128_guard.diff`). Offering it upstream is Mark's call. |

**What EXL3 buys, so far:** about 8 GB of VRAM at the daily driver's config, and perplexity within 0.55%
at 64% of the VRAM. That VRAM is room for context or a second model. Test 3 says whether the quality
holds beyond perplexity.

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
2. ~~O1, RDNA4.~~ **DONE** (`RESULT_EXL3_HIP.md`): loads, but CPU only.
3. **O6 KLD: RUNNING** (`PREREG_EXL3_KLD.md`).
4. **The MTP verification test** is a `--draft-max` sweep, or an EXL3 int8 GEMV timing at m = 1 to 8. It
   decides whether O5 is a kernel problem buun could fix. That makes it the most valuable next test.
5. ~~O8: read exllamav3's conversion requirements.~~ **DONE, and nothing blocks sm_60 in what was read**
   (`NOTE_EXL3_QUANTIZER_ON_SM60.md`). What remains is a real conversion on `.73`.
6. **O6 task accuracy.**
7. **O4 degrade path and O7 long context,** one long-context run.
8. **O10 on NVMe,** after Mark's disk decision.
