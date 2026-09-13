# Prereg — what is full residency worth for Flash-Next on `.194`, and can EXL3 get there at IQ4 quality?

**Written 2026-09-13 ~12:45, before any arm.** `.194` was powered on for this at ~12:15. The only things
run so far are orientation (disk, DIMM slots, tensor tables), sha256 of the weights, and the build.

Mark: *"EXL3 (at better performance) could be a big benefit for a big ass MoE like that on .194."*

## Three facts that make the question concrete

**1. turboderp's Flash-Next chart** (`turboderp/Qwen3.8-Flash-Next-exl3` model card). His method: a
self-generated in-domain trace of 14,496 input + 45,588 output tokens, mean KLD against the FP model,
x-axis in bits per weight *excluding embeddings and the output head*.

| quant | bpw (chart x-axis) | mean KLD |
|---|---|---|
| EXL3 2.05 H4 NG4 | 2.05 | 0.0684 |
| UD-IQ1_M | ~2.8 | 0.0804 |
| **EXL3 3.05 H5 NG5** | 3.05 | **0.0177** |
| **UD-Q2_K_XL** | ~3.1 | **0.0533** |
| UD-IQ3_XXS | ~3.3 | 0.0349 |
| **UD-IQ4_XS** | ~4.05 | **0.0165** |
| EXL3 4.05 H6 NG6 | 4.05 | 0.0067 |
| UD-Q4_K_XL | ~5.2 | 0.0084 |

At ~3 bpw EXL3 sits **3.0× closer to the reference than UD-Q2_K_XL**, and within 7% of UD-IQ4_XS.

**2. On this box, ~3 bpw is exactly the size that fits.** The n-gram table (`per_layer_token_embd`,
160 × 320,001,536, **IQ4_NL in all three UD quants**, 28.80 GB) is an input-layer tensor
(`LLM_TENSOR_LAYER_INPUT`) and stays on the CPU. EXL3's n-gram side file is CPU-decoded by design
(`8488d453e` touches no `ggml-cuda` file). What reaches the GPUs:

| file | on disk | n-gram table | ≈ for the GPUs | 4 × 16 GiB |
|---|---|---|---|---|
| UD-Q2_K_XL | 78.87 GB | 28.80 GB | ~50 GB | fits |
| EXL3 3.05bpw_h5_ng5 | 85.14 GB | 32.64 GB | ~50 GB, less bf16 embeddings and the vision tower | fits |
| UD-IQ4_XS | 93.68 GB | 28.80 GB | ~65 GB | **4 of 48 layers short** (measured 08-28) |

**If turboderp's chart holds, EXL3 3.05 is IQ4_XS-class fidelity at Q2_K_XL's footprint — resident here,
where IQ4_XS is not.**

**3. `.194`'s DIMM layout is already right for four sticks.** 4× Hynix **HMA42GR7MFR4N-TF** (16 GB 2Rx4
DDR4-2133 RDIMM) in P1_DIMMA1/B1 and P2_DIMME1/F1: two channels per socket, one DIMM per channel.
Four more in C1/D1/G1/H1 doubles the channels. **Whether Flash-Next would notice depends on how much of
its time is host-bound** — which the residency arms below measure.

## A mechanism question this test has to settle first

`RESULT_FLASHNEXT_PREFILL.md` (09-03) attributed the flat ~35 tok/s prefill to **streaming offloaded
experts from host RAM**. Set beside the 08-28 point, that attribution weakens:

| date | config | share of layer weights on the CPU | prefill |
|---|---|---|---|
| 08-28 | IQ4_XS, 4 GPUs, layer split, `-ngl 44` | 4 of 48 whole layers ≈ 8% | ~59 tok/s |
| 09-03 | Q2_K_XL, 2 GPUs, tensor split, `-ncmoe 30` | experts of 30 layers ≈ 58% | ~35 tok/s |

**About seven times the offloaded share cost only 1.7× in prefill.** A straight line through the two
points gives a host-independent floor near **15 ms/token (~67 tok/s)** and predicts that full residency
lifts the 08-28 configuration by only **~1.13×**. The two points also differ in quant, GPU count and split
mode, so this is an inference, not a measurement.

**The competing mechanism:** a 512-token ubatch spread across 512 experts at 10 per token gives each
expert matmul **~10 rows**, and sm_60 has no int8 dot-product instructions, so no MMQ — a matmul that
small runs far below what the card can do, wherever the weights live.

**Why this matters most for EXL3:** ~10 rows per expert is EXL3's measured weak regime — a 4-row batch
costs EXL3 **2.08×** a single row on Pascal, GGUF **1.37×** (`RESULT_EXL3_MTP_SWEEP.md`). If prefill is
kernel-bound, residency will not rescue it, and EXL3 will be slower at it than GGUF.

