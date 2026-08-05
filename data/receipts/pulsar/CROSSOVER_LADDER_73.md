# Crossover ladder: pulsar vs llama.cpp (stock + turboquant) — no crossover found

**Question:** at what model:VRAM ratio does pulsar's NVMe expert streaming overtake llama.cpp's
layer offload? **Answer on this rig: it doesn't.** llama.cpp wins at every ratio tested, by a
strikingly constant ~3×.

Date 2026-08-03. Node `.73`: 2× Tesla P100-PCIE-16GB (**31.77 GiB usable**), i5-8600K, **15 GB RAM**,
models on Intel Optane H10 QLC, **PCIe 3.0 ×2, 1.1 GB/s sequential, 92% full**.
Prompt `"The three most important inventions of the twentieth century were"`, n=64, temp 0.

## Result

Three engines, identical rig / prompt / n=64 / temp 0.

| rung | model | size | ×VRAM | **stock b10154** | **turboquant d0e2a8b64** | **pulsar** |
|---|---|---|---|---|---|---|
| A | Hermes3.6-35B-A3B APEX | 23.93 GiB | 0.75× | **39.86** | 39.36 | 13.18 / 13.20 |
| B | Laguna-S-2.1 UD-IQ2_XXS | 34.64 GiB | 1.09× | 8.55 ¹ | **8.72** | 1.65 / 2.35 |
| C | Laguna-S-2.1 UD-IQ4_NL | 54.70 GiB | 1.72× | 2.44 ¹ | **2.91** | 0.85 / 0.82 |

¹ stock **cannot run Laguna with flash attention at all** on sm_60 — it crashes on the first
decode (see below). Those two figures required `-fa off`. The turboquant column ran with FA **on**.

**llama.cpp wins every rung by ~3×** (best-llama.cpp ÷ pulsar: 3.02× / 3.71× / 3.55×).
No crossover exists anywhere in 0.75×–1.72× on this hardware.

**turboquant vs stock:** 0.987× / 1.020× / 1.193×. A dead heat where the model fits, pulling
ahead as it overflows — but note rungs B and C are not like-for-like, since stock is handicapped
to `-fa off` there. The +19% at rung C is the only gap outside noise.

pulsar's VRAM-cache hit rate falls with size as expected: A 84%, B 58→71%, C 38→46%. Both pulsar
runs are shown (its `bench.sh` protocol reports the second warm run).

## ⚠️ Prediction FALSIFIED — logged before the run

> "Pulsar loses at 0.80× almost certainly … It should win somewhere past 1×, because llama.cpp's
> offloaded experts hit the same slow disk-and-RAM path without a popularity census to exploit."

Wrong. The gap did not close at 1.09× or 1.72× — it stayed near 3× throughout. The census does
not compensate; llama.cpp's mmap + OS page cache handles the overflow better than pulsar's
tiering does **on this hardware**.

## The comparison is not VRAM-symmetric — state this with any quote

llama.cpp used **both** cards (31.77 GiB). pulsar used **one** (15.89 GiB), because its multi-GPU
path is a 75× regression on this node (remote-tier peer reads over `PHB`, no NVLink — see
`../../Apollo Docs/Pulsar_Engine_Findings.md`). So per *engine-usable* VRAM the rungs are really
1.50× / 2.18× / 3.44× for pulsar against 0.75× / 1.09× / 1.72× for llama.cpp.

This is each engine **at its best on this box**, which is the practical question. It is *not*
"same hardware, same memory budget". A pulsar build without the peer-read defect would get a
second card and a materially different result.

## Where this does and does not generalise

**Does not:** `.73` is close to a worst-case host for a streaming engine — 15 GB RAM (the host
tier that absorbs VRAM misses) and a QLC drive at 1.1 GB/s sequential, 92% full, on PCIe 3.0 ×2.
The author's reference box is 30 GB RAM and one Gen5 NVMe; his published Laguna figure is
17.3 tok/s on IQ2_XXS. **This receipt does not claim pulsar is slower than llama.cpp in general.**

**Does:** on hardware like this — old cards, little RAM, a slow full disk — the streaming approach
has no advantage at any size we can hold, and the answer to "should I use it instead of llama.cpp"
is no, up to 1.72×.

## Bug found: STOCK llama.cpp cannot run Laguna on sm_60 with flash attention — the fork can

Stock b10154 (`0e4a03622`), both Laguna quants, first decode step:

```
ggml-cuda.cu:106: CUDA error
CUDA error: invalid argument
  in function ggml_cuda_kernel_launch at common.cuh:1659
  cudaGetLastError()
#8  ggml_cuda_flash_attn_ext_tile_case<128, 128>(ggml_backend_cuda_context&, ggml_tensor*)
```

- Loads fine; fails on the **first kernel launch of the first decode**.
- **Model-specific, not build-specific:** the same binary ran Hermes with FA at 39.86 tok/s
  minutes earlier.
- **Quant-independent:** identical on UD-IQ2_XXS and UD-IQ4_NL.
- `-fa off` clears it completely — 8.55 tok/s, 0 CUDA errors, coherent output.
- ⚠️ **Corrected mid-investigation:** first read as the PDL (`cudaLaunchKernelEx`, Hopper-only)
  path. Wrong — PDL is compiled in (302 symbols) but `GGML_CUDA_PDL=0` changes nothing, and the
  failing check reports `cudaGetLastError()`, i.e. the plain-launch path. It is a launch-config
  rejection on the FA tile kernel, cause not yet identified.

### The fork does NOT reproduce it

`TheTom/llama-cpp-turboquant` @ `d0e2a8b64` (post-#254, upstream base **10281**), same cards, same
model, FA **on**, `-c 1024`: **8.72 tok/s, 0 CUDA errors, coherent output.** Both Laguna quants.

**Cause not established.** Two hypotheses were formed and both are dead:

1. ~~PDL (`cudaLaunchKernelEx`, Hopper-only) misfiring on Pascal~~ — PDL is compiled in (302
   symbols) but `GGML_CUDA_PDL=0` changes nothing, and the failing check is `cudaGetLastError()`,
   i.e. the plain-launch path.
2. ~~Tom's `f924ee29f` "laguna: … CUDA GQA ratio fix" (modulo dispatch for ratios 6 and 9)~~ —
   that patch is in the **MMA** selector, and every MMA gate in `fattn.cu` is
   `cc >= GGML_CUDA_CC_TURING` or higher. **Pascal never reaches the MMA path**, which is
   consistent with the crash being in `flash_attn_ext_tile_case`.

What is established: **stock 10154 crashes, fork 10281 does not.** The delta could be an upstream
fix landing in 10155–10281 or something fork-original; a bisect is required and has not been run.

⚠️ **Do not report this upstream yet** — no minimal repro, no named parameter, and the fix may
already exist upstream past 10154. Next step is bisecting b10154→b10281 on the Laguna load.

## Limits

- One prompt, one length (n=64), one run per llama.cpp cell (pulsar got 2 per its protocol).
- llama.cpp auto-fits layers (`-ngl` unset); no manual `-ncmoe` tuning was attempted, which might
  improve its numbers further.
- Disk was at **92%** — the earlier Hermes measurements in `Pulsar_Engine_Findings.md` were taken
  at 77–89%. QLC degrades when full; pulsar is the engine that cares.

## Provenance

`.73:~/ladder/` — `ladder.log`, `rungC.log`, `resp_*.json`, `srv_*.log`; scripts `~/ladder.sh`, `~/rungC.sh`
