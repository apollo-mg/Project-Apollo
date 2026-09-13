# Result — Flash-Next on `.194`: residency buys decode, not prefill, and spilling experts is nearly free where spilling layers is not

**Run 2026-09-13, 13:07–13:55, `.194`**, Stage 1 of `PREREG_FLASHNEXT_RESIDENCY.md` (`5972e9e`; Amendment 1
`ff1a17d`, Amendment 2 `caa4e09`). Driver `flashnext_residency.py` at sha `3699e75d`, scorer
`tools/score_flashnext_residency.py`, raw rows in `flashnext_res/results.jsonl`. Build buun **`c7f114d34`**,
clean worktree, sm_60, GCC 15.2. 4× Tesla P100 at 150 W. **All six weight shards matched unsloth's
published sha256.** Stage 2 (EXL3 3.05bpw) is staged and follows separately.

## Headline

| arm | what sits on the CPU | GPU MiB (4 cards) | decode, 500-token prompt | prefill, 1,800 |
|---|---|---|---|---|
| **F-Q2** — UD-Q2_K_XL, `-ngl 99` | nothing but the n-gram table | 50,190 | **21.05 tok/s** | 144.4 |
| **X-Q2** — `-ngl 99 -ot` experts of layers 44–47 | 4 layers' **experts** | 46,390 | **19.90** | 128.9 |
| **P-Q2** — `-ngl 44` | 4 **whole** layers | 44,872 | **13.07** | 106.7 |
| **P-IQ4** — UD-IQ4_XS, `-ngl 44` | 4 whole layers | 57,138 | 11.63 | 105.3 |
| **P-IQ4-numa** — `+ --numa distribute` | 4 whole layers | 57,138 | 12.58 | 96.2 |
| **P-IQ4-b** — drift control | 4 whole layers | 57,138 | 12.08 | 103.0 |

Medians of three reps. Full table, including 3,600-token prompts, in the scorer output below.

## Four findings

**1. Fully resident, a 180B MoE decodes at 21 tok/s on four P100s** — **1.81×** today's best-quality
configuration (IQ4_XS, 4 layers spilled, 11.63) on the same build. The UD-Q2_K_XL quant occupies 50,190
MiB across the four cards, matching the ~50 GB predicted from its tensor table.

**2. Spill experts, not layers.** Moving the **experts** of four layers to the CPU cost **5.5%** of decode
(19.90 vs 21.05). Moving the **same four layers whole** cost **38%** (13.07). A token routes to 10 of 512
experts per layer, so the CPU touches a sliver of the spilled experts; a whole layer drags its dense
attention, SSM state and KV onto the CPU as well. In seconds per token: the expert spill adds ~3 ms, the
layer spill ~29 ms. **This was not a prediction — it is the arm P-R6 needed, read for speed as well.**

**3. Residency buys decode, and much less prefill** — P-R1 and P-R2 both confirmed. Decode 1.61×,
prefill 1.35×. **This weakens our own 09-03 attribution** (`RESULT_FLASHNEXT_PREFILL.md`), which called
the flat prefill a host-streaming limit: with nothing streaming at all, prefill is still ~131–144 tok/s. Mark's
guiTOP video of X-Q2 (`NOTE_GUITOP_XQ2_UTILIZATION.md`) shows why prefill cannot be fast here: **one card
works at a time**. Whether pipeline parallelism engages for the fully resident arm is being checked by
the post-run verifier.

**4. `--numa distribute` is a trade, not a win:** **+6.1% decode** over the mean of its two controls
(P-R5 confirmed; the controls drifted 3.9%, less than the effect), and **−8 to −9% prefill** at every
prompt length. The same shape as DS4, where it traded a worse cold first response for warm throughput.

## Host memory bandwidth — the baseline for a DIMM upgrade

| configuration | triad GB/s |
|---|---|
| node 0 local (10 threads) | 22.68 |
| node 1 local | 22.68 |
| node 0 CPUs → node 1 memory | **7.00** |
| interleaved across both (20 threads) | 27.90 |
| first-touch, both sockets (20 threads) | 45.14 |