## Setup

- **`.194`**: 4× Tesla P100-PCIE-16GB (sm_60) at 150 W, application clock recorded; 2× Xeon E5-2650 v3,
  two NUMA nodes (distance 21 vs 10); 60 GiB as above; Samsung 860 SATA SSD.
- **Build: buun `c7f114d34`** (master, 2026-09-13), clean worktree `~/buun-c7f114d34` with an empty
  `git status`, `-DCMAKE_CUDA_ARCHITECTURES=60 -DCMAKE_CUDA_FLAGS=-allow-unsupported-compiler`, CUDA
  12.4, **no local patch**. One build for every arm of both stages. The driver aborts unless the build log
  ends `BUILD EXIT 0` and `llama-server --version` reports `c7f114d34`.
- **Weights verified against unsloth's published sha256** (`unsloth/Qwen3.8-Flash-Next-GGUF` LFS oids,
  in `published_sha256.json`) before first use. **No earlier verification record exists for these files.**
- **Flags, every arm:** `-c 4096 -np 1 -b 2048 -ub 512 -fa on --jinja -fit off -sm layer -ctk f16 -ctv f16`,
  `GGML_CUDA_ALLREDUCE=internal`. **KV is explicit**, because buun defaults to VBR; the driver aborts if
  the server log reports any other K/V type. `-c 4096` matches 08-28 and holds the longest prompt.
- **MTP off in every arm.** Speculation changes the batch shape per step, and EXL3's MTP asymmetry would
  confound Stage 2.
- **Page cache dropped before every arm** (`sudo -n`, NOPASSWD confirmed), so each arm starts equally
  cold and a NUMA arm cannot inherit the previous arm's placement — the DS4 re-baseline lesson.
- **Prompts:** wikitext token IDs, truncated to exactly **500 / 1,800 / 3,600** tokens and sent as IDs, so
  every arm sees byte-identical input (hash recorded per request). The file is the **`.73` copy, sha
  `173c87a5…`**, the one test 3 used; the control plane's `engines/wiki.test.raw` hashes to `d5558cd4…`, is
  a different file, and is not used. `cache_prompt: false`, temperature 0, `n_predict 128` with
  `ignore_eos`, 3 reps per length, one discarded warm-up, a fresh server per arm
  ([[server-uptime-is-a-variable]]).
- **Coherence gate per arm:** "17 × 23" must come back 391, or the run aborts.
- **Driver** `flashnext_residency.py`, one JSONL row per measurement, flush + fsync, resumable by arm.
  **Scorer** `tools/score_flashnext_residency.py`. Both committed with this prereg.

## Stage 1 — GGUF only, files already on disk

| arm | weights | placement | question |
|---|---|---|---|
| **B-\*** | — | STREAM-style triad (`membw.c`, written for this test): node 0 local, node 1 local, node 0 → node 1 remote, interleaved, first-touch across both | the host-bandwidth baseline a DIMM upgrade gets measured against |
| **F-Q2** | UD-Q2_K_XL | `-ngl 99` | fully resident |
| **P-Q2** | UD-Q2_K_XL | `-ngl 44` | 4 whole layers on the CPU — the same count as IQ4_XS on 08-28 |
| **X-Q2** | UD-Q2_K_XL | `-ngl 99 -ot "blk\.(44\|45\|46\|47)\.ffn_(up\|down\|gate)_exps=CPU"` | experts-only offload of the same 4 layers — and does `-ot` move them on this build? |
| **P-IQ4** | UD-IQ4_XS | `-ngl 44` | today's best-quality config; bridge to 08-28 |
| **P-IQ4-numa** | UD-IQ4_XS | `-ngl 44 --numa distribute` | the NUMA lever, where host RAM is in the loop |
| **P-IQ4-b** | UD-IQ4_XS | `-ngl 44` | drift control: P-IQ4 repeated after the NUMA arm |

**The X-Q2 regex is checked against the file,** not assumed: layers 44–47 carry
`blk.N.ffn_down_exps.weight` (IQ4_NL) and `ffn_gate_exps` / `ffn_up_exps` (IQ2_XS), 838,860,800 elements
each — **~3,650 MiB across the four layers.** Moved, the CUDA buffers shrink by about that; not moved,
by nothing.

**Fallback declared now:** if F-Q2 fails to load at `-ngl 99`, **F-IQ1** (UD-IQ1_S, 72.55 GB on disk,
~44 GB for the GPUs) replaces it, hash-verified on demand. P-R1–P-R3 are then scored against F-IQ1 and
labelled cross-quant.

### Predictions

