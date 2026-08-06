# Pulsar engine on the P100 fleet — findings, knobs, and what NOT to re-derive

**Author:** Claude (Architect). **Date:** 2026-08-02. **Node:** `.73` (2× Tesla P100, sm_60).
**Upstream:** `github.com/giannisanni/pulsar` — third-party, MIT-adjacent, not ours.
Successor to `giannisanni/neutronstar`. Rust + CUDA MoE inference engine, ~29,100 lines,
own GGUF parser / tokenizer / quantizer / kernels. **No llama.cpp in the stack.**

> **Read this file before touching pulsar.** Every mechanism below cost source-diving to
> establish. Re-deriving them by `cat`/`grep` over SSH against an 8,044-line `lib.rs` is
> what produced the 2026-08-02 context blowout. See `GEMINI.md` → *Orientation Budget* and
> *Read Local, Not Over SSH*.

## Where the code is

| copy | path | note |
|---|---|---|
| local (authoritative) | `~/.gemini/antigravity-cli/brain/902930f2-…/scratch/pulsar` | edits were authored here, then `scp`'d to `.73` |
| remote | `.73:~/pulsar` | build tree; `target/release/pulsar-cli` |

Both at git `a7fc493` **plus 5 uncommitted files** — the sm_60 port (see CHANGELOG
`[Unreleased]`, Antigravity+Mark). Verified present on `.73` and the binary
(`21:50:43`) postdates both edited sources, so the numbers below came from the ported build.

## The sm_60 port, and why it matters

`crates/kernels/build.rs:7` states the floor plainly: **"the floor is dp4a = sm_61"**.
P100 is sm_60 and lacks the instruction. The port is:

- `build.rs` → `let archs = vec!["60".to_string()]`
- `pulsar_kernels.cu:20` → software `__dp4a` under `#if __CUDA_ARCH__ < 610`
- `lib.rs`, `quant/{cpu_dot,lib}.rs` → inlined `Q6_K` dequant path

**[O]** The `__dp4a` polyfill is a faithful scalar expansion — four int8 products, correct
sign extension, integer accumulate. Exact vs hardware dp4a, not approximate.
**[I]** It replaces one instruction with ~8 in the innermost loop of every quantized dot
product; plausible contributor to decode cost, not isolated by any A/B run here.

⚠️ **We are running below the project's supported floor.** Nothing upstream tests sm_60.

## Measured on `.73` — cold vs warm census

Protocol note: `scripts/bench.sh` requires a **warm census, n=64, second warm run**. A run
against a fresh `.warm` file is explicitly *not* a benchmark. Neither number below is a
canonical `bench.sh` figure; both are `pulsar-cli` direct invocations.

### Hermes3.6-35B-A3B-Uncensored-Genesis-V6-APEX — 25.69 GB (23.93 GiB), 40 layers, 256 exp × top-8

**Update (2026-08-03):** always run this node with `CUDA_VISIBLE_DEVICES=0`. The auto dual-GPU
split strands the expert tier on device 1 and turns every expert access into a fine-grained PCIe
peer read — **up to 75× slower**, deterministic, and *not* corruption. See the multi-GPU section
below for the mechanism, the A/B, and the retraction of the earlier "P2P corruption" claim.
⚠️ The dual-GPU rows in the table below vary by tier placement; read the `expert tier on CUDA
device N` line before comparing any two of them.

| | dual-GPU cold, n=15 | dual-GPU warm, n=64 | single-GPU warm, n=15 | single-GPU warm, n=64 |
|---|---|---|---|---|
| decode | 5.88 tok/s | 6.75 tok/s | 16.73 tok/s | **12.40 / 13.42 tok/s** |
| prefill (5 tok) | 1.89 s | 0.18 s | 0.30 s | 0.45 s |
| VRAM cache hits | 60% | 73% | 88% | 85–88% |
| host cache | 0% of rem. | 0% of rem. | 100% of rem. | 87–88% of rem. |
| tier | dev 0, 8.8 GiB | dev 1, 4.5 GiB | dev 0 only | dev 0 only |

