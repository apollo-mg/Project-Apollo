# What gfx1201 actually launches — and why nobody has RDNA turbo prefill numbers

**2026-08-18**, RX 9070 XT (gfx1201, RDNA4), ROCm 7.2.4.
Builds `fca3093c9` (pre-#295) and `f6124e914` (#295 merge), plus `f050a2501` (tq295) as a
same-build control. Scripts `kernel_census.sh`, `pf.sh`, `thr.sh`.

## 1. Decode launches ncols=1. Never ncols=2.

`TheTom` in #294: *"`ncols=2` is a shape decode really launches, so a residual there sits on a
live path, unlike the D=256 one which is a V-side accumulator spill on a shape nothing
launches."*

That is an assumption about which template instances reach the GPU, and it is checkable from
outside the build. There is no `rocprof` here, but `AMD_LOG_LEVEL=4` prints every dispatch's
`ShaderName` **including template arguments**.

ggml_type numbering (fork `ggml.h`): `1=F16 2=Q4_0 8=Q8_0 43=TURBO2_0 44=TURBO3_0 47=TURBO4_0`.

| config | kernel launched | count |
|---|---|---:|
| D=128, GQA **3:1**, decode | `flash_attn_ext_vec<128, 1, TURBO3, Q8_0>` | 84 |
| D=256, GQA **4:1**, decode | `flash_attn_ext_vec<256, 1, TURBO3, Q8_0>` | 40 |
| D=256, GQA **6:1**, decode | `flash_attn_ext_vec<256, 1, TURBO3, Q8_0>` | 80 |
| D=128, decode @ depth 4096 | `flash_attn_ext_vec<128, 1, TURBO3, Q8_0>` | 112 |
| D=128, turbo3 symmetric | `flash_attn_ext_vec<128, 1, TURBO3, TURBO3>` | 84 |

**Every decode configuration launches `ncols=1`.** Three GQA ratios and two head dims, and
the packing factor never moves the VEC `ncols`. Depth changes the launch *count* (84 → 112)
and not the shape, which is the control behaving as it should.

**Consequence for #294:** on gfx1201, plain decode does **not** launch the `<128,2,…>` class.
Whatever reaches `ncols=2` here, ordinary token generation at these GQA ratios is not it. That
*strengthens* the case for putting the surviving shapes on the ignore list rather than
weakening it — but it also means the premise "a residual there sits on a live path" should be
re-checked on the arch it is being argued about.

**Not established:** what *does* launch `ncols=2`. Speculative decoding and multi-sequence
batching both raise `Q->ne[1]` and are the obvious candidates; `llama-bench` cannot produce
either, and the D=128 model here has no draft head.

## 2. `llama-bench` cannot prefill with quantized KV on gfx1201

Discovered while trying to add a prefill regime. **Same build**, `llama-bench` versus
`llama-server`:

| path | config | result |
|---|---|---|
| `llama-bench` | `-p 256 -n 0`, any quantized KV | **ROCm error → abort** (`ggml-cuda.cu:109`) |
| `llama-server` | ~2000-token prompt, `turbo3`/`q8_0` | **fine**, coherent output |

The threshold is exact and matches the fork's own HIP branch in
`ggml_cuda_get_best_fattn_kernel`, which routes `Q->ne[1] <= 8` to VEC and everything larger
to TILE/MMA:

| `llama-bench` arg | result |
|---|---|
| `-p 4` | ok |
| `-p 8` | **ok** |
| `-p 9` | **ABORT** |
| `-p 256 -ub 16` | ABORT |
| `-p 256 -ub 8 -b 8` | **ok** — 331.6 t/s |

Every quantized pair aborts (`turbo3/q8_0`, `turbo3/turbo3`, `q8_0/q8_0`, `turbo4/q8_0`,
`turbo2/q8_0`); only `f16/f16` prefills (1639 t/s).

**Pre-existing** — `fca3093c9` aborts identically, so #295 neither caused nor fixed it.

**Why it matters:** `llama-bench` is how turbo codecs get measured. On RDNA4 it cannot produce
a prefill number for *any* quantized KV type. That is a plausible reason the runtime evidence
TheTom wants from an RDNA part does not exist — the standard tool refuses. Workaround for
anyone who needs it: `-ub 8 -b 8`.

**Corrected on the way to this.** The first framing was "prefill with quantized KV aborts on
RDNA4." **That is wrong** — serving handles a 2000-token prompt fine. It is the benchmark
path only. The two were also initially compared across *different builds*; re-tested within
one build before recording.

## What this does NOT establish

- **Not a serving bug.** `llama-server` is unaffected at any prompt length tested.
- **Not root-caused.** `ggml-cuda.cu:109` is the generic `ggml_cuda_error` handler; the
  underlying `hipError` string is swallowed by `llama-bench`'s log callback and was not
  recovered.
- **Not upstream-compared.** No upstream HIP build on this box, so whether stock `llama.cpp`
  shows the same is untested.
- **Launch identity, not timing.** `AMD_LOG_LEVEL=4` gives kernel names and counts. It is not
  a profiler; nothing here measures per-kernel time.
