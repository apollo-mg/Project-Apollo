# Pre-registered — is jabba's Flash-Next gibberish the missing Turbo K/V unrotation?

Registered **2026-09-02**, before any run. Prompted by jabba on Discord: *"qwen3.8-flash fails
completely for me, generates gibberish or nothing at all, other models including other models
larger than my VRAM work just fine."*

## Hypothesis, from code reading only

buun's master carries two qwen4 correctness fixes that Tom's `feature/turboquant-kv-cache`
(`fb2cc35ab`) does **not**:

| fix | buun | Tom |
|---|---|---|
| `295850adc` restore Turbo **V** output in sparse attention | `build_attn_v_unrotate(...)` | still the bare `if (inp->self_v_rot)` Hadamard, line 585 |
| `0f6a7267a` unrotate Turbo **K** after QSA gather | `ggml_turbo_wht(ctx0, k_sel, 1)` | **no occurrence** of `ggml_turbo_wht` / `ggml_is_turbo_kv_type` in `qwen4exp.cpp` |

buun's own note gives the mechanism: the optional upstream Hadamard tensor is *"deliberately
absent for Turbo cache types"*, so on a Turbo V cache `self_v_rot` is null, the branch never runs,
and V is consumed in the rotated storage domain. Same for K after `GET_ROWS` materializes a static
Turbo cache as F32.

**Predicted consequence:** on Tom's fork, Qwen3.8-Flash-Next produces garbage **only when the KV
cache is a Turbo type**, and is fine on `f16`. Other architectures are unaffected because they do
not use the QSA sparse-attention path — which matches "other models work just fine".

## Arms — single GPU throughout

`CUDA_VISIBLE_DEVICES=0`, default `-sm layer`. Deliberately single-device to remove the
`head_count_kv` zero-width-slice failure (Flash-Next has `head_count_kv = 2`) as a confound —
that is a *different* garbage-producing bug and must not contaminate this one.

| # | arm | prediction | confidence |
|---|---|---|---|
| A | `-ctk f16 -ctv f16` | **coherent** | 0.85 |
| B | Turbo KV (`turbo3`/`vbr`, whichever the build accepts) | **garbage** | 0.75 |
| C | `-ctk q8_0 -ctv q8_0` — quantized but NOT Turbo | **coherent** | 0.70 |

## Reasoning

**B at 0.75, not higher.** The code reading is unambiguous, but I have not confirmed that
`self_v_rot` is actually null under a Turbo cache on *Tom's* tree — that is buun's claim about
*buun's* tree, and the two implementations have diverged. If Tom populates `self_v_rot` for Turbo
types, the branch fires and the bug does not exist.

**C is the arm that makes the finding specific.** If q8_0 is also garbage, the problem is
quantized KV in general, not the Turbo rotation, and the diagnosis is wrong.

**A at 0.85 rather than 0.95** because jabba also reports "or nothing at all", which can indicate
a separate load/emit failure that f16 would not fix.

## Falsifiers stated in advance

- **All three coherent** -> hypothesis dead; jabba's issue is config or hardware, not this.
- **All three garbage** -> not the Turbo rotation; look at the arch import itself.
- **A and C coherent, B garbage** -> confirmed, and the fix is a port of buun's two commits.

## Not claimed

jabba's hardware and exact flags are unknown; he may be on multiple GPUs, in which case the
`head_count_kv` rule is a competing explanation. This run tests only whether the Turbo-rotation
bug **exists on Tom's fork**, which is worth knowing regardless of what jabba is hitting.
