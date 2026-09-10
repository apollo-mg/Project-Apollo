# DS4 tensor split on `85eb0596a` — memset cleared, one op left, 2 devices WORKING

**2026-08-30**, `.194`, 4x P100 sm_60 @ **150 W / 1063 MHz**, `DeepSeek-V4-Flash-0731-UD-IQ1_S`
(77 GB, 3 shards), `GGML_CUDA_ALLREDUCE=internal`. Predictions registered before the run in
`PREDICTIONS_85eb0596a_DS4.md`.

Flags held byte-identical to every prior ladder row: `-ngl 99 -c 8192 -fit off -fa on -ncmoe 40
-np 1`. Only `-sm` / `-ts` / `CUDA_VISIBLE_DEVICES` vary.

## Headline

`85eb0596a` as pushed clears the `memset_tensor` stop. The next stop — the only one observed, on
**2 devices**; see the caveat below — is a missing dispatch entry:

```
ggml-backend-meta.cpp:1035: ggml op not implemented: LIGHTNING_INDEXER
```

With a one-line addition, **DS4 runs coherently under `-sm tensor` on 2, 4, and unevenly-weighted
4 devices** — the first time it has produced text on any of these topologies. No arm asserted; no
arm needed a second rule.

**Caveat on "only".** The `:1035` abort was observed on 2 devices. Both 4-device arms were run on
a binary that already carried the dispatch, so I never watched them fail without it. The op appears
in every layer of every graph, so they would near-certainly stop at the same place — but that is
inference, not a measurement, and it is not claimed as one.

## The coherence baseline (arm 0), so "coherent" is a comparison and not a judgement call

UD-IQ1_S is a 1-bit quant. It writes oddly even when correct, so the same three prompts were run
first under the known-good `-sm layer` on the same two cards, same binary, same flags.

| prompt | `-sm layer` (baseline) | `-sm tensor` + patch |
|---|---|---|
| `The capital of France is` | ` Paris.", "target": "Paris", "ref": null, ...` | ` Paris. It is the largest city in France ... Eiffel Tower, the Louvre Museum, and the Notre-Dame Cathedral.` |
| first five primes / why 9 | `2,3,5,7,11` + `9 ... divisible by 3` | `2,3,5,7,11` + `9 ... can be divided by 3` |
| same prefix, why 15 | `2,3,5,7,11` + `15 ... divisible by 3 and 5` | `2,3,5,7,11` + `15 ... divisible by 3 and 5` |

Both arms drift into JSON/dataset formatting — there is no chat template on `/completion` — but
**every factual claim is correct in both**, and the tensor arm is if anything the more fluent of
the two. This is not the `////` failure mode.

Three prompts, not one, deliberately: fresh, unrelated (forces a full sequence reset), and
prefix-sharing (forces `cached n_tokens > 0`). The new `memset_tensor` has five distinct code
paths and one prompt exercises one of them.

> **Provenance correction, 2026-09-02.** That AXIS_2 rule was **already upstream** — present in
> `spiritbuun/buun-llama-cpp` via an upstream sync dated 2026-07-06, seven weeks before I proposed
> it. Tom said as much when he took it (*"matches the upstream DS4 implementation"*), so nothing
> was misrepresented to him, but "the rule I proposed" reads as novelty and was not. Turboquant
> lacked it only because that fork diverged from upstream before it landed. The `LIGHTNING_INDEXER`
> dispatch IS genuinely ours — absent from upstream-synced trees too.
> See `RESULT_BUUN_MASTER_COMPARISON.md`.

## The remaining op, instrumented rather than guessed

A diagnostic printing the split state of all four sources:

```
LI-DIAG node=lid_score_masked-2 ne=[256,4,1,1]
  src0=lid_q_rot-2 (view)                      axis=10  ne=[128,64,4,1]
  src1=lid_k-2                                 axis=10  ne=[128,1,256,1]
  src2=lid_weights-2 (view)                    axis=10  ne=[64,4,1,1]
  src3=Meta(CUDA0,CUDA1)#dsv4_lid_kq_mask#0    axis=10  ne=[256,4,1,1]
```

All four sources are **MIRRORED** (axis 10), on every one of the op's occurrences. The lightning
indexer therefore needs no split rule of its own — it needs to be *routed*. It sits naturally with
the other DS4 ops:

```cpp
            case GGML_OP_DSV4_HC_COMB:
            case GGML_OP_DSV4_HC_PRE:
            case GGML_OP_DSV4_HC_POST:
            case GGML_OP_LIGHTNING_INDEXER: {
                split_state = handle_generic(src_ss, /*scalar_only =*/ true);
            } break;
```

`scalar_only = true` is the conservative choice and is deliberate: the indexer reduces over both
`ne[0]` (head dim) and `ne[1]` (indexer heads) of `q`, so a genuine dimension split of its inputs
would need real thought. With `true`, an all-MIRRORED graph passes and anything else aborts loudly
instead of silently computing on a wrong slice.

