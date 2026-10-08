# Result -- Kaden's P100 fork (Kmic-68 `e48e240a8`) against the .73 daily driver: 2.06x plain decode and 1.83x prefill at matched flags; served, 2.14x decode at 2k, 2.23x at 32k and 4.10x at 128k. All six speed/validity predictions hold. P7 fails badly: `GGML_CUDA_P2P=1` takes decode to 0.08 t/s on BOTH builds, because the VT-d IOMMU faults every peer write

**2026-10-08.** Pre-registration `PREREG_KMIC_VS_DAILY_73.md` (`4619fc58`), with Deviations 1-3, each committed before
its rows (`bfaba5e4`, `26a7a35b`, `bc47b071`).
- **Runner:** `run_wrap.sh` -> `run_kmic.sh` (desktop) -> `launch73.sh` (on .73) + `kbench.py`.
- **Raw:** `raw/*.jsonl` (one record per completion, with timings, collapse stats and decoded text) and `raw/run.log`.
  `raw/logs/` holds each cell's server log, exact command, pre-leg clocks and 2 s power log, plus
  `iommu_p2p_evidence.txt`.

## Setup

- **Host:** .73: i5-8600K, 16 GB, 2x Tesla P100-PCIE-16GB on separate CPU root ports (`PHB`, no NVLink). Driver
  580.178.04, kernel 7.0.0-31-generic. 150 W cap and 1,328 MHz application clocks on both cards for every leg (V4).
