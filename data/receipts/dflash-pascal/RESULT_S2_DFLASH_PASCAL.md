# DFlash's depth advantage does not survive on Pascal — the curve inverts

**2026-08-18**, `.73`, dual Tesla P100 (sm_60), **150 W cap, clocks pinned 1063 MHz** (fleet
`p100-efficiency.service`, unchanged throughout — every power sample read `1063-1063 MHz`).
`moe-cache-test` `bb3c3fa` built for CUDA sm_60. Target `Qwen3.5-9B-Q8_0` (unsloth MTP
variant), DFlash draft `Qwen3.5-9B-DFlash.Q8_0` (1.3 GB), `-ngl 99 -c 8192 --jinja`,
12 prompts × 2 reps. Raw `s2.log`, `s2bc.log`, script `dflash_p100.sh`.

Closes `BACKLOG S2`. Direct port of the RX 9070 XT drafter showdown — same target file, same
prompt set, same `n_max` sweep — so the two are comparable.

## Result

| n | MTP t/s | DFlash t/s | MTP acc | DFlash acc | | 9070 XT MTP | 9070 XT DFlash |
|---|---:|---:|---:|---:|---|---:|---:|
| off | 28.87 | 28.87 | — | — | | 55.27 | 55.27 |
| 3 | 51.31 | **52.28** | 76.81 % | 76.74 % | | 107.95 | 116.68 |
| 7 | 41.75 | **46.50** | 53.67 % | 53.85 % | | 104.53 | 140.03 |
| 15 | 14.65 | *OOM* † | 29.18 % | — | | 76.35 | **150.66** |

† see "The OOM is itself the finding" below.

**On RDNA4 DFlash climbs monotonically and peaks at its deepest setting. On Pascal both
drafters peak at n=3 and fall away.** At n=15 MTP is **slower than not speculating at all**
(14.65 vs 28.87). DFlash decays more gracefully than MTP (+11 % at n=7) but the *"depth is
nearly free"* property that made it win on RDNA4 is absent here.

**Practical consequence: the `--spec-draft-n-max` advice from the 9070 XT run does not
transfer.** Raising the flag is worth +26-29 % there and is a large loss on Pascal. One
default cannot serve both drafters *or* both architectures.

## The control validates the port

Acceptance is a property of the drafter and the prompts, not the hardware, so it should match
across machines. It does, at every depth:

| n | MTP Δ | DFlash Δ |
|---|---|---|
| 3 | 76.81 vs 77.49 % → **0.68 pp** | 76.74 vs 76.79 % → **0.05 pp** |
| 7 | 53.67 vs 53.15 % → **0.52 pp** | 53.85 vs 52.86 % → **0.99 pp** |
| 15 | 29.18 vs 29.03 % → **0.15 pp** | — |

`P5` confirmed at conf 0.85. Every throughput difference above is hardware, not drafting.

## Power: the cap never bound, the clock pin always did

| arm | busy W | peak W | clock |
|---|---:|---:|---|
| off | 75.3 | 104.5 | 1063 |
| mtp_n3 | 88.5 | 120.8 | 1063 |
| mtp_n7 | **91.7** | 129.0 | 1063 |
| mtp_n15 | **58.8** | 123.0 | 1063 |
| dfl_n3 | 86.7 | 119.5 | 1063 |
| dfl_n7 | 89.8 | **130.2** | 1063 |

Against a **150 W** cap: 61 % sustained at worst, 87 % at the single worst instant. **The
power limit never throttled anything.** The `-ac 715,1063` clock pin, however, was active in
every sample — stock boost is 1328 MHz, so **every number here is at ~80 % clock**.

**Comparability caveat (raised by Mark, and it is correct):** the 9070 XT ran at stock
clocks; these ran capped. So *"P100 is 52 % of the 9070 XT"* conflates hardware with our own
efficiency config, and the absolute cross-machine ratio should not be quoted without it.
**Within S2 nothing is affected** — both drafters, all depths, identical clock — so the curve
inversion and the DFlash-vs-MTP comparison stand as measured.

**This also answers whether the efficiency chart transfers.** It was derived from
*"+25 % decode tok/J at 84 % speed"* on plain decode. Speculation raises draw by ~17 % at
n=3-7 and still lands 40 % below the cap, so **`-pl 150` is not the operative constraint in
either regime.** If we want to know what the config costs under speculation, the knob to
test is `-ac`, not `-pl` — and that test stays inside the 150 W envelope.

## The OOM is itself the finding

`dfl_n15` died at `ggml-cuda.cu:109 CUDA error: out of memory`, inside
`ggml_cuda_pool_vmm::alloc` ← `ggml_cuda_mul_mat_cublas` — a transient pool allocation, not a
weights ceiling. **MTP survived the same depth.**