## VRAM: tensor split is the more balanced placement

Measured after the three prompts, so KV is included.

| arm | GPU0 | GPU1 | GPU2 | GPU3 | spread |
|---|---|---|---|---|---|
| `-sm layer -ts 1,1` | 5205 | 9267 | — | — | **1.78x** |
| `-sm tensor -ts 1,1` | **7177** | **7177** | — | — | **1.00x** |
| `-sm tensor -ts 1,1,1,1` | **4535** | **4535** | **4535** | **4535** | **1.00x** |
| `-sm layer -ts 3,4,4,1` | 3905 | 3055 | 4921 | 4943 | 1.62x |
| `-sm tensor -ts 3,4,4,1` | 4815 | 5381 | 5857 | 3239 | 1.81x |

(MiB. Even tensor arms are exact to the megabyte.)

Layer split puts 78 % more on GPU1 than GPU0 at `-ts 1,1`; tensor split is exact. That matters on
a 16 GB card, where the ceiling is set by the fullest device.

The uneven arm does **not** track 3:4:4:1 proportionally (measured ratio ~1.49:1.66:1.81:1.00).
With `-ncmoe 40` most weight is on the CPU, so what remains on each device is dominated by
mirrored and non-split allocations that `-ts` does not scale. Recorded as an observation, not a
defect — I did not test whether the ratio tracks better without `-ncmoe`.

## Ladder

| head | DS4 `-ts 1,1` first failure | server ready? | completes a prompt? |
|---|---|---|---|
| `163517b9a` | OOB write during weight loading | no | no |
| `3042c600b` | central policy stop — 1 unit for 2 devices | no | no |
| `1336de3bf` | `:535` UNKNOWN axis on ROPE_BACK | no | no |
| `16f65b057` | `:597` MUL_MAT MIRRORED x AXIS_0 | no | no |
| `4b0e2ee98` | `:597` MUL_MAT AXIS_2 x AXIS_2 | no | no |
| `4b0e2ee98` + AXIS_2 rule | `ggml-backend.cpp:552` memset unimplemented | yes, 185 s | no |
| **`85eb0596a`** | `:1035` op not implemented: LIGHTNING_INDEXER | yes, 172 s | no |
| **`85eb0596a` + LI dispatch** | — none — | **yes, 172 s** | **YES, coherent** |

### Device-count ladder, all on `85eb0596a` + the LI dispatch

| arm | ready | asserts | 3/3 prompts | verdict |
|---|---|---|---|---|
| `-sm tensor -ts 1,1` (2 dev) | 172 s | none | yes | **PASS** |
| `-sm tensor -ts 1,1,1,1` (4 dev) | 172 s | none | yes | **PASS** |
| `-sm tensor -ts 3,4,4,1` (4 dev, uneven) | 182 s | none | yes | **PASS** |

The uneven arm was the one I expected to fail, at `:1038 GGML_ASSERT(split_state.ne[j] % div == 0)`
— the assert it produced on `c232282aa`. It did not fire. Nothing in this head's diff targets
divisibility, so either an earlier head in the series fixed it or the grouped placement from
`4b0e2ee98` sidesteps it.

### The uneven arm's output, and the control that stopped me reporting a bug

The uneven tensor arm loops — `</div>` twenty times on the France prompt, and a doubled
`</think>: The first five prime numbers ...` on the third. The even arms do not. That reads like a
numerics failure caused by uneven slices.

It is not. Running `-sm layer -ts 3,4,4,1` — the historically-working configuration, same ratio,
same binary, same prompts — reproduces the doubled `</think>` block **byte for byte**, and
degenerates *worse* on the primes prompt (it echoes the prompt back as a token-by-token
translation map). The repetition belongs to the model at IQ1_S with an uneven layer distribution,
not to tensor split.

Stated plainly because the opposite conclusion was one un-run control away.

## `test-llama-archs` on sm_60

Run twice at `CUDA_VISIBLE_DEVICES=0,1`: once on the head as pushed, and again on the **patched**
tree, since the patched binary is the one being proposed and the first result predates the patch.

- As pushed, 2 devices: **rc=0**, 458 OK rows, every Meta row OK or SKIP.
- **With the LI dispatch, 2 devices: rc=0, 458 OK rows, no failures.** Unchanged.
- All four devices visible: **aborts**, but at the policy stop, not a bug —
  `llama-model.cpp:818: cannot tensor-split blk.0.attn_q.weight: segment 0 has only 2 splittable
  units for 4 devices`. The synthetic archs have `head_count_kv = 2`; this is the rule working.
  Worth knowing that the suite is not runnable as-is on a >2-GPU box.

## Internal AllReduce is unavailable on Pascal, and the warning blames the wrong thing

