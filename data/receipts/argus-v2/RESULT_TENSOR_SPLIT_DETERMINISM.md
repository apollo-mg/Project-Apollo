# Result -- `-sm tensor` is deterministic on `.73`, after one warmup request

**2026-09-20, `.73`** (2x Tesla P100, sm_60). Gate defined in `argus/CORPUS_DESIGN_v2.md`:
decide the corpus v2 split mode by measurement rather than caution, because `-sm tensor` is
measured at >1.6x on this fleet and a ~30 h campaign would save ~11 h.

## Configuration

Live daily-driver server, unmodified: `Qwen3.8-27B-Q6_K.gguf`, `-sm tensor`, `-ngl 99`,
`-c 262144`, `-ctk vbr -ctv vbr`, port 8080, reached through the wake proxy on 8099 so every
request registered as activity and the node could not suspend mid-gate.

Card sampling, fixed seed, single turn, `enable_thinking: false`:

```
temperature 1.0   top_p 0.95   top_k 20   seed 12345   max_tokens 300
```

**Prompt chosen for ENTROPY, deliberately.** A first attempt used "list five primes over 100",
which returned 24 tokens and would have been identical under any perturbation -- the model is far
too confident there for reduction-order noise to flip a token. A confident task cannot detect
this class of defect. The gate uses open-ended prose at temp 1.0, where the next-token
distribution is flat, a single logit wobble flips a token, and the divergence then compounds.

## Result

| | n | distinct outputs |
|---|---:|---:|
| **first request after load** | 1 | -- (`c3c0c996b4d0955d`) |
| **every request after it** | **24** | **1** (`eda9903162a01d4f`) |

**24 consecutive byte-identical generations.** VERDICT: **`-sm tensor` is deterministic on this
node under seeded card sampling, once warm.**

The first request differs and differs informatively: it consumed **300 tokens and stopped on
`length`**, where all 24 later runs stopped naturally at **299 on `stop`**. It genuinely
diverged, at character 123, then produced a different continuation:

```
run 1  : ... curled strips like dried skin. Rust, the color of dried ...
runs 2+: ... curled strips like dried skin. Rust eats into the iron ...
```

**Prefix caching is NOT the explanation.** `cached_tokens` is **0 on all 25 requests** -- the
34-token prompt was fully re-prefilled every time, so the cache never engaged and cannot account
for run 1. The residual candidates are first-execution effects at that tensor shape: kernel
selection/autotune, lazy allocation, or VBR KV buffer initialisation.

## What this does and does not establish

**Establishes:** on `.73`, 2-GPU tensor split, single-turn, thinking off, seeded, warm -- the
implementation does not have timing-dependent reduction. 24/24 is the same bar the original
temp-0 determinism receipt cleared (15/15).

**Does NOT establish, and each of these is a real gap:**

1. **`.194`.** A determinism PASS does not transfer across device count -- `FINDING_INSTRUMENT_VERSION`
   showed a verdict flip between 2 and 4 GPUs from layer split and reduction order alone. A FAIL
   here would have transferred (and would have ended it cheaply); a pass does not. **The campaign
   box needs its own gate.** If the campaign runs 2-GPU partitions of `.194`, that is at least the
   same split arity, so only topology differs.
2. **Campaign conditions.** Tested single-turn with thinking OFF. The campaign is multi-turn,
   tools active, thinking ON, `preserve_thinking` default. Different code paths.
3. **Prefix caching, specifically.** `cached_tokens` was 0 throughout, so the cache path was
   **never exercised**. A real agentic run hits it constantly. Determinism under cache reuse is
   untested and is the likeliest place for this result not to hold.
4. **No `-sm layer` control.** Whether the first-request effect is tensor-specific or general is
   unknown; testing it means restarting the daily driver. The mitigation is identical either way,
   so this was left undone deliberately rather than overlooked.

## The operational finding, which generalises

**Discard a warmup request after every model load.** This sharpens the existing rule that server
uptime is a variable: restarting before each benchmark leg is necessary but not sufficient, because
the first request after the restart is itself unreliable. One throwaway generation, then measure.

Had the gate run at K=2 -- and K=2 was the number I would have reached for before thinking about
it -- it would have read 1 of 2 differing and scored `-sm tensor` NOT DETERMINISTIC, discarding a
1.6x speedup on a warmup artifact. The K=15 floor was specified precisely because timing-dependent
reduction is flaky rather than consistently broken; it caught the opposite error.

## Recommendation

**Provisionally adopt `-sm tensor` for corpus v2, conditional on the `.194` gate passing under
campaign conditions** (multi-turn, tools, thinking on, prefix cache warm). Add a discarded warmup
request to the harness's per-leg startup. If the `.194` gate fails, fall back to `-sm layer` and
accept the ~11 h.

## Artifacts

`tp_det.sh` (the gate), `det_tensor_batch1.jsonl` / `det_tensor_batch2.jsonl` (25 raw responses,
hashes and finish reasons).