That asymmetry is architectural: the MTP head lives *inside* the target file (`blk.64`) and
shares the target's KV cache, while DFlash is an external model with its own `ctx_dft` and its
own cache. So on a 16 GB-per-card box, **the drafter that is cheaper in compute is the one
that runs out of memory first**, and it does so exactly at the depth where it is supposed to
win. That is a deployment constraint, not a bug.

Recovery attempts (`s2c_dfl15.sh`), least-invasive first:

| | change | result |
|---|---|---|
| A | `GGML_CUDA_NO_VMM=1`, `-c 8192` | **failed** — still OOM |
| B | `GGML_CUDA_NO_VMM=1`, `-ngld 40` | **failed** |
| C | `-c 4096` | ran: **15.86 t/s** |

**C is NOT comparable** — every other arm is `-c 8192` — and is recorded only as an existence
proof that the arm runs. Read alongside MTP's 14.65 it suggests DFlash n=15 is also far below
the unspeculated 28.87, but the table above deliberately leaves the cell empty.

## A hypothesis I formed, tested wrongly, and withdraw

`mtp_n15` draws **58.8 W busy — less than plain decode's 75.3 W — while running 2× slower**.
A compute-saturated arm cannot draw less power than the workload it is slower than, so the
GPU is **idle-waiting, not compute-bound**. That observation is solid and it falsifies the
mechanism pre-registered in `dflash_p100.sh` (*"the wide verification batch saturates compute
on a bandwidth-rich/compute-poor card"*). Direction predicted right, reason wrong.

I then proposed launch overhead: *"CUDA graphs are disabled on Pascal, so 15 sequential
dependent head passes each pay full launch cost."* **That premise was false and the test of it
was void.** Three compounding errors, recorded because each is reusable:

1. **The log line came from a different machine and a different binary.** The
   `"disabling CUDA graphs due to GPU architecture"` message I quoted was in `t16k.log` on
   **`.194`** — a `frontier-hazard` run on buun's tree — not from `.73`'s server at all. I
   carried an observation across two boxes and two llama.cpp versions.
2. **The override I tested does not exist in that build.** `GGML_CUDA_FORCE_GRAPHS` is read
   **nowhere** in `moe-cache-test`. `S2b` set an environment variable the binary ignores, so
   its null result (51.23 vs 51.31; 14.63 vs 14.65; power unchanged) tested nothing.
3. **Graphs were on the whole time.** `CMakeCache.txt` has `GGML_CUDA_GRAPHS:BOOL=ON`, and
   this build's `ggml_cuda_graph_check_compability` gates only on node type
   (`MUL_MAT_ID`), with **no architecture gate**. So CUDA graphs were active during every S2
   arm.

**Net: the serialization mechanism behind MTP's depth-15 collapse remains unexplained.** The
power evidence for *"idle-waiting, not compute-bound"* stands; the explanation for *why*
does not. `S2b`'s arms are void and are not quoted as evidence in either direction.

**`AFM-19`:** *a null result only counts if the manipulation is verified to have taken
effect.* Check that the flag is read, the message changed, or the state actually differs —
before reading the null. And never carry a log observation between binaries.

## Relevance to `TheTom/llama-cpp-turboquant#306` (adaptive draft depth)

That PR adds runtime-adaptive depth via a hysteresis state machine driven by **acceptance
rate** — up after consecutive full accepts, down on misses, bounded by
`--spec-draft-n-min-adaptive` (default 3) and `--spec-draft-n-max`.

**This data says acceptance rate cannot, by itself, choose a depth.** Acceptance matched
across the two architectures to within 1 pp at every depth (table above), while the optimal
depth did not:

| n | acceptance | 9070 XT | P100 |
|---|---:|---|---|
| 15 | ~29 % | **best arm** (150.66, 2.7× off) | **worst arm** (14.65, 0.5× off) |

**At the same 29 % acceptance, one architecture is at its fastest and the other is slower than
not speculating.** An acceptance-driven controller receives an identical signal in both cases
and would back off on RDNA4 precisely where it should push. Its floor of 3 happens to protect
Pascal, but by construction rather than by observing the cost.

The signal that separates them is **measured throughput**, which the controller could sample
directly at no extra cost — it is already generating tokens. Offered as a measurement, not a
design prescription; the PR is MTP-only and this fleet is the only Pascal + RDNA4 pair
reporting into that project.

## What this does not establish

- **One model, one target file.** `Qwen3.5-9B-Q8_0`; no MoE, no larger target.
- **Decode only**, 320-token generations, single slot, `-c 8192`.
- **Capped clocks.** 1063 MHz vs a 1328 MHz stock boost; absolute numbers scale with that.
- **No fidelity gate.** Throughput and acceptance only. `RESULT_SPECULATION_IS_NOT_BIT_EXACT`
  already showed speculative output is not bit-identical to non-speculative, so acceptance
  rate is not a quality claim.
- **`dfl_n15` at `-c 8192` is still missing** and the mechanism behind the n=15 collapse is
  still open.
