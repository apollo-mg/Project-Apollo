# DRAFT — PR #324 reply for `1336de3bf`. For Mark to review. NOT POSTED.

---

Synced to `1336de3bf`. DS4 gets **materially further** — it now reaches warm-up — and the mirroring
of `attn_output_a/b` is clearly correct. Two gaps left, both traced to a specific line.

## DS4, `-ts 1,1` (two devices) — two blockers, in order

### Blocker 1: `ROPE_BACK` is routed to the wrong handler

First failure was `ggml-backend-meta.cpp:535 GGML_ASSERT(ret.axis != GGML_BACKEND_SPLIT_AXIS_UNKNOWN)`.
Instrumented:

```
SPLIT UNKNOWN: op=ROPE_BACK dst=node_47 scalar_only=1
   src[0] = attn_raw-0 (reshaped) (view)      axis=1    <- split
   src[1] = Meta(CUDA0,CUDA1)#leaf_11#0       axis=10   <- MIRRORED
```

`ROPE_BACK` has the same source signature as `ROPE` (data + mirrored positions/freqs), but the
dispatch sends it somewhere else:

```cpp
case GGML_OP_ROPE:      split_state = handle_rope(src_ss);                        break;
case GGML_OP_ROPE_BACK: split_state = handle_generic(src_ss, /*scalar_only=*/true); break;
```

`handle_generic` requires every source to share a split state, so split data against mirrored
positions yields `UNKNOWN` and aborts — and `scalar_only=true` would force `UNKNOWN` for any real
split axis even if they agreed. `handle_rope` already encodes the right rule
(`GGML_ASSERT(src_ss[1].axis == MIRRORED); return src_ss[0];`).

**Tested:** routing `GGML_OP_ROPE_BACK` to `handle_rope` clears this and DS4 then **reaches
warm-up**. One line:

```cpp
 case GGML_OP_ROPE_BACK: {
-    split_state = handle_generic(src_ss, /*scalar_only =*/ true);
+    split_state = handle_rope(src_ss);
 } break;
```

I have not checked whether any arch relies on the old `scalar_only` behaviour for `ROPE_BACK`, so
treat that as a proposal rather than a verified-safe change.

### Blocker 2: `handle_mul_mat` has no MIRRORED x AXIS_2 case

With that applied, the next stop is `ggml-backend-meta.cpp:593`, the `GGML_ABORT("fatal error")`
at the end of `handle_mul_mat`. Instrumented:

```
MUL_MAT unhandled: dst=attn_wo_a-0
  src0 = blk.0.attn_output_a.weight (reshaped)      axis=10  <- MIRRORED (your new fix)
  src1 = attn_derope-0 (reshaped) (permuted)        axis=2   <- split on AXIS_2
```

`handle_mul_mat` covers MIRRORED x MIRRORED, AXIS_1 x MIRRORED, MIRRORED x AXIS_1, and
AXIS_0 x AXIS_0. **MIRRORED x AXIS_2 is not covered** — and that combination is exactly what
mirroring `attn_output_a` creates, since the activation it multiplies is still head-split.

By analogy with the existing MIRRORED x AXIS_1 case (which returns `src_ss[1]`), a mirrored weight
against a head-split activation should presumably yield the head-split result. But that is your
invariant to set, not mine, so I stopped here rather than guess.

## Summary

| head | DS4 `-ts 1,1` first failure |
|---|---|
| `c232282aa` | `:730` SET_ROWS split mismatch (graph) |
| `163517b9a` | `ggml-backend.cpp:472` OOB write during **weight loading** |
| `3042c600b` | central policy stop: `attn_output_a`, 1 unit for 2 devices |
| `1336de3bf` | `:535` UNKNOWN axis on **ROPE_BACK** |
| `1336de3bf` + ROPE_BACK fix | `:593` **MUL_MAT MIRRORED x AXIS_2**, after warm-up |

Steady progress each time. Did not run `-ts 1,1,1,1` or `-ts 3,4,4,1`, since you gated those on
two devices passing.

Tree left clean at `1336de3bf`; all instrumentation reverted. Happy to test whatever you push.