**Local runs at 66% of the two-channel theoretical 34.1 GB/s; remote runs at 31% of local.** Filling
C1/D1/G1/H1 should roughly double the local figures and cannot touch the remote path. **For Flash-Next
specifically, host bandwidth only matters for what spills** — ~3 ms per token when experts spill.

## Predictions, scored by the committed scorer

| id | prediction | result |
|---|---|---|
| P-R1 | residency buys decode, ≥ 1.3× | **CONFIRMED** — 1.61× |
| P-R2 | residency does not buy prefill, < 1.5× | **CONFIRMED** — 1.35× |
| P-R3 | resident prefill flat within ±20% (500 → 3,600) | **FALSIFIED** — −20.2%, on noisy reps (below) |
| P-R4 | P-IQ4 decode within ±15% of 08-28's ~9.0 | **FALSIFIED** — 11.63, +29.2% |
| P-R5 | `--numa distribute` ≥ +3% decode | **CONFIRMED** — +6.1%, control drift 3.9% |
| P-R6 | `-ot` moves ≥ 2,000 MiB off the GPUs | **CONFIRMED** — −3,800 MiB (card 3: 11,815 → 7,975) |
| P-BW1 | local triad 50–80% of theoretical | **CONFIRMED** — 66% on both nodes |
| P-BW2 | remote ≤ 0.7× local | **CONFIRMED** — 0.31× |
| P-BW3 | first-touch both sockets ≥ 1.7× one | **CONFIRMED** — 1.99× |

**P-R3 is a knife-edge and is reported as one.** F-Q2's 3,600-token reps were 102.7 / 104.5 / 130.4 tok/s
and its 500-token reps 93.7 / 131.0 / 131.2. The committed statistic is the median, so −20.2% stands; best
of three would read flat. The spread at 3,600 is larger than the effect being tested.

**P-R4 is build drift, not a hardware change.** The 08-28 number came from Tom's `d74823a0c` with default
KV; today's is buun `c7f114d34` with explicit f16 KV, at a longer prompt. **Flash-Next numbers from before
today are not comparable to these without a rerun.**

## A protocol flaw worth fixing next time

**The first request at each new prompt length is 20–30% slower in prefill, in every arm** (F-Q2 at 500:
93.7 then 131.0; X-Q2: 99.1 then 141.5; P-Q2: 89.9 then 129.3). The single 64-token warm-up does not warm
the longer shapes. Medians absorb it at three reps except where two reps run slow, which is exactly P-R3.
**Next run: one discarded warm-up per length.**

## What this says about the EXL3 question

- **Residency is worth 1.61× in decode here** — the prize EXL3 3.05bpw would claim by fitting at
  UD-Q2_K_XL's footprint with IQ4-class fidelity.
- **Finding 2 shrinks that prize for GGUF too.** A GGUF that misses residency by a few layers can recover
  most of it by spilling experts instead of layers. IQ4_XS missed only because **card 0** overflowed at
  `-ngl 99` (16,847 MiB requested, 08-28); moving two to four layers' experts off card 0 (`-ncmoe 2`–`4`)
  should fit it. **Untested and not preregistered** — the obvious next arm: IQ4-class quality possibly near
  20 tok/s, with files already on disk.