| id | prediction | conf |
|---|---|---|
| P-R1 | **Residency buys decode:** F-Q2 decode (500-token prompt) ≥ 1.3× P-Q2 | 0.7 |
| P-R2 | **Residency does *not* buy prefill:** F-Q2 prefill at 1,800 tokens < 1.5× P-Q2 | 0.6 |
| P-R3 | F-Q2 prefill is **flat**: at 3,600 tokens within 20% of its value at 500 | 0.6 |
| P-R4 | **Bridge:** P-IQ4 decode within ±15% of the 08-28 receipt's ~9.0 tok/s | 0.7 |
| P-R5 | `--numa distribute` lifts P-IQ4 decode ≥ 3% over the mean of P-IQ4 and P-IQ4-b — **INCONCLUSIVE** if those two differ by more than the effect | 0.5 |
| P-R6 | **`-ot` moves experts on this build:** X-Q2's summed CUDA model buffers are ≥ 2,000 MiB smaller than F-Q2's | 0.8 |
| P-BW1 | Each socket's local triad lands between 50% and 80% of the two-channel theoretical 34.1 GB/s | 0.7 |
| P-BW2 | Remote (node 0 → node 1 memory) ≤ 0.7× node-0 local | 0.8 |
| P-BW3 | First-touch across both sockets ≥ 1.7× the single-socket local mean | 0.7 |

**P-R2 contradicts our own 09-03 receipt on purpose.** If it is falsified — especially at ≥ 3× — host
streaming was the dominant prefill cost after all, the 09-03 attribution stands, and full residency is
worth far more than this prereg expects.

**P-R6's history.** `-ot` "had no effect" on 08-28, on Tom's `d74823a0c`, and one of the four rows behind
that was a no-op by design (see the note added to `RESULT_FLASHNEXT_PASCAL.md`). Meanwhile `--n-cpu-moe`
is implemented as `llm_add_n_cpu_ffn_overrides(value, LLM_FFN_EXPS_REGEX, params.tensor_buft_overrides)`
— the same list `-ot` fills — and the 09-03 runs on buun's `7a918624b` fitted a 74 GB model on two 16 GB
cards with `-ncmoe 30`, which is impossible unless it placed experts on the CPU. **So override-based
placement has already worked on buun's tree once**; the 08-28 failure may be that build, or that regex.

## Stage 2 — EXL3 3.05bpw_h5_ng5, fully resident (gated)

**Not runnable today.** `.194` has **39 GB free**; the branch is **85.14 GB**. Mark decides what to free,
and **`flashnext_iq1s` is not a candidate until Stage 1 finishes**, because it is Stage 1's fallback.
Download via `tools/hf_fetch.py`, pinned to a revision, every file verified against the published sums.
Same build, flags and prompts; `-sm layer`, since `32c2c1479` rejects multi-device EXL3 tensor split.

| id | prediction | conf |
|---|---|---|
| P-X1 | Loads and answers coherently on sm_60 (buun developed Qwen4 EXL3 on sm_86) | 0.6 |
| P-X2 | All 48 layers resident on the 4 cards; nothing but the n-gram table on the CPU | 0.8 |
| P-X3 | **The practical win:** decode ≥ P-IQ4's — IQ4-class fidelity, faster than today's IQ4 configuration | 0.65 |
| P-X4 | Decode ≤ F-Q2's — same footprint, and EXL3 pays its kernel cost | 0.75 |
| P-X5 | **The MoE-fragmentation cost:** prefill ≤ 0.75× F-Q2's, because ~10 rows per expert is EXL3's weak regime | 0.6 |

## Declared in advance

- **This test measures speed and placement, not quality.** Quality comes from turboderp's chart, and
  **he is EXL3's author** — an interested party using his own method. Our independent 27B measurement
  found a much smaller EXL3 advantage: **1.3× lower KLD at ~4 bpw, against his 2.5× on Flash-Next.**
  Either MoE experts genuinely favour trellis quantization, or the methods differ; this test cannot tell.
- **We cannot replicate his KLD here.** A Q8_0 reference of a 180B model is ~190 GB — more than `.194`'s
  combined 60 GiB + 64 GiB and more than its free disk. **A paired task benchmark is the only independent
  quality instrument available** — test 11's design, and a separate prereg.
- **The x-axis caveat on his chart:** "excluding embeddings" hides that EXL3 3.05 carries its n-gram
  table at 5 bits (32.64 GB) where unsloth uses 4.5-bit IQ4_NL (28.80 GB). That table lives in host RAM,
  so it does not change the VRAM comparison — but it is fidelity spent off-axis.
- **Layer split is pipelined:** at `-np 1` one card works at a time. These are single-user numbers.
- **One prompt source, one context length, one GGUF packager** (unsloth UD).
- **Runtime:** Stage 1 ≈ 1.5 h, about 13 minutes per arm, mostly cold loads from SATA. `.194` idles at 218 W.
