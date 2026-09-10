# DRAFT — PR #324 reply for `16f65b057`. For Mark to review. NOT POSTED.

---

Synced to `16f65b057`. Both propagation rules work — DS4 gets past `ROPE_BACK` and past the first
projection — and the new diagnostic did exactly what you built it for. It stops at two devices, one
matmul later.

## DS4, `-ts 1,1` — one more gap, cleanly reported

```
llama-server -m DeepSeek-V4-Flash-0731-UD-IQ1_S-00001-of-00003.gguf \
  -ngl 99 -sm tensor -c 8192 -ts 1,1 -fit off -fa on -ncmoe 40 -np 1
```

Warm-up reached, then:

```
ggml-backend-meta.cpp:597: unsupported mul_mat split states:
  node = attn_out-0
  src0 = blk.0.attn_output_b.weight            axis=10   (MIRRORED)
  src1 = attn_wo_a-0 (permuted) (cont)         axis=0    (AXIS_0)
```

No instrumentation needed on my side this time — node, both sources, both axes, straight out of the
log. That is a real improvement over chasing `GGML_ABORT("fatal error")` with a custom build.

### Where the axis-0 split comes from

Your axis-2 rule fired correctly and produced `attn_wo_a` carrying the activation's head split. A
`permute` + `cont` then lands that same data on **axis 0**, and the second half of the grouped
projection (`attn_output_b`) multiplies it. So this is the immediate downstream consequence of the
rule you just added, not an unrelated gap.

### Why this one is the contraction-dimension case

Your new rule is scoped to a replicated left operand with the right operand split over axis 2 or 3,
**outside** the contraction dims. Here the right operand is split over **axis 0**, which *is* the
contraction dimension. Each device holds the full `attn_output_b` and a slice of the activation
along the contracted axis, so each computes a partial sum and the true result is their sum.

That is the same situation the existing branch at `:595` already handles for the both-split case:

```cpp
if (src_ss[0].axis == AXIS_0 && src_ss[1].axis == AXIS_0) {
    GGML_ASSERT(split_states_equal(src_ss[0], src_ss[1]));
    return {assume_sync ? MIRRORED : PARTIAL, {0}, {1}, 1};
}
```

So MIRRORED x AXIS_0 looks like it should yield **PARTIAL** (or MIRRORED under `assume_sync`) by the
same argument — a replicated weight against a contraction-split activation is still a partial
product. `PARTIAL` appears to be fully wired downstream (9 sites in this file, including the
all-reduce path), so it should not be a new concept.

**Stated as an observation, not a patch.** You scoped the last rule deliberately narrowly, and
whether a mirrored-times-contraction-split matmul should silently become an all-reduce is your
invariant to set — it changes the communication pattern, not just the bookkeeping. I did not test a
change this time; happy to if you want it de-risked on real hardware before you push.

## Trajectory

| head | DS4 `-ts 1,1` first failure |
|---|---|
| `c232282aa` | `:730` SET_ROWS split mismatch |
| `163517b9a` | `ggml-backend.cpp:472` OOB write during weight loading |
| `3042c600b` | central policy stop — `attn_output_a`, 1 unit for 2 devices |
| `1336de3bf` | `:535` UNKNOWN axis on ROPE_BACK |
| `1336de3bf` + ROPE_BACK fix | `:593` MUL_MAT MIRRORED x AXIS_2 |
| **`16f65b057`** | **`:597` MUL_MAT MIRRORED x AXIS_0**, one matmul further, self-reported |

Did not run `-ts 1,1,1,1` or `-ts 3,4,4,1`, per your gating. Tree clean at `16f65b057`, no local
modifications.
