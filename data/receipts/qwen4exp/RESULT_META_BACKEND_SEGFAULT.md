# Deterministic segfault in `ggml_backend_meta_graph_compute` on a prefix-extension prompt

**Status: CLOSED. Do NOT report.** The crashing configuration was deliberately disabled upstream
and in buun's tree on 2026-09-01, hours after the commit our binary was built from. Current code
refuses it with a clean error instead of crashing. Kept as a record of the failure mode behind
that gate.

**2026-09-03.** `.194`, 2x P100 (sm_60) @ 150 W / 1063 MHz, Ubuntu 26.04.
Build `~/buun-llama-cpp/build_sm60_qwen4` at **`7a918624b`** (2026-09-01), configured
`-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=60 -DGGML_CUDA_FA=ON -DGGML_CUDA_FA_ALL_QUANTS=OFF
-DCMAKE_BUILD_TYPE=Release`, nvcc `/usr/bin/nvcc`.

## Reproducer — 2 requests, 3/3 crashes

```
llama-server -m Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf \
  -c 16384 -ngl 99 -fa on --jinja -np 1 -fit off -ncmoe 30 -sm tensor --kv-unified \
  --host 127.0.0.1 --port 8096
# CUDA_VISIBLE_DEVICES=0,1  GGML_CUDA_ALLREDUCE=internal
```

1. POST `/completion` with a ~1,800-token prompt (`cache_prompt: false`, `n_predict: 8`).
2. POST `/completion` with a ~3,650-token prompt **whose text begins with prompt 1**.
3. Server segfaults during the second request. `curl: (52) Empty reply from server`.

Three fresh-server trials, three crashes, core dumped each time. A fourth crash occurred earlier
in the prefill sweep that first surfaced this.

## The crash is at one fixed instruction

```
llama-server[1778889]: segfault at 76b8c72a9e24 ip 76b963aec131 error 6 in libggml-base.so.0.22.0[53131,76b963aae000+a2000]
llama-server[1878450]: segfault at 71797e2a7e24 ip 717a1e8ec131 error 6 in libggml-base.so.0.22.0[53131,717a1e8ae000+a2000]
llama-server[1913284]: segfault at 7024b22a7e24 ip 702552e8a131 error 6 in libggml-base.so.0.22.0[53131,702552e4c000+a2000]
llama-server[1947665]: segfault at 7ef2bf2a9e24 ip 7ef35c0ec131 error 6 in libggml-base.so.0.22.0[53131,7ef35c0ae000+a2000]
```

Module offset **`0x53131` in all four**, across different PIDs and ASLR bases. `error 6` = write
to a non-present page, user mode.

```
$ addr2line -f -C -e libggml-base.so.0 0x53131
ggml_backend_meta_graph_compute(ggml_backend*, ggml_cgraph*)
ggml-backend-meta.cpp
```

## Server-side signature, identical in all three trials

```
slot cache_plan_s: selected slot by LCP similarity, f_sim_best = 0.500 (> 0.100 thold), f_keep = 0.997
slot   operator(): edit/divergence sample
    (cached/incoming/lcp/reusable/rewind/append/cache_prompt) = (1824/3649/1824/0/0/1825/0)
slot print_timing: prompt processing, n_tokens = 3645, progress = 1.00, t = 103.02 s / 35.38 tok/s
<segfault>
```

`lcp = 1824` but `reusable = 0` — a full common prefix is found and then none of it is reused.
`rewind = 0` in the reproducer, so **the rewind is not required**; the original sweep crashed with
`rewind = 6`. `cache_prompt` is `false` on the request and the slot-selection path still runs.

Also present on **every** task in this build, including ones that do not crash:
`checkpoint publication/accounting preparation failed; retained ring is unchanged`.

## Ruled out

- **Not OOM.** 58 GB of 60 GB host RAM available; `dmesg` shows no OOM killer, only the segfault.
- **Not context overflow.** 3,649 tokens into `-c 16384`.
- **Not the model file.** Same GGUF serves shorter prompts fine, and served the full TURBO and
  batch suites earlier today.
- **Not a one-off.** 3/3 plus the original.

## Why this hardware found it

`GGML_CUDA_ALLREDUCE=internal` is set, but sm_60 fails the `cc >= 700` gate, so every run takes the
fallback: `internal AllReduce init failed (n_devices != 2?); falling back to meta-backend butterfly`
(see [allreduce-internal-inert-on-pascal]). The butterfly reduction lives in this same file
(`ggml-backend-meta.cpp:2432`). This is the inverse of the usual Pascal situation: normally sm_60
means *we cannot test the bug* (CUDA graphs, MMA flash-attention, PDL launch ordering -- three
separate cases today). Here it means we are on a branch few others exercise.

## Isolation — it requires `-sm tensor`

All three arms at `-ncmoe 44` so split mode is the only variable:

| arm | config | result | meta backend |
|---|---|---|---|
| C (control) | 2 GPU, `-sm tensor` | **CRASH** | butterfly active |
| A | 2 GPU, `-sm layer` | clean, server alive | not used |
| B | 1 GPU | clean, server alive | not used |

