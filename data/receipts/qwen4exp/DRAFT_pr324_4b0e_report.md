# DRAFT — PR #324 reply for `4b0e2ee98`. For Mark to review. NOT POSTED.

---

Synced to `4b0e2ee98`. Your correction on the PARTIAL rule was right — I was labelling the result
correctly without making the local dimensions work. The grouped placement gets DS4 substantially
further: with one added matmul rule it now **loads and reaches server-ready**, and the next stop is
a different class of problem entirely.

## `-ts 1,1` on `4b0e2ee98` as pushed

```
ggml-backend-meta.cpp:597: unsupported mul_mat split states:
  node = attn_wo_a-0
  src0 = blk.0.attn_output_a.weight (reshaped)        axis=2
  src1 = attn_derope-0 (reshaped) (permuted)          axis=2
```

Your grouped split works — `attn_output_a` now carries a real split rather than 1 unit. But after
the reshape both operands present on **axis 2**, and `handle_mul_mat` has no case for
`AXIS_2 x AXIS_2`. It covers MIRRORED x MIRRORED, AXIS_1 x MIRRORED, MIRRORED x AXIS_1,
AXIS_0 x AXIS_0, and (from `16f65b057`) MIRRORED x AXIS_2/3.

### Tested addition

`ne[2]`/`ne[3]` are batch dimensions, outside the contraction. If both operands carry the *same*
split there, each device holds matching batch slices of both sides, computes an independent slice,
and no communication is needed — so the result simply carries the split:

```cpp
// Both operands split on the SAME batch axis (ne[2]/ne[3]), outside the contraction dims:
// every device holds matching batch slices of both sides and computes its own slice.
if (src_ss[0].axis == src_ss[1].axis &&
        (src_ss[0].axis == GGML_BACKEND_SPLIT_AXIS_2 || src_ss[0].axis == GGML_BACKEND_SPLIT_AXIS_3) &&
        split_states_equal(src_ss[0], src_ss[1])) {
    return src_ss[0];
}
```

With that, **DS4 clears the split-state phase entirely and the server reaches ready (185 s)**.
Offered as a proposal, not a patch — the `split_states_equal` guard is doing real work there and
you may want it scoped more tightly.

## Next stop: `memset_tensor` is unimplemented on the Meta buffer

```
ggml-backend.cpp:552: GGML_ASSERT(buf->iface.memset_tensor != NULL
                                 && "memset not implemented by backend buffer") failed
```

This is your own marked TODO:

```cpp
/* .memset_tensor   = */ nullptr, // TODO implement     // ggml-backend-meta.cpp:1516
```

Triggered on the **first prompt**, at sequence reset:

```
slot operator(): id 0 | task 0 | new prompt, n_ctx_slot = 8192, task.n_tokens = 5
slot operator(): id 0 | task 0 | cached n_tokens = 0, memory_seq_rm [0, end)
```

DS4 looks like the first architecture to reach it. Ordinary attention KV never needs a memset —
it is overwritten — but DS4's recurrent compressor states (`llama_dsv4_comp_state`, plus the HCA/CSA
and lightning-indexer caches) have to be **zeroed** on a sequence clear. That is a split-buffer
memset across devices rather than a split-state rule, so it is squarely yours to shape.

## Ladder status

Did not reach `-ts 1,1,1,1` or `-ts 3,4,4,1` — both gated on two devices passing.

| head | DS4 `-ts 1,1` first failure | server ready? |
|---|---|---|
| `163517b9a` | OOB write during weight loading | no |
| `3042c600b` | central policy stop — 1 unit for 2 devices | no |
| `1336de3bf` | `:535` UNKNOWN axis on ROPE_BACK | no |
| `16f65b057` | `:597` MUL_MAT MIRRORED x AXIS_0 | no |
| **`4b0e2ee98`** | `:597` MUL_MAT AXIS_2 x AXIS_2 | no |
| **`4b0e2ee98` + the rule above** | `ggml-backend.cpp:552` **memset_tensor unimplemented** | **YES, 185 s** |

Tree left clean at `4b0e2ee98`; all local changes reverted. Happy to test whatever comes next.