⚠️ Two single-GPU n=64 figures: **12.40** via `bench.sh` (canonical) and **13.42** from a direct
`pulsar-cli` invocation. Prefer the `bench.sh` number in any published comparison. Shorter runs
read high — the 16.73 at n=15 is the documented n-effect, not a better configuration.

### Laguna-S-2.1-UD-IQ4_NL (3 shards) — 58.75 GB (54.71 GiB), 48 layers, 256 exp × top-10

| | cold, n=60 | warm, n=64, temp 0 |
|---|---|---|
| decode | 0.63 tok/s | **3.60 tok/s** |
| prefill (16 tok) | 18.90 s | **5.09 s** |
| VRAM cache hits | 44% | 40% |
| host cache | 31% of remainder | 39% of remainder |
| tier | *idle — no census* | dev 1, 3469 triples, 14.6 GiB |
| resident slots | — | 30,744 |

⚠️ n differs between the Laguna arms (60 vs 64); not a matched pair.

**[O]** Warming is worth +15% decode on Hermes and **5.7×** on Laguna.
**[I]** The census pays in proportion to how much of the model does *not* fit — Hermes is
73% resident, Laguna is not. Mechanism: tier ranking from the `.warm` popularity file.
Confound not excluded: consecutive runs keep warming (bench.sh documents 2.56 → 2.83 tok/s
on GLM-5.2 from an unchanged binary), so single-run deltas overstate.

**Not comparable to the README table.** His Laguna figure (17.3 tok/s, 22.4 w/ CPU lane) is
**IQ2_XXS at 36 GB** on 2× consumer 16 GB cards; ours is 1.63× that file size on P100s.
A matched point needs IQ2_XXS, and `/mnt/models` has only ~27 GB free.

## `.73` is a poor host for this design — quantify before blaming the engine

- **Disk:** `/mnt/models` = `/dev/nvme1n1p1`, Intel HBRPEKNX0202AH (Optane H10), **PCIe 3.0 ×2**
  (`8.0 GT/s`, width `2`), **1.1 GB/s sequential** (`dd bs=1M iflag=direct`), 236 G at **89% full**.
  Expert slabs are scattered random reads — the real floor is worse than the sequential figure.
- **RAM:** 15 GB total, ~11 available. Reference box has 30 GB. Host cache read **0%** on both
  Hermes runs: every VRAM miss went to disk.
- **Compute:** sm_60, dp4a emulated, `--use_fast_math` global.

**[U]** No isolation run attributes decode cost among {disk, host cache, dp4a, P100 bandwidth}.
Do not rank these without an A/B.

## 🔑 Multi-GPU is 75× slower — remote-tier peer reads, no NVLink. ALWAYS use `CUDA_VISIBLE_DEVICES=0`

**[O] Alternating A/B, n=32, `--ctx 512`, 25 s settle between runs, same binary/prompt/census:**

| run | tok/s | wall (32 tok) | VRAM hits | host, of rem. | tier placement |
|---|---|---|---|---|---|
| A dual r1 | **0.17** | 190.79 s | **98%** | 0% | dev 1, 6788 triples, 14.6 GiB |
| B single r1 | **12.79** | 2.50 s | 83% | 92% | none (all local) |
| A dual r2 | **0.17** | 190.79 s | **98%** | 0% | dev 1, 6790 triples, 14.6 GiB |
| B single r2 | **12.87** | 2.49 s | 83% | 93% | none (all local) |

**190.79 s twice, to the hundredth — deterministic, not noisy.** 75×.

### The mechanism

**98% VRAM hits at 0.17 tok/s** rules out both corruption and cache thrash: the slow arm has a
*better* hit rate than the fast one. Compute runs on device 0 (`using CUDA device 0`), the tier
lands on **device 1**, and peer access is enabled (`crates/kernels/src/lib.rs:325`,
`cudaDeviceCanAccessPeer` → `cudaDeviceEnablePeerAccess`). Kernels therefore dereference
pointers into the *other card's* VRAM. That still counts as a "VRAM hit" — the slab is resident,
just on the wrong GPU — while every access becomes a fine-grained PCIe round trip across `PHB`
instead of a local HBM read.