The control crashing at `-ncmoe 44` rules out the original `-ncmoe 30` being special. Both crash
sites symbolize to the same routine: `0x53131` (write to non-present page) and `0x531cb`
(null deref), 154 bytes apart in `ggml_backend_meta_graph_compute`.

**Bug statement:** `-sm tensor` on qwen4exp + a request whose prompt extends a previous request's
prefix -> segfault in the meta backend graph compute. Two requests, no exotic flags.

## Attribution — RESOLVED: fork-only configuration

Stock `ggml-org/llama.cpp` at `d30500b` (2026-09-03), built for sm_60 with identical cmake flags,
**refuses to start in the crashing configuration**:

```
E llama_model_load: error loading model: LLAMA_SPLIT_MODE_TENSOR not implemented for architecture 'qwen4exp'
```

Upstream has the architecture (`src/models/qwen4exp.cpp`, `LLM_ARCH_QWEN4EXP` in `llama-arch.cpp`)
but does not implement tensor-split for it. `ggml_backend_meta_graph_compute` itself is upstream
code, but **the path that reaches it in this configuration exists only in buun's fork**. Upstream
users cannot hit this. It is buun's to fix, and there is nothing to file with ggml-org.

## A narrative I over-claimed, corrected

I initially framed this as "only Pascal exercises this branch", built on the observed
`falling back to meta-backend butterfly` warning and the day's pattern of three sm_60-only fallback
findings (CUDA graphs, MMA flash-attention, PDL launch ordering). **The evidence does not support
that.** The isolation shows the trigger is tensor-splitting; the butterfly fallback is *present*
but was never shown to be *necessary*. Hardware with working internal AllReduce may well crash by a
different route through the same function. That is answerable by anyone with two post-Pascal GPUs
and matters for how widely this bites, so it belongs in the report as an open question rather than
as a Pascal-exclusivity claim.

## Attribution is NOT yet established

I initially called `ggml-backend-meta.cpp` fork-specific. **That was wrong** -- it exists upstream
at `ggml/src/ggml-backend-meta.cpp` in `ggml-org/llama.cpp`. But buun's tree carries fork commits
touching it, including `fa8b372e7 ggml-backend-meta: allow sharded + full-width MIRRORED binary
ops` and `f5ad17a09 vbr : tensor-parallel KV -- meta-backend shard pools (WIP)`, alongside
upstream-numbered work (`#26490` DeepSeek 4 `-sm tensor`, `#27574`, `#27586`).

Shared code with fork modifications. Two builds settle it, both in flight:

1. **Stock `ggml-org/llama.cpp` at sm_60**, same cmake flags -> does the reproducer crash there?
2. **buun HEAD** (we are 4 commits behind; `cb703be37` "preserve MTP state across prompt
   checkpoints" landed after our build and touches this area) -> is it already fixed?

Isolation also running: `-sm layer` on 2 GPUs (same footprint, different split) and single-GPU
`-ncmoe 44` (no meta backend at all), to establish whether this is tensor-split-specific or
multi-GPU-general.

**Nothing goes to buun until 1 and 2 are answered.** He is mid-merge and has already said of a
different fix "could be a different issue actually"; an unattributed crash report would cost him
time. The old build is preserved as the control that demonstrates the crash.


## Resolution — the config was already known-broken and gated off

`llm_arch_supports_sm_tensor()` in `src/llama-arch.cpp` is a **denylist**: enumerated cases
`return false`, `default: return true`.

| build | `QWEN4EXP` in denylist | `-sm tensor` on qwen4exp |
|---|---|---|
| ours, `7a918624b` (2026-09-01) | absent -> `default: return true` | permitted -> **segfault** |
| buun HEAD, `3823c9eb6` | `case LLM_ARCH_QWEN4EXP:   // TODO: fix test-llama-archs` | **refused, clean error** |
| upstream `d30500b` | present | refused, clean error |

Added by **`36b101543` "qwen4exp: fix seq_cp, block position keying, mtmd input, cuda abort, add
tests (#27941)", Daniel Han, 2026-09-01** — the same day as, but a few commits after, the commit
our binary was built from. The `TODO` comment shows the author already knew the path fails tests.

**Therefore: nothing to report.** Both buun and upstream refuse the configuration. A reproducer for
a path that is already gated costs the maintainer time and delivers nothing. This receipt stands as
a record of *what* the failure actually is behind that gate -- a segfault in
`ggml_backend_meta_graph_compute` on a prefix-extension prompt -- which the TODO ("fix
test-llama-archs") does not describe. If anyone later un-gates qwen4exp tensor-split, this is the
runtime symptom to check for, and the two-request reproducer is in `~/segv_repro.sh` on `.194`.

## Operational consequence for this fleet

**`-sm tensor` on Flash-Next is no longer available.** Today's Flash-Next measurements
([RESULT_BATCH_PARALLELISM.md](RESULT_BATCH_PARALLELISM.md), the prefill sweep) all used
`-sm tensor` on `7a918624b`. Those numbers are valid records of what that binary did, but they are
**not reproducible on current code**. Future Flash-Next work on 2+ GPUs must use `-sm layer`
(verified working today, arm A of the isolation) or a single GPU, and throughput will differ.