- **Model:** unsloth `Qwen3.8-27B-Q6_K.gguf`, the daily driver's, with `mmproj-F16.gguf` on the served legs.
- **D (daily):** buun `510cbbbfa` + `f08683ffa`. Served with the wake proxy's command minus `--resume*`:
  - VBR KV (floor t4, auto budget);
  - `-np 2 --kv-unified`;
  - MTP draft 3;
  - no `-b`/`-ub`, so the defaults of 2048/**512**.
- **K (Kaden):** `e48e240a8` plus a one-line `#include <algorithm>` (Deviation 1). Served with his QUICKSTART command
  minus `GGML_CUDA_P2P=1` (Deviation 3):
  - q4_0/q4_0 KV;
  - `-np 1`;
  - MTP draft 4 at `p-min 0.2`;
  - `-b 32768 -ub 2048`;
  - our F16 projector. The `-ub 1024` fallback was not needed.
- **Node state:** the wake proxy was stopped from just before 12:08 until 14:16:54. A completion through `:8099` at
  14:21 returned "OK" from a cold start in 62 s.

## M1 -- matched flags (f16 KV, no MTP, no projector, `-ub 2048`, 2k prompt, 256 tokens greedy, 3 reps per cell, ABBA)

| cell | prefill t/s | decode t/s |
|---|---|---|
| MD0a | 218.1, 220.6, 220.4 | 15.05, 15.04, 15.04 |
| MK0a | 401.9, 414.0, 380.9 | 31.02, 30.93, 30.90 |
| MK0b | 398.6, 400.7, 410.9 | 31.02, 30.94, 30.89 |
| MD0b | 217.3, 220.6, 220.0 | 15.05, 15.02, 14.99 |
| **D mean / K mean** | **219.5 / 401.2 = 1.83x** | **15.03 / 30.95 = 2.06x** |

- **This is the only kernel-for-kernel comparison in the test.** KV, MTP, batch size and projector are identical, so
  the 2.06x decode gap is in the weight path: K's tuned sm_60 matvec against D's, which runs fp32 math under the
  carve-out.
- **Prefill spread:** the per-cell ABBA ratios are 1.82x and 1.84x. The worst rep pairing (380.9 / 220.6) is 1.73x.
- **Greedy text:** K's 256-token greedy output is byte-identical to D's (1,041 characters) on this prompt. Each build
  is also identical to itself across all six reps. That is one prompt, not a quality result; the KLD panel was not
  run.

## M2 -- each arm as it serves (2k/32k seeds 1-2 on legs D1 K1 K2 D2; 128k seed 1 on D1/K1; 512 tokens at temperature 1.0)

| depth | D decode | K decode | **K/D** | D prefill | K prefill | **K/D** |
|---|---|---|---|---|---|---|
| 2k (n=4) | 26.51 [24.3-28.6] | 56.71 [51.9-62.3] | **2.14x** | 176.8 | 375.5 [349.7-397.9] | 2.12x |
| 32k (n=4) | 21.68 [21.3-22.1] | 48.36 [44.8-52.8] | **2.23x** | 158.8 | 385.4 [383.7-387.0] | **2.43x** |
| 128k (n=1) | 11.25 | 46.16 | **4.10x** | 98.4 | 296.8 | 3.02x |

- **MTP acceptance** (accepted/drafted): D 0.750 / 0.682 / 0.843 at 2k / 32k / 128k; K 0.676 / 0.611 / 0.781. K
  drafts deeper (4 against 3) and accepts a smaller share, and still decodes 2.1-4.1x faster.
- **Depth falloff, 2k -> 128k:** D keeps 0.42 of its 2k decode, K keeps 0.81. Prefill: D keeps 0.56, K 0.79.
  - This conflates depth with text, at n=1: each depth continues a different slice.
  - Acceptance at 128k is higher on both arms (0.84 and 0.78, against 0.68 and 0.61 at 32k), which flatters both
    128k decode figures.
  - It also flatters the README comparison below. It barely moves the 4.10x ratio, since both arms get the lift.
- **The 128k leg's wall time:** D 1,378 s, K 454 s.
- **Against the daily driver's 09-24 curve** (`split-prefill-73`, buun `08826ad6e` at 1,063 MHz: decode 24.7 -> 8.0,
  prefill 151 -> 99), today's D at 1,328 MHz is 26.5 -> 11.25 decode and 176.8 -> 98.4 prefill.
- **Against Kaden's README** (175 W): his MTP decode of 54 t/s at 2k and 38 t/s at 122k compare with K here at 56.7
  (2k) and 46.2 (128k) under our 150 W cap. His tg256 of 33.2 compares with 30.95 here, but M1 decodes after a 2k
  prompt and his figure has none.

### What the served rows do and do not isolate

| | D | K |
|---|---|---|
| KV cache | VBR: f16 at 2k/32k (`kv_bpv` 16.0 / 15.3-15.8); **at the t4 floor at 128k (4.22 bpv)**, with "VBR budget 9088 MiB exceeded ... clamped at the --vbr-floor" | q4_0 / q4_0 throughout |
| slots | `-np 2 --kv-unified` | `-np 1` |
| MTP | draft 3 | draft 4, `p-min 0.2`, sampled drafter (`LLAMA_SPEC_*` env) |
| batch | `-b 2048 -ub 512` (defaults) | `-b 32768 -ub 2048` |

- **Part of the prefill gap is D's `-ub 512`, not K's code.** D prefills 219.5 t/s at `-ub 2048` in M1 and 176.8 served
  at 2k. Adding `-ub 2048` to the daily command should recover some of it. That was not tested here, and it costs
  compute-buffer VRAM that VBR's auto budget would otherwise give to KV.
  - **Tested the same day in `ub-daily-73/RESULT_UB_DAILY_73.md`: it does not.** `-ub 2048` costs +2,168 MiB per
    card and every real request fails (the MTP draft context runs out of VRAM on GPU 0). `-ub 1024` buys 1.14-1.16x
    prefill, but drops the KV to ~4.75 bits/value at 32k and fails at 102k tokens.
- **The 128k decode gap (4.10x) has three candidate causes, and none was isolated:**
  - the per-call whole-cache f16 conversion that D's `launch_fattn` still does and K removed (the registered
    mechanism behind P4);
  - D running at the VBR floor at that depth;
  - `-np 2`.

## Validity checks

| check | result |
|---|---|
| **V1** tokenizer | **pass**: identical `/tokenize` (920 ids) on all 8 cells |
| **V2** no collapse | **pass**: every K completion has a longest run of 2-16 characters (< 64) and 60-75 distinct characters (> 20). The 16-character run at 128k occurs on D too, so it is in the source text. |
| **V3** vision on K | **pass**: the `media_probe.png` answer is word-for-word identical on K1 and D1 ("HARBOR 4729", the blue rectangle, the red circle). K's image request took 5.5 s, D's 13.8 s. |
| **V4** clocks | **pass**: 150.00 W and 1,328 MHz application clocks on both GPUs before every leg (`raw/logs/*.clocks`) |
| **V5** survived | **pass**: all 8 cells alive at the end, `abort_lines 0` |

## Registered verdicts

| # | claim | conf. | result |
|---|---|---|---|
| P1 | M1 plain decode K >= 1.5x D | 0.7 | **holds: 2.06x** |
| P2 | M1 prefill K >= 1.8x D | 0.6 | **holds: 1.83x** (ABBA cells 1.82x and 1.84x) |
| P3 | served MTP decode at 2k K >= 1.5x | 0.65 | **holds: 2.14x** |
| P4 | served MTP decode at 128k K >= 2.5x | 0.6 | **holds: 4.10x** (n=1 per arm). Its registered mechanism, the f16 conversion, was not isolated (see above). |
| P5 | 32k prefill K >= 2x | 0.6 | **holds: 2.43x**, partly D's `-ub 512` |
| P6 | V2 and V3 pass on K at `-ub 2048` with the F16 projector, no fallback | 0.6 | **holds** |
| P7 | M1: D with `GGML_CUDA_P2P=1` >= 3 % faster than D0 | 0.5 | **fails, by about 190x in the wrong direction**: 0.08 t/s against 15.0 |

## Finding -- `GGML_CUDA_P2P=1` on .73: the IOMMU blocks every peer write

- **Symptom (Deviations 2-3).** Decode falls to 0.08 t/s (13 s per token) on **both** builds. 2k prefill stays at
  89-125 t/s, because batched ubatches amortise the stalls and single tokens do not. The cards report 99-100 %
  utilization while drawing ~35 W, which Mark spotted on the telemetry. K's QUICKSTART recommends this env.
- **Mechanism.** The kernel logged DMAR write faults from each GPU to addresses in the *other* GPU's BARs:

  | GPU | its BARs | faulted writes go to |
  |---|---|---|
  | 01:00.0 | BAR0 `0x40000000`, BAR1 `0x2000000000` | `0x2800000000`, `0x2800009000`, `0xee139000` (all in 02:00.0's BARs) |
  | 02:00.0 | BAR0 `0xee000000`, BAR1 `0x2800000000` | `0x2000000000`, `0x2000009000`, `0x40139000` (all in 01:00.0's BARs) |

  - Example line: `DMAR: [DMA Write NO_PASID] Request device [01:00.0] fault addr 0x2800000000 [fault reason 0x05]
    PTE Write access is not set`.
  - Counts: 1,968 logged GPU fault lines, plus 655 rate-limit notices covering **7,445,787 rate-limited fault
    messages**. That counts suppressed log calls, not faults one for one.
  - VT-d is enabled in firmware, and the kernel runs it in DMA-translation mode (default; the cmdline is only `ro quiet
    splash`). Read directly, the GPUs' IOMMU group 2 has domain type `DMA-FQ` (translation; passthrough would read
    `identity`). The peer apertures are not in its page tables, so each peer write faults.
- **Control by time.** GPU faults occur only from 12:08 to 13:09, which is the MD1 and MK1 (P2P) windows. There are
  **none** in the 66 minutes of non-P2P cells from 13:10 to 14:16 (`iommu_p2p_evidence.txt`, bucketed by 10-minute
  window). The Optane H10 at 0a:00.0 also logs about one read fault a day, before and during the run; that is
  unrelated.
- **The readiness probe lies.** `nvidia-smi topo -p2p r` reports OK, and CUDA enables peer access without error, so
  only the kernel log shows anything.
- **Deviation 3's hypothesis is superseded as the explanation.** It guessed that peer reads across client-CPU root
  ports are emulated. The IOMMU accounts for this stall, and every fault is a write. Whether root-port P2P actually
  helps once translation is off is what an `iommu=pt` test would show. The prereg text stands as written.
- **Fix candidates, UNTESTED:** `iommu=pt` (keeps VT-d available, identity-maps DMA) or `intel_iommu=off` on the kernel
  cmdline, or VT-d off in firmware. Each needs a reboot. Until one is measured, `GGML_CUDA_P2P=1` stays off on .73.

## Reproducibility observation (not registered)

- **D is seed-reproducible at temperature 1.0.** D1 and D2 are byte-identical on all four seeded completions (2k and
  32k, seeds 1-2). Their draft counts match exactly, and their timings are within 0.6 %.
- **K is not.** K1 and K2 diverge at characters 57, 44, 373 and 5 on the same four requests. K is deterministic at
  temperature 0 (MK0a = MK0b, and both equal D).
- **The likely cause, not verified:** K's sampled drafter (`LLAMA_SPEC_SAMPLE_TEMP`, `LLAMA_SPEC_DRAFT_TOPK`) draws
  from an unseeded RNG.
- **Consequence:** K's served spread (51.9-62.3 t/s at 2k) mixes kernel noise with acceptance on different texts, and
  a seeded A/B on K needs temperature 0.

## What it means

- **Kaden's fork is about 2x faster than our daily driver on the same rig and model,** in both the matched-flag
  measurement and as served. His published numbers reproduce at our 150 W cap.
- **The matched-flag result is the one to borrow from:** 2.06x decode with f16 KV and no MTP points at the sm_60
  weight path. In D that path runs fp32 math under the carve-out; in K it uses fp16 products with fp32 folds.
- **The served gap widens with depth** (2.1x at 2k to 4.1x at 128k). The f16-conversion fix is the registered
  candidate, but the KV-format and slot differences mean this test does not show it.
- **Quality was not compared.** D does fp32 math and K does fp16 products, served on q4_0 KV against VBR. The only
  evidence here is one 256-token greedy match. Before .73 switches, a KLD panel against an fp32 base is the missing
  piece. Switching is Mark's decision.
- **Not tested** (as registered): `-np 2` on K, `--resume` (K has no equivalent), tool calling, depths above 128k.
