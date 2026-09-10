# DRAFT — PR #324 reply for `85eb0596a`. For Mark to review. NOT POSTED.

---

Synced to `85eb0596a`. **DS4 generates coherent text under `-sm tensor` on all three
topologies** — 2 devices, 4 devices, and uneven `-ts 3,4,4,1`. Your memset implementation holds
up; one op still needs a dispatch entry, and with that added nothing else stops it.

4x P100 sm_60 @ 150 W / 1063 MHz, `DeepSeek-V4-Flash-0731-UD-IQ1_S`,
`-ngl 99 -c 8192 -fit off -fa on -ncmoe 40 -np 1`, `GGML_CUDA_ALLREDUCE=internal`.

## The one remaining stop

As pushed, the run reaches server-ready and then aborts on the first decode (observed on 2
devices — both 4-device arms were run with the dispatch already in, so I did not watch them fail
without it):

```
ggml-backend-meta.cpp:1035: ggml op not implemented: LIGHTNING_INDEXER
```

Rather than guess a rule I instrumented the op to print its sources' split states. Every
occurrence, every layer:

```
LI-DIAG node=lid_score_masked-2 ne=[256,4,1,1]
  src0=lid_q_rot-2 (view)                      axis=10  ne=[128,64,4,1]
  src1=lid_k-2                                 axis=10  ne=[128,1,256,1]
  src2=lid_weights-2 (view)                    axis=10  ne=[64,4,1,1]
  src3=Meta(CUDA0,CUDA1)#dsv4_lid_kq_mask#0    axis=10  ne=[256,4,1,1]
```

All four sources MIRRORED. So the indexer needs no rule of its own, just routing — it sits with
the other DS4 ops:

```cpp
             case GGML_OP_DSV4_HC_COMB:
             case GGML_OP_DSV4_HC_PRE:
-            case GGML_OP_DSV4_HC_POST: {
+            case GGML_OP_DSV4_HC_POST:
+            case GGML_OP_LIGHTNING_INDEXER: {
                 split_state = handle_generic(src_ss, /*scalar_only =*/ true);
             } break;
```

`scalar_only = true` deliberately: the indexer reduces over both `ne[0]` (head dim) and `ne[1]`
(indexer heads) of `q`, so an all-MIRRORED graph passes and a genuinely dimension-split one aborts
loudly rather than computing on a wrong slice. If you would rather it handle a real split, that
needs a rule I have no case to test against — nothing in this model produces one.

## Results with that one line added

Three prompts per arm, not one: a fresh prompt, an unrelated prompt (forces a full sequence
reset), and one sharing a long prefix with the second (forces `cached n_tokens > 0`). Your memset
has five distinct paths and I did not want to claim it from a single call.

| arm | ready | asserts | 3/3 prompts | VRAM per device (MiB, after prompts) |
|---|---|---|---|---|
| `-sm tensor -ts 1,1` | 172 s | none | yes | 7177 / 7177 |
| `-sm tensor -ts 1,1,1,1` | 172 s | none | yes | 4535 / 4535 / 4535 / 4535 |
| `-sm tensor -ts 3,4,4,1` | 182 s | none | yes | 4815 / 5381 / 5857 / 3239 |
| `-sm layer -ts 1,1` (control) | 194 s | none | yes | 5205 / 9267 |

The even tensor arms are exact to the megabyte; layer split at `-ts 1,1` is 1.78x lopsided.

Sample completion, 4 devices, `-sm tensor -ts 1,1,1,1`:

> ` Paris. It is the largest city in France, with a population of over 2 million people. Paris is
> known for its iconic landmarks such as the Eiffel Tower, the Louvre Museum, and Notre-Dame
> Cathedral. It is also a major cultural and economic center in Europe...`

and on the primes prompt it returns 2, 3, 5, 7, 11 with `9 is not prime because it is divisible
by 3`. Same facts as the layer-split control, no `////`.

## One thing I nearly reported as a bug, and the control that stopped me

The uneven `-ts 3,4,4,1` arm loops — `</div>` twenty times on one prompt, a doubled `</think>`
block on another — where the even arms do not. That reads like uneven slices breaking numerics.

It is not. `-sm layer -ts 3,4,4,1`, same binary, same prompts, reproduces the doubled `</think>`
block **byte for byte** and degenerates worse on the other prompt. It is the 1-bit quant with an
uneven layer distribution, and it is not attributable to tensor split.

## `test-llama-archs` on sm_60

Ran it twice at 2 devices — on the head as pushed, and again on the patched tree, since the patch
is what I am proposing.

- As pushed: **rc=0**, 458 OK rows, every Meta row OK or SKIP.
- **With the LI dispatch: rc=0, 458 OK rows, no failures.** Unchanged.
- All four devices visible: aborts, but at your policy stop, working correctly —
  `llama-model.cpp:818: cannot tensor-split blk.0.attn_q.weight: segment 0 has only 2 splittable
  units for 4 devices`. The synthetic archs have `head_count_kv = 2`.

Flagging that only because it means the suite is not runnable as-is on a >2-GPU box, which you
would not see on the 5090 or the M5 Max.

## Separate, small: the AllReduce warning blames the wrong thing on Pascal

Every tensor arm logs this (no layer arm does), with exactly 2 devices visible and
`GGML_CUDA_ALLREDUCE=internal` set:

```
W internal AllReduce init failed (n_devices != 2?); falling back to meta-backend butterfly
```

At `-lv 5` the real reason shows up one line above, at DEBUG:

```
D ggml_cuda_ar_pipeline_init: internal AllReduce requires compute capability >= 700
                              (device 0 has cc=600); falling back
```

`allreduce.cu:404` — the chunked kernel needs `__nanosleep`, so sm_70+. P100 is sm_60 and never
gets past that check; the device count is fine. Nothing is broken, the butterfly fallback works,
but the only message visible at default verbosity names a cause that is false on Pascal, and the
true one is DEBUG-only. Might be worth putting the reason in the WARN.

Useful to me either way: it means internal AllReduce has never been active on any of my Pascal
tensor-split runs, so every number I have sent you came through the meta-backend butterfly.

## Not claiming a throughput number

These are single samples, and the multi-GPU arm on this dual-Xeon box is bistable when NUMA-
unbound (I measured 12.80 / 12.56 / 15.83 / 15.75 on one binary and one set of flags last week and
posted a correction for it). Correctness only here. Happy to do a bound, repeated throughput
comparison against `-sm layer -ts 3,4,4,1` if that is useful.

Tree is otherwise clean at `85eb0596a`; the only local change is the two-line dispatch above.
