# #348 on RDNA4: the deadlock fix is correct, and it uncovers a second bug underneath

**2026-09-05.** RX 9070 XT (gfx1201, ROCm), `TheTom/llama-cpp-turboquant`.
Raw: `raw_tq348_rdna4_fix.log`. Both builds `-DGGML_HIP=ON -DAMDGPU_TARGETS=gfx1201
-DGGML_HIP_NO_VMM=OFF -DCMAKE_BUILD_TYPE=Release`, env `GGML_TQ_MMQ=1 GGML_TQ_NATIVE=1`.

## Part 1 — the hang reproduces on RDNA4 (issue #348 was RDNA-unverified)

`439fe673` ("cuda: read GGML_TQ_MMQ once instead of on every mul_mat"), the commit that
introduced the self-recursive static:

```cpp
static bool ggml_cuda_tq_mmq_enabled() {
    static const bool enabled = ggml_cuda_tq_mmq_enabled();   // calls itself
    return enabled;
}
```

`test-backend-ops test -o MUL_MAT -p type_a=tq4_1s -b ROCm0`:

| | observed |
|---|---|
| test cases completed | **0 of 149** |
| elapsed before kill | 143 s |
| `/proc/<pid>/wchan` | **`futex_wait`** |
| GPU utilisation | 8 % (idle) |

Identical signature to @jasstrong's MI210 (gfx90a) report. The issue text asserted
*"on RDNA and CDNA any prefill hangs"*; **RDNA is now measured, not inferred.**

## Part 2 — the fix works, and exposes an abort at the same shape

`27d17bd68` (merge of #348), same command, same machine:

```
MUL_MAT(type_a=tq4_1s,...,m=16,n=1..7,k=256,...): OK      <- 7 cases now pass
MUL_MAT(type_a=tq4_1s,...,m=16,n=8,k=256,...):  J_best=0
mmq.cuh:1561: fatal error
```

Exit **134** (SIGABRT). Cases n=1..7 pass where previously *nothing* ran, so the deadlock is
genuinely fixed. But the run aborts at **`m=16, n=8, k=256`** — precisely the case
jasstrong named as the hang point, and the first with `n >= 8` (the MMQ threshold).

**On RDNA4 the deadlock was masking a second, independent failure at the same shape.**
jasstrong's MI210 run reported 149/149 after the fix, so this is arch-specific.

## Root cause

`mmq.cuh:1489-1510`:

```cpp
int J_best        = 0;
int ntiles_J_best = INT_MAX;

for (int J = 8; J <= 128 && ntiles_J_best > 1; J += 8) {
    const ggml_cuda_mmq_config config = ggml_cuda_mmq_get_config(type, J, fallback, cc);
    if (config.type == GGML_TYPE_COUNT)                  continue;   // no config for (type, J)
    if (mmq_get_nbytes_shared(config, cc) > smpbo)       continue;   // exceeds shared mem
    ...
    J_best = J;
}

switch (J_best) {
    case 8: ... case 128: ...
    default:
        fprintf(stderr, "J_best=%d\n", J_best);
        GGML_ABORT("fatal error");
}
```

**Every one of the 16 candidates (J = 8, 16, ... 128) is rejected**, so `J_best` keeps its
initialiser `0`, the switch finds no `case 0`, and it aborts. There is no guard between the
loop and the switch — no "found nothing, fall back to the non-MMQ path" branch.

Backtrace confirms the path:
```
ggml_abort
mul_mat_q_switch_J<(ggml_type)46, true>      <- type 46 = TQ4_1S, fallback=true
ggml_cuda_mul_mat_q
ggml_cuda_mul_mat_tq4_1s_mmq
ggml_cuda_mul_mat
ggml_cuda_graph_evaluate_and_capture
```

**Measured cause (hypothesis falsified).** I predicted the `smpbo` shared-memory check was
rejecting every candidate, reasoning that RDNA4's 64 KB LDS is tighter than CDNA/NVIDIA.
**Wrong.** Instrumenting both `continue` branches and re-running:

```
[JPROBE] J=  8 rejected: no config (GGML_TYPE_COUNT)
[JPROBE] J= 16 rejected: no config (GGML_TYPE_COUNT)
...
[JPROBE] J=128 rejected: no config (GGML_TYPE_COUNT)
```

**16 of 16 rejected by `GGML_TYPE_COUNT`. Zero by the shared-memory check.** Nothing to do
with memory limits.

The dispatcher (`mmq.cuh:229`) routes by architecture:

```cpp
if (GGML_CUDA_CC_IS_RDNA4(cc)) return ggml_cuda_mmq_get_config_rdna4(type, J, fallback);
```

and the RDNA4 table has no TQ4_1S entry at any J:

| config table | TQ4_1S entries | TQ3_1S entries | total CASEs |
|---|---:|---:|---:|
| `mmq-config-cdna.cuh` | **8** | 0 | 161 |
| `mmq-config-rdna3.cuh` | **13** | 0 | 272 |
| `mmq-config-ampere.cuh` | 0 | 0 | 352 |
| **`mmq-config-rdna4.cuh`** | **0** | **0** | 260 |

So the TQ MMQ path was wired up for CDNA and RDNA3 and never given RDNA4 entries. The
lookup correctly reports "no config", the loop correctly rejects all 16, and then the switch
has no `case 0` to land on — the missing piece is a guard for "no viable J, fall back to the
non-MMQ path" rather than aborting.

Note `TQ3_1S` is 0 everywhere including CDNA and RDNA3, so `tq3_1s` presumably takes a
different route or is simply never MMQ-dispatched; untested here.

## Why CI did not catch it

The abort is behind `GGML_TQ_MMQ=1`, an opt-in env var, on an AMD-only code path, at
`n >= 8`. The project has no AMD hardware; every gate that stayed green ran either on
NVIDIA (where the environment lookup short-circuits) or below the MMQ threshold.

## Scope and caveats

- One card, one type (`tq4_1s`), one shape. `tq3_1s` untested — same gate, likely same result.
- The `smpbo` hypothesis is inference from the code, not a measurement.
- **This is not a regression in #348.** #348 fixes a real deadlock and its fix is correct.
  This second bug was simply unreachable while the deadlock existed.
- Default builds are unaffected: without `GGML_TQ_MMQ=1` the path is never taken.