**[O] The cards are `Tesla P100-PCIE-16GB` — no NVLink** (that is the SXM2 variant). Fine-grained
peer reads are precisely the traffic NVLink exists to carry.

**[O] Monotonic in how much of the working set is stranded remotely:**

| tier placement | remote bytes | tok/s |
|---|---|---|
| device 0 (local) | 0 | 5.88 |
| device 1 | 4.5 GiB | 6.75 |
| device 1 | 14.6 GiB | **0.17** |
| single-GPU | none | 12.8–13.5 |

⚠️ **RETRACTED — "`.73` is bistable here."** An earlier reading of this called the spread
(0.17 / 6.75 / 8.69) run-to-run flakiness, by analogy to the HA-04 35/100/100/35 result. Wrong:
those runs differed in **tier placement**, a variable printed in every log and not controlled for.
With placement held constant the result repeats to four significant figures. Read the
`expert tier on CUDA device N: … GiB` line before comparing any two pulsar runs.

⚠️ **`.194` is a worse case, not a better one.** `nvidia-smi topo -m` there: GPU0↔GPU1 `PHB`
(socket 0), GPU2↔GPU3 `PHB` (socket 1), and **every 0/1↔2/3 pair is `SYS`** — across QPI between
sockets (19.2 GB/s/direction, node distance 21 vs 10). Four cards do **not** give this engine
64 GB of usable VRAM; a tier landing across a socket boundary would be worse than the 0.17
measured here. On `.194` the value is the **host cache**, not aggregate VRAM.

### ⚠️ CORRECTED 2026-08-03 — the "P2P corruption" mechanism is FALSIFIED

An earlier revision of this section claimed P2P "silently fails or drops bits", delivering
"garbage zero-tensors" that corrupt logits and force a degenerate repetition loop, collapsing
cache locality to <46% and 0.17 tok/s. **Tested and refuted:**

- The single-GPU run — where no P2P transfer occurs at all — produces the **identical**
  degenerate repetition: `Paris.\nThe capital of France is Paris.\n…` at 13.42 tok/s with
  **88% VRAM hits**. Repetition coexists with excellent locality on one card.
- The repetition is what a **raw completion at `--temp 0` with no chat template** does on
  `-p "The capital of France is"`. It is not a numerics signal, and pulsar's own
  `scripts/bench.sh` uses a similarly open prompt.
- The cold dual-GPU Hermes run placed its tier on **device 0** and repeated anyway; the warm run
  placed it on device 1 and repeated identically. Repetition does not track P2P involvement.
- The quoted collapse figures do not match anything measured here: our dual-GPU runs were
  **60% / 73%** hits at **5.88 / 6.75 tok/s**, not <46% at 0.17.
- The dual-GPU Laguna run fetched experts from a **14.6 GiB tier on device 1** and produced a
  correct, coherent explanation of MoE architecture. Bit-dropping P2P cannot yield that.

**[I]** Slower, not broken: cross-bridge fetch latency over `PHB`, plus a smaller effective
resident set when the tier is split. No corruption is in evidence.

⚠️ **Do not cite a corruption bug on this hardware.** If you want to establish one, the test is
`--teacher-force` logit agreement between the one-GPU and two-GPU paths (see correctness gap
below) — not the shape of greedy text.

## Knobs — and the big trap

### ⚠️ `PULSAR_SPLIT` does nothing for a MoE

`crates/engine/src/lib.rs:2951` —

```rust
let qwen35_dense = shape.family == Family::Qwen35 && shape.n_expert == 1;
if qwen35_dense && kernels::device_count() > 1 && PULSAR_SPLIT != "off" { … }
```

It is the **dense** whole-layer-ownership path (the ThinkingCap-27B mode). Laguna logs
`256 experts x top-10`, so `n_expert == 1` fails and the block never executes.
**This is the question that triggered the 2026-08-02 loop. It is now answered.**

### What actually moves a streaming MoE

