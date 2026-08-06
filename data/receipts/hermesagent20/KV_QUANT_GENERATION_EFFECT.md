# Does KV quantisation change what the Architect says? — 9070 XT, generation path

Control plane, RX 9070 XT (gfx1201). Engine `llama_cpp_turboquant` (TheTom, v9971
`c26cbdffc`), no compatibility hacks. Model `Qwopus3.5-27B-v3-Q2_K.gguf`, ctx 8192.
Date 2026-07-28.

## Prompt for the test

r/LocalLLM, 2026-07-28, "Thank you, whoever said don't quant the KV" (90 up / 50 comments):
claims dropping q8_0 KV on Qwen3.6-27B was *"night and day"*. Evidence offered is an
impression.

Our KLD panel disagrees on its own terms — q8_0 is the **gentlest** codec measured, and
**depth-invariant**:

| ctx | q8_0 same-top | turbo8 | turbo4 | turbo2 |
|---|---|---|---|---|
| 2048 | 98.674 | 98.528 | 96.786 | 91.386 |
| 8192 | 98.757 | 98.708 | 96.970 | 92.059 |
| 16384 | 98.677 | 98.637 | 96.732 | 91.743 |
| 32768 | 98.743 | 98.659 | 96.665 | 91.086 |

But that panel is `llama-perplexity`: teacher-forced, all prefill, matched K=V, wikitext. The
Reddit claim is about **generation**. Today's decode work showed the two do not map onto each
other — turbo8 (98.659 % same-top) produced byte-identical generation over 6000 tokens, an
event with ~1e-11 probability under per-token agreement. So the panel cannot settle this.

## Design

Greedy decode (temp 0, top_k 1), identical 594-token prompt, `cache_prompt=false`, `-np 1`,
2 runs per arm for self-consistency, 1200 tokens generated.

- **Arm F**: `-ctk f16 -ctv f16` (reference)
- **Arm Q**: `-ctk q8_0 -ctv q4_0` — **exactly** what `scripts/startup/start_architect.sh`
  serves in production

Arm Q's KV is **asymmetric with a 4-bit V side**, which the panel never tested (matched K=V
only). It is therefore uncharacterised by any prior measurement here.

## Results

| arm | sha | chars | tok/s |
|---|---|---|---|
| f16 run0 | `94b081c14224` | 4704 | 31.95 |
| f16 run1 | `94b081c14224` | 4704 | 31.79 |
| q8q4 run0 | `2e3d3beb4326` | 4687 | 24.27 |
| q8q4 run1 | `2e3d3beb4326` | 4687 | 24.32 |

Both arms self-consistent (byte-identical run-to-run), so the comparison floor is zero and
the difference between arms is attributable to the KV codec.

### 1. Output diverges almost immediately

**First divergence at char 73 of 4704** — roughly 20 tokens into generation.

```
f16 : ...In 2003 he       appeared in the television series Doctors as " Mark " in
q8q4: ...In 2003 Boulter  appeared in the television series Doctors as " Mark
```

The divergence point is a **coreference choice** — pronoun vs proper noun — which is exactly
the kind of near-tied decision where a small numeric perturbation flips the argmax. Both
continuations are grammatical and factually consistent.

**Divergence is not degradation.** This measures that the outputs differ, not that one is
worse. Nothing here supports "night and day" in quality terms, and nothing here refutes it
either — quality was not measured.

Contrast with `.73`: matched turbo8 (8.125 bpv both sides) gave byte-identical generation for
6000 tokens, while q8_0 K + **q4_0 V** diverges at token ~20. The asymmetric 4-bit V side is
the plausible difference, and it is the one thing the panel never covered.

### 2. Quantised KV is 31 % SLOWER than f16 here

31.87 tok/s (f16) vs 24.30 tok/s (q8q4) — f16 is **1.31× faster**, consistently across both
runs of each arm.

At ctx 8192 on a 16 GB card, KV quantisation is buying VRAM that is not needed and paying for
it in **both** throughput and fidelity. The dequantisation cost on every attention op is not
recovered by anything at this context size.

## Actionable

The Architect currently runs `-ctk q8_0 -ctv q4_0` at `-c 65536`. The quantisation exists to
make 64k context fit. That trade is real at 64k — but if typical working context is well
under that, switching to `-ctk f16 -ctv f16` at a reduced `-c` would be **faster and closer
to reference simultaneously**. Worth measuring where f16 KV stops fitting on 16 GB with this
model, then setting `-c` just under it.

## Caveat to an earlier claim

`RDNA4_ARCHITECT_DETERMINISM.md` states `--cache-ram 0` closes prefix-cache reuse. Server logs
here show **context checkpoints are still active** (`created context checkpoint 1 of 32`,
149.626 MiB each, plus `erased invalidated context checkpoint` events). That is a separate
state-carrying mechanism from the prompt cache — on `.73` it was the `vbr_nockpt` hypothesis
(`--ctx-checkpoints 0`, `--slot-prompt-similarity 0`). It did not produce nondeterminism in
either measurement (5/5 and 2/2 byte-identical), but the claim "two of three channels closed"
understated what is still live. Corrected here.

## Limits

- One prompt, one model, ctx 8192. Not a quality evaluation.
- Does not decompose q8_0-K from q4_0-V. A `q8_0`/`q8_0` arm would isolate whether the 4-bit V
  side is responsible, and is the obvious next test.
- Speed figure is this engine on this card; it does not generalise to CUDA backends.

## Provenance

`~/projects/HermesAgent-20/kv_generation_effect.sh`, results in
`~/projects/HermesAgent-20/kv_generation/`