Every **tensor** arm logs (and no layer arm does — 0 occurrences in both layer-split logs):

```
W internal AllReduce init failed (n_devices != 2?); falling back to meta-backend butterfly
```

even with exactly 2 devices visible and `GGML_CUDA_ALLREDUCE=internal` set. The parenthetical is a
guess in the source, and on this hardware it is the wrong guess. Re-running at `-lv 5` shows the
real reason one line above, at DEBUG:

```
D ggml_cuda_ar_pipeline_init: internal AllReduce requires compute capability >= 700
                              (device 0 has cc=600); falling back
W internal AllReduce init failed (n_devices != 2?); falling back to meta-backend butterfly
```

`allreduce.cu:404` — the chunked kernel uses `__nanosleep`, which is sm_70+. P100 is sm_60, so
`ggml_cuda_ar_pipeline_init` returns `nullptr` on the compute-capability check, never on the
device count.

Two consequences:

1. **`GGML_CUDA_ALLREDUCE=internal` is inert on the entire P100 fleet.** Every tensor-split run we
   have ever done on Pascal used the meta-backend butterfly. The env var has been pinned in our
   harnesses on the assumption it did something; it does not, and cannot, on sm_60.
2. The only message visible at default verbosity states a cause that is false here, and the true
   cause is DEBUG-only. Worth surfacing in the WARN.

I have full server logs only from today, so I cannot say whether this predates `85eb0596a` — the
earlier ladder logs are 8-line summaries. It is not a regression claim.

## Not claimed

**No throughput number from these runs.** AFM-28: the multi-GPU arm on this NUMA-unbound dual-Xeon
box is bistable (12.80 / 12.56 / 15.83 / 15.75 on one binary and one set of flags). The 1.6 t/s
figures in the logs are single samples on a 1-bit 77 GB model with 40 MoE layers on CPU and are
recorded only as evidence that generation happened. Correctness only.


## Run hygiene — a lingering process, checked rather than assumed

The `clean_4dev` server ignored the harness's `SIGTERM` and stayed alive for 21 minutes, through
the uneven arm and the layer control, holding **280 MiB on each of the four GPUs**. It needed
`kill -9`. Two consequences, both checked rather than assumed:

- **Did my prompts reach the right process?** Yes. Each arm's own log records
  `listening on http://127.0.0.1:8087` under its own PID (3828816 / 3907433 / 3989328 / 4082979),
  so each bound the socket itself. Independently: at temperature 0 the arms return *different*
  text for the same prompt (`Paris. It is the largest city in France, with a population of over
  2 million` on 4-dev even vs `Paris. It's famous for its historical monuments` on uneven), which
  they could not if both sets of curls had been answered by one process.
- **VRAM figures for the uneven and control arms are inflated by ~280 MiB per device.** The even
  arms are clean. This does not affect any correctness conclusion, and the uneven ratio observation
  above is unaffected in direction, but the absolute numbers carry that tax.

The harness now needs to *verify* the kill rather than fire and sleep — `pkill` returning is not
evidence the process died. Same shape as AFM-27: an action that returns is not an action that
took effect.

## Prediction scoring

Registered in `PREDICTIONS_85eb0596a_DS4.md` before any run. All arm predictions were written
against **the head as pushed**; the LI dispatch was not foreseen.

| # | arm | predicted | conf | actual | score |
|---|---|---|---|---|---|
| 0 | `-sm layer` baseline coherent | yes | 0.97 | yes | ✅ |
| A | `-sm tensor -ts 1,1` completes | yes | 0.70 | **no** — `:1035` LIGHTNING_INDEXER | ❌ |
| A2 | arm A output coherent | yes | 0.55 | yes (with dispatch) | ✅ |
| B | 4 dev even completes | yes | 0.45 | yes (with dispatch) | ✅ |
| C | 4 dev uneven completes | yes | 0.30 | yes (with dispatch) | ✅ |
| D | `test-llama-archs` sm_60 pass | yes | 0.90 | yes at 2 dev; policy stop at 4 | ✅ |

Two things I got wrong and one I got right for the wrong reason:

- **A falsified.** I predicted the memset implementation might not survive all five of its code
  paths. It survived every one; what stopped the run was an op that had never been dispatched at
  all. I was watching the code that had just changed instead of the code that had never been
  reached.
- **C badly underconfident (0.30).** I anchored on the `:1038` divisibility assert from
  `c232282aa` and did not check whether the intervening five heads had made it unreachable. A
  failure mode from an old head is not evidence about a new one unless something still points at
  it.
- **A2 at 0.55 was the right instinct** — coherence deserved its own number, separate from "does
  it run" — but the reason I gave (kernels might get the wrong slice) was not what made it close.
  What nearly cost me a false bug report was the *uneven* arm's repetition, which needed a control,
  not a lower prior.