| var | effect |
|---|---|
| `PULSAR_CACHE_GB` | host cache size — the lever RAM starves on `.73` |
| `PULSAR_DEV_CACHE_GB` | device cache; CLI force-sets `2` only when prompt > 384 tokens |
| `PULSAR_ATTN_VRAM_GB` | caps resident attention stack. Defaults per family (`lib.rs:3201`): `Mla` 6 GB, `Dsv4` 8 GB, `Gqa`/`Qwen35` unbounded. **[U] Laguna's `Family` was NOT established this session** — `grep -rn "laguna" crates/engine/src/` before assuming which default applies, or you will tune against the wrong branch |
| `PULSAR_GPU` | primary device index |
| `PULSAR_CPU_B` / `PULSAR_CPU_CAP` / `PULSAR_CPU_STEAL` | CPU lane. README shows Laguna 17.3 → 22.4 with it — but on a 9900X; `.73`'s 8600K + 15 GB will give back far less |
| `PULSAR_KV=5` | q4_0 KV, opt-in — frees device 0 for more tier |
| `PULSAR_TIERS=off` | disables tiers; restores bit-exact float ordering (tiers reorder adds — documented drift class) |
| `PULSAR_MTP` / `PULSAR_MTP_DEPTH` | speculative decode off the model's own nextn head |

Full list: `grep -rohE 'PULSAR_[A-Z0-9_]+' crates/ | sort -u` (~88 vars).

## The correctness gap — the highest-value open item

`scripts/check.sh` gates on: kernel selftests, `tokenizer`/`gguf`/`stream` unit tests, a
census-ratchet regression, and **decode-vs-fresh-prefill bit-exactness** — that last one is
*self*-consistency. `crates/tokenizer/tests/hy3_parity.rs` is token-stream parity against
**ds4**, pulsar's own ancestor. Every llama.cpp mention in the tree is source-reading to port
a graph, not a numerical comparison.

**There is no external numerics gate.** But the instrument already exists:

```
--teacher-force   per-position top-5 (id, logit) along a given token sequence,
                  one JSON line per position, "for cross-engine agreement checks"
--dump-logits
```

**Proposed leg (not run):** teacher-force an identical token sequence through pulsar and
llama.cpp on the same GGUF, compare top-5 / KLD. Run it on **sm_60 first** — that is the path
below the supported floor, and it is the exact shape of the FAST_FP16 defect this fleet already
confirmed (median KLD 0.0023 → 0.000001, same-top 96.5% → 99.9%). Either outcome is publishable:
pulsar's first external numerics receipt, or a second Pascal silent-corruption finding.

## Ruled out / known

- `-sm`-style split modes are a **llama.cpp** concept; pulsar has its own placement model. Do not
  transfer conclusions from `APEX_IMINI_2xP100_NOFIT.md` between engines.
- Pulsar streams experts rather than partitioning them, so it sidesteps the DS4 tensor-split wall
  we hit in llama.cpp (`ce3dce77b`, then the `ggml-backend-meta.cpp:730` assert). `crates/engine/src/real/dsv4.rs`
  exists; README claims 284B at 87 GB / 8.2 tok/s. **Untested by us.**
- Degenerate repetition on `-p "The capital of France is" --temp 0` is expected for a raw
  completion with no chat template. Not a defect signal.

## Open

1. Matched Laguna point vs the README (needs IQ2_XXS 36 GB; needs disk cleared).
2. Cross-engine numerics panel via `--teacher-force` (above).
3. Whether host cache reading 0% on Hermes is config or a population bug.
4. ~~CPU-lane gain on an 8600K.~~ **[Resolved]** `PULSAR_CPU_B=1` yields exactly 0.01 tok/s difference on Hermes. The 85% VRAM cache hit rate on a single GPU completely nullifies the PCIe transfer bottleneck the CPU lane is designed to solve.
5. ~~Canonical `bench.sh` figures — nothing here used the project's own harness.~~ **[Resolved]** Single-GPU canonical baseline for Hermes 35B is **12.40 tok/s**.

## Provenance

All measurements this session, direct `pulsar-cli` runs on `.73`, quoted from tool output in
the Claude transcript of 2026-08-02. Disk/RAM figures from `df`/`findmnt`/`free`/`dd`/sysfs on
`.73`. Source line numbers against local scratch copy at `a7fc493` + 5 uncommitted files.
