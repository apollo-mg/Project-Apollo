# Pre-registered predictions — DS4 tensor split on `85eb0596a`

Registered **2026-08-30**, before any run on this head. `.194`, 4x P100 sm_60 @ 150 W / 1063 MHz,
`DeepSeek-V4-Flash-0731-UD-IQ1_S`, `GGML_CUDA_ALLREDUCE=internal`.

Head `85eb0596a` contains (a) the AXIS_2 x AXIS_2 mul_mat rule I proposed, generalised by Tom to
`axis >= AXIS_2 && axis < GGML_MAX_DIMS`, and (b) a full `memset_tensor` for the Meta buffer,
which was the exact stop on `4b0e2ee98` + my local rule.

> **Provenance correction, 2026-09-02.** That AXIS_2 rule was **already upstream** — present in
> `spiritbuun/buun-llama-cpp` via an upstream sync dated 2026-07-06, seven weeks before I proposed
> it. Tom said as much when he took it (*"matches the upstream DS4 implementation"*), so nothing
> was misrepresented to him, but "the rule I proposed" reads as novelty and was not. Turboquant
> lacked it only because that fork diverged from upstream before it landed. The `LIGHTNING_INDEXER`
> dispatch IS genuinely ours — absent from upstream-synced trees too.
> See `RESULT_BUUN_MASTER_COMPARISON.md`.


## Arms

Flags held byte-identical to the prior ladder rows: `-ngl 99 -c 8192 -fit off -fa on -ncmoe 40
-np 1`. Only `-sm` / `-ts` / visible devices vary.

| # | arm | prediction | confidence |
|---|---|---|---|
| 0 | `-sm layer`, 2 dev — **coherence baseline** | coherent | 0.97 |
| A | `-sm tensor -ts 1,1`, 2 dev | reaches ready **and** completes a prompt | 0.70 |
| A2 | arm A output coherent vs baseline | coherent | 0.55 |
| B | `-sm tensor -ts 1,1,1,1`, 4 dev | reaches ready and completes | 0.45 |
| C | `-sm tensor -ts 3,4,4,1`, 4 dev | reaches ready and completes | 0.30 |
| D | `test-llama-archs` on sm_60 | pass | 0.90 |

## Reasoning behind the numbers

**A at 0.70, not higher.** The memset implementation is the right shape and Tom ran the test
suite, but on `4b0e2ee98` the assert fired at *first prompt*, i.e. one call through one branch.
The new code has five distinct paths (segmented axis-0, segmented axis-1, the contiguous
AXIS_0/1/2 switch, PARTIAL, MIRRORED). DS4's recurrent compressor + HCA/CSA + lightning-indexer
state is the widest variety of buffer shapes any arch has pushed through here.

**A2 at 0.55 — deliberately lower than A.** Clearing the split-state phase and the memset phase
means the *bookkeeping* is consistent; it does not mean every kernel got the slice it expected.
Flash-Next produced fluent `////` while nominally running. Coherence is a separate claim and
gets a separate number.

**B at 0.45.** Genuinely open. The `head_count_kv` rule does **not** apply — DS4 is MLA and never
reaches the GQA path; its own MIRRORED/paired patterns govern. So the 4-device question is not
answered by anything measured so far, in either direction.

**C at 0.30, below B.** Uneven `-ts` has its own documented failure independent of device count:
on `c232282aa` it aborted at `:1038 GGML_ASSERT(split_state.ne[j] % div == 0)` — *earlier* than
the even arm. Nothing in this head's diff addresses divisibility of a granularity unit across an
uneven ratio.

## Falsifiers stated in advance

- If A aborts, the failure is a **memset branch**, not the mul_mat rule — the mul_mat rule already
  passed on `4b0e2ee98` locally.
- If A completes but the text is degenerate (repeated token, punctuation runs, non-sequitur where
  the baseline is fine), that is a **numerics** failure, and the split-state work is complete
  while the kernels are not. Report as such; do not call it "working".
- If C fails at `:1038` and B passes, report as a **granularity/divisibility** issue, explicitly
  NOT as "4 devices don't work".

## Not being claimed from this run

**No throughput number.** AFM-28 (one day old): the 4-GPU arm on this NUMA-unbound dual-Xeon box
is bistable, 12.80 / 12.56 / 15.83 / 15.75 on the same binary and flags. A single sample here
would repeat exactly the error Mark caught. Correctness only.
