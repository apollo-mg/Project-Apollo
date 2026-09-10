# Loss of prompt-cache reuse under `-sm tensor` is specific to buun's fork

**Date:** 2026-09-07 · **Node:** `.73`, 2× Tesla P100 (sm_60) · Raw: `.73:~/forkcache.log`, `~/fc_*.log`

Third receipt in this directory. `RESULT_TENSOR_SPLIT_BREAKS_BINDING.md` found the VBR
artifact store failing to bind under tensor split; `RESULT_TENSOR_SPLIT_BREAKS_ALL_CACHING.md`
showed f16 and q8_0 lose reuse there too. This one asks whether that is upstream behaviour
that buun inherited, or buun's own.

## Result

All three forks expose `-sm {none,layer,row,tensor}`, so this compares `tensor` to `tensor`.
Identical 4,010-token prompt sent twice per arm, one model, one node, minimal flag set common
to all three binaries: `-ngl 99 -c 32768 -np 1 -fa on -ctk f16 -ctv f16`. No `--cache-ram`,
no `--kv-unified`, no `-fit`, no VBR — portability over continuity with the earlier matrix.

| fork | version | `-sm tensor` pass 2 | `-sm layer` pass 2 |
|---|---|---|---|
| upstream | `0.1.1-dev` build 1, `34af94c` | **4 tok / 105.86 ms** | 4 tok / 84.80 ms |
| llama-cpp-turboquant (Tom) | `205`, `f6124e9` | **4 tok / 89.18 ms** | 4 tok / 94.92 ms |
| buun-llama-cpp | `0.3.0-dev` build 979, `c9c52d71` | **4010 tok / 4522.31 ms** | 4 tok / 51.17 ms |

Five of six cells reuse the prefix. The sole failure is buun + tensor. Every arm started and
served; no arm errored or fell back.

Pass-1 prefill differs across forks (upstream 1131 t/s, Tom 886, buun 889). Not the subject
here and not controlled for — different feature sets and build dates. Do not read it as a
performance comparison.

## The caveat that keeps this from being conclusive

The upstream and Tom binaries were built **2026-08-17**. buun's tree merged upstream through
`0f3a71be` at `a71ca2fd2`, i.e. **after** that date. So this does not exclude the possibility
that a post-2026-08-17 upstream change broke tensor-split caching and buun inherited it —
in which case Tom's fork would also break once he rebases, and upstream is the right place
to look.

**Resolved by the bisect below**, which does not need a fresh upstream build: buun's own
Aug 25 binary is already broken, a week before the Sep 2 sync. An inherited post-Aug-17
upstream regression cannot explain a failure that predates the merge that would have
carried it.

What the matrix does establish: **the failure is not intrinsic to tensor split on sm_60, not
intrinsic to this model, and not intrinsic to two-GPU P100s** — three binaries on the same
hardware disagree.

## Bearing on the earlier receipts

Neither prior receipt is affected. The binding failure and the all-codec reuse failure are
both reproduced on `c9c52d71` exactly as recorded. This adds only that upstream and Tom's
tree, at their August builds, do not share the behaviour.

## Bisect within buun's own tree

Three buun builds already resident on `.73`, same protocol, `-sm tensor`, f16 KV.
No rebuilds — these binaries were on disk from earlier campaigns. Raw: `.73:~/buunbisect.log`.

| build date | version string | pass 2 |
|---|---|---|
| 2026-07-26 | `10442 (a8e5b5a38)` | **516 tok / 637.87 ms** — reuses 3,494 of 4,010 |
| 2026-08-25 | `531 (e332b24)` | 4010 tok / 4508.56 ms — no reuse |
| 2026-09-06 | `0.3.0-dev build 979, c9c52d71` | 4010 tok / 4526.25 ms — no reuse |

**The regression window is 2026-07-26 → 2026-08-25, inside buun's tree.** That is a month
before the `a71ca2fd2` upstream sync of 2026-09-02, which removes the "inherited a
post-2026-08-17 upstream regression" explanation raised above. The Aug 17 upstream binary
caches correctly and buun's Aug 25 build does not.

The July build's 516-token pass 2 is partial reuse, not a clean 4 — most likely checkpoint
granularity rather than a defect. Recorded as measured; not investigated.

`a8e5b5a38` is not present in the local clone, so the window cannot be enumerated from here
— buun rewrites history (cf. the `97474a38b` squash). The Aug 25 build's own HEAD is
`e332b2494 "dflash: harden checkpoint rewind lifecycle"`. Checkpoint/rewind is the machinery
this bug lives in, and the 27B divergence line from 2026-09-06 reports `rewind=3, append=0`.
That is a suggestive name, not evidence — it names the build boundary, not a culprit commit.

**Narrowing further requires builds at intermediate commits, which is buun's history to
walk, not ours.**