- **So the case for EXL3 on `.194` now rests mostly on quality per byte** (turboderp's 0.0177 against
  UD-Q2_K_XL's 0.0533), not on residency. Stage 2 measures its speed; quality needs a task benchmark.

## Deviations

- **The server-log parse found nothing** (Amendment 2): no buffer sizes, no KV types at default verbosity.
  The f16-KV check was vacuous; a load-only reload at `-lv 4` (`post_stage1_verify.sh`) supplies the
  positive check, recorded in an addendum when it lands.
- **P-R6 was scored on summed GPU memory after load**, not model buffers (Amendment 2).
- **Full per-request timings were not recorded in Stage 1** (added for Stage 2). Speculation was necessarily
  off: no draft model or MTP sidecar was loaded and no speculative flags were passed.
- **The 08-28 comparison crosses builds** (P-R4).

## Scorer output

```
| arm | loaded | GPU MiB after load (per card = sum) | pp 500 / 1800 / 3600 | tg @500 / 1800 / 3600 |
|---|---|---|---|---|
| F-Q2 | True | [13481, 12447, 12447, 11815] = 50190 | 131.0 / 144.4 / 104.5 | 21.05 / 20.94 / 19.03 |
| P-Q2 | True | [11681, 11269, 11277, 10645] = 44872 | 129.3 / 106.7 / 117.0 | 13.07 / 13.22 / 12.20 |
| X-Q2 | True | [13901, 12257, 12257, 7975] = 46390 | 141.4 / 128.9 / 141.2 | 19.90 / 20.99 / 19.08 |
| P-IQ4 | True | [14769, 13959, 14365, 14045] = 57138 | 115.7 / 105.3 / 115.2 | 11.63 / 12.05 / 11.12 |
| P-IQ4-numa | True | [14769, 13959, 14365, 14045] = 57138 | 104.9 / 96.2 / 105.9 | 12.58 / 12.49 / 11.53 |
| P-IQ4-b | True | [14769, 13959, 14365, 14045] = 57138 | 117.8 / 103.0 / 112.6 | 12.08 / 12.19 / 11.12 |
```

---

## Addendum — 14:02: the post-run verifier

`post_stage1_verify.sh` reloaded each configuration with the driver's exact flags plus `-lv 4`, load only, no requests:

| config | KV cache | pipeline parallelism |
|---|---|---|
| F-Q2 | K f16, V f16 | **enabled** |
| P-Q2 | K f16, V f16 | off |
| X-Q2 | K f16, V f16 | off |
| P-IQ4 (P-IQ4-numa and -b use the same flags) | K f16, V f16 | off |

- **The vacuous f16 check hid nothing:** every configuration used f16 KV, as declared.
- **Pipeline parallelism engaged exactly where the code says it can** (fully offloaded, no tensor overrides) — **and it
  did not help.** F-Q2's prefill (131.0 / 144.4 / 104.5 tok/s) is no better than X-Q2's with it off (141.4 / 128.9 /
  141.2). Something serializes prefill regardless; one `nsys` capture of F-Q2 would show what (BACKLOG S8).
- At `-lv 4` the loader lines do appear (6–7 buffer lines per configuration), in `flashnext_res/verify/load_*.log`.

**A follow-up found reading buun's `common/fit.cpp`:** the auto-fit has a placement mode commented *"everything but
sparse MoE weights"* (`LAYER_FRACTION_MOE`, line 28) and MoE-cache-aware planning. **Every run here used `-fit off`**,
the fleet's rule on Pascal since the row-split crashes — which is what forced whole-layer spills. **Whether `-fit` now
spills Flash-Next's experts on its own, and whether it still crashes on Pascal, is untested**, and belongs with the
`-ncmoe` follow-up.

---

## Addendum — Stage 3, 14:55–15:02: spilling experts rescues IQ4_XS, and decode here is overhead-bound

| arm | placement | GPU MiB after load | decode 500 / 1,800 / 3,600 | prefill 500 / 1,800 / 3,600 |
|---|---|---|---|---|
| **S3-X4** | `-ngl 99 -ncmoe 2` | [15515, 15191, 15591, 15269] = **61,566** | **21.28 / 21.37 / 18.97** | 146.5 / 141.6 / 146.0 |
| S3-FIT | `-ngl 99 -fit on` | did not load | — | — |

| id | prediction | result |
|---|---|---|
| P-S1 | IQ4_XS loads at `-ncmoe 2` | **CONFIRMED** — card 0 at 15,515 MiB, under its 16,384 |
| P-S2 | expert spill rescues IQ4_XS, ≥ 1.4× P-IQ4 | **CONFIRMED** — 21.28 vs 11.63 tok/s = **1.83×** |
| P-S3 | the overhead-bound cost model, > 17.5 tok/s | **CONFIRMED** — 21.28 (bandwidth-bound predicted 15.7) |
| P-S4 | `-fit on` loads on Pascal | **FALSIFIED as coded** — by the arm, not the hardware; see Amendment 5 |
| P-S5 | auto-fit spills experts | **NOT TESTABLE** — the fitter never ran |

**1. The overflow that kept IQ4_XS off the cards was two layers of experts.** Moving them to the CPU brings card 0
from 16,847 MiB (the 08-28 request) to 15,515, and the model runs.

**2. Decode on this box is overhead-bound, not bandwidth-bound — the day's most useful placement fact.** IQ4_XS
carries **1.30×** UD-Q2_K_XL's resident bytes and decodes at **the same speed** (21.28 vs 21.05 tok/s). A cost
model built on bytes and bandwidth would have predicted 15.7 and mis-ranked every placement choice. **Bits are
nearly free in decode here; per-token overhead is the scarce thing.**

**3. So the best Flash-Next configuration measured on `.194` today is UD-IQ4_XS with `-ncmoe 2`:** IQ4-class
fidelity at **21.3 tok/s**, against 11.63 for the same quant with four whole layers spilled, and the same speed as
a 3-bit quant fully resident. Files already on disk, one flag.

**4. Prefill is unchanged by the placement** (141.6–146.5 tok/s, marginally above F-Q2's), consistent with Stage 1's
P-R2 and with the one-card-at-a-time picture in `NOTE_GUITOP_XQ2_UTILIZATION.md`.

**5. The protocol flaw repeats:** the first rep at each length is slow again (98.9 / 146.5 / 146.8 tok/s prefill at
500). Medians absorb it; the fix is a warm-up per length.

**6. The verbose reload confirms the placement:** 49/49 layers offloaded, K and V both f16.

**What it means for Stage 2.** The prize EXL3 3.05bpw was to claim here — IQ4-class fidelity at a resident
footprint — is now available to a GGUF that spills two layers' experts. turboderp's own chart puts UD-IQ4_XS
(0.0165) slightly ahead of EXL3 3.05bpw (0.0177) in fidelity, so **the remaining question for EXL3 on `.194` is
whether it can beat 21.3 tok/s at comparable fidelity.** That is what the retry measures.

---

## Addendum — Stage 2 (retry), 15:35–15:51: EXL3 3.05bpw runs on Pascal, and wins on quality per byte

The first attempt died on disk space (Amendment 4). The retry ran the arm unchanged: the 24 files re-verified
against the manifest in 1,133 s, the model loaded in **about 11 min 40 s** (15:35:48 → first request 15:47:30),
answered "17 × 23" correctly, and completed every rep. **All five Stage 2 predictions confirmed.**

| id | prediction | result |
|---|---|---|
| P-X1 | loads and answers coherently on sm_60 | **CONFIRMED** |
| P-X2 | all layers resident, ≥ 40,000 MiB on the cards | **CONFIRMED** — 50,060 MiB; the reload reports 50/50 layers |
| P-X3 | decode ≥ P-IQ4 | **CONFIRMED** — 18.41 vs 11.63 tok/s |
| P-X4 | decode ≤ F-Q2 | **CONFIRMED** — 18.41 vs 21.05 tok/s |
| P-X5 | prefill ≤ 0.75× F-Q2 at 1,800 | **CONFIRMED** — 99.3 vs 108.3 (0.69×) |

### The matched-footprint comparison — the cleanest in the campaign

| configuration | GPU MiB | decode 500 / 1,800 / 3,600 | prefill 500 / 1,800 / 3,600 | KLD (turboderp's chart) |
|---|---|---|---|---|
| **EXL3 3.05bpw_h5_ng5** | **50,060** | 18.41 / 18.40 / 16.79 | 95.8 / 99.3 / 99.5 | **0.0177** |
| UD-Q2_K_XL, fully resident | 50,190 | 21.05 / 20.94 / 19.03 | 131.0 / 144.4 / 104.5 | 0.0533 |
| UD-IQ4_XS, `-ncmoe 2` | 61,566 | 21.28 / 21.37 / 18.97 | 146.5 / 141.6 / 146.0 | 0.0165 |

**The two 50 GB configurations sit 130 MiB apart.** At that footprint EXL3 is **3.0× closer to the reference**
than the GGUF and decodes at **0.87×** its speed, with prefill at **0.69×**. That is the EXL3 trade stated
plainly, and it is the first configuration on this fleet where EXL3's advantage is purchasable: on `.73` the
ladder found GGUF faster at every quality level with VRAM to spare.

**But `.194` also has VRAM to spare.** Spending 11.5 GB more on UD-IQ4_XS with two layers' experts spilled is
**faster (21.28 vs 18.41) and slightly better (0.0165 vs 0.0177)**. So EXL3 wins the matched-footprint
comparison and still loses the machine: **the practical pick on `.194` remains UD-IQ4_XS with `-ncmoe 2`.**
EXL3 3.05bpw becomes the pick on a box where ~50 GB is the ceiling.

**Fidelity here is turboderp's**, from his model card: his corpus, his reference, his method. **We cannot measure
Flash-Next KLD on this fleet** — a Q8_0 reference is ~190 GB. Our own 27B measurement found a smaller EXL3
advantage than his charts imply (`exl3-campaign/RESULT_EXL3_COMPRESSION.md`), so treat the 3.0× as his number,
not ours.

**Two costs the table does not show.** EXL3 took **11.7 minutes to load** against roughly two for the GGUFs,
because the n-gram table is prepared into a 31 GB temp file first — that alone rules it out for wake-on-demand
(campaign O10). And **P-X5's attribution is still open:** Amendment 1 established that a 512-token ubatch is
5,120 token-expert pairs, past the int8 path's 2,048 limit, so prefill takes another path; the dispatch read on
09-13 says that is reconstruct-to-fp16 plus `cublasGemmEx` for dense matmuls, but the MoE case was not traced.
**Name the path before attributing the prefill gap to row scaling.**

---

## Addendum — Stage 3b, 15:52–15:58: buun's auto-fit works on Pascal, and lands within 9% of the hand-tuned placement

| arm | placement | GPU MiB after load | decode 500 / 1,800 / 3,600 | prefill 500 / 1,800 / 3,600 |
|---|---|---|---|---|
| **S3-FIT2** | `-fit on`, **no user `-ngl`** | [15147, 15191, 15245, 14993] = **60576** | 19.46 / 20.15 / 17.88 | 143.7 / 134.6 / 147.2 |

| id | prediction | result |
|---|---|---|
| P-S4b | `-fit on` loads on Pascal | **CONFIRMED** — the S3-FIT failure was the pinned `-ngl 99`, not the hardware |
| P-S5b | decode ≥ 1.2× P-IQ4 | **CONFIRMED** — 19.46 vs 11.63 tok/s = **1.67×** |
| P-S6b | within ±10% of the hand placement | **CONFIRMED** — 19.46 vs S3-X4's 21.28 = **-8.6%** |

**The fitter chose the right kind of spill by itself.** Its server log shows `tensor overrides to CPU are used with
mmap enabled`, so it spilled **experts**, not whole layers — the option Stage 1 measured as roughly seven times
cheaper per layer. It also logs `MoE cache fit kept stock placement: no selected device satisfies the cache hardware
policy`: buun's expert cache needs compute capability 7.0, so the P100s never get it.

**This bears on the fleet's `-fit off` habit.** With `-sm layer` pinned, `-fit on` is safe on `.194` and beats our
hand-set `-ngl 44` by **1.67×**, reaching within 9% of a placement we had to reason out from an 08-28
VRAM model. `CLAUDE.md`'s rule is about **row** splitting; it should not be read as "never let the fitter place
tensors". Changing that guidance is Mark's call.

**Ranking on `.194`, all measured today on one build, at the 500-token prompt:**

| configuration | GPU MiB | decode | note |
|---|---|---|---|
| UD-IQ4_XS `-ncmoe 2` | 61,566 | 21.28 | hand-placed, the fastest measured |
| UD-IQ4_XS `-fit on` | 60576 | 19.46 | chosen automatically |
| UD-Q2_K_XL fully resident | 50,190 | 21.05 | 3-bit-class fidelity |
| EXL3 3.05bpw | 50,060 | 18.41 | best fidelity per byte |
| UD-IQ4_XS `-ngl 44` | 57,138 | 11.63 | this morning's configuration |
