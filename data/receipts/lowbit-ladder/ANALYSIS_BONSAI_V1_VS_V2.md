# Analysis -- what actually changed between Bonsai v1 and Bonsai 2, from the artifacts

**2026-09-19, written while the Bonsai cells were still queued.** Prompted by Mark's question:
*"why did the formula and whatever they learned AFTER Bonsai 28B v1's release, not seem to transfer
over to Qwen 3.8... wonder if it was a rushed release, something they couldn't replicate."*

Everything below is read directly from GGUF metadata of files on this machine. No speculation is
presented as measurement.

## First: the KLD measurement is valid

Checked before drawing any conclusion, because if Bonsai 2 were a quantisation of a *different*
base model, its KLD against our Qwen3.8-27B reference would measure model difference, not codec
error, and the whole Bonsai arm would be meaningless.

| check | reference (Qwen3.8-27B Q8_0) | Bonsai 2 PQ2_0 |
|---|---|---|
| core tensors present | 851 | **851, zero shape mismatches** |
| vocab size | 248,320 | 248,320 |
| embedding_length / feed_forward_length | 5120 / 17408 | 5120 / 17408 |
| attention heads / kv heads / key len | 24 / 4 / 256 | 24 / 4 / 256 |
| ssm inner / state / groups / dt rank | 6144 / 128 / 16 / 48 | identical |
| rope base / sections | 1e7 / [11,11,10,0] | identical |
| block_count | 65 | 64 *(no MTP layer)* |
| nextn_predict_layers | 1 | absent *(no MTP head)* |

**Shape-identical on every core tensor.** The only differences are the absent MTP head, already
accounted for in the scored-bytes method. The Bonsai cells measure quantisation error.

## The question is mis-framed, and that is the useful part

**Bonsai v1 has the same architecture fingerprint as Bonsai 2** -- same 5120 embedding, 17408 FFN,
64 blocks, 248,320 vocab, identical SSM and RoPE parameters. So this is **not** a case of a method
developed on one model failing to carry to a different one. The architecture did not change.
**The method did.**

## What changed, from metadata alone

| | Bonsai v1 | Bonsai 2 |
|---|---|---|
| quant type | 42 | 142 (PQ2_0) / 143 (PTQ1_0) |
| quantised tensors | **498** | **402**, plus **96 at BF16** |
| Hadamard rotation | **absent entirely** | 401 tensors |
| effective bpw | ~2.23 | 2.12 (PQ2_0) / 1.75 (PTQ1_0) |
| `general.name` | `Bonsai-27B` | **`Hf`** |
| `general.basename` | absent | `folded` |
| `general.version` | absent | `v5` |

**402 + 96 = 498, exactly.** v2 operates on the same tensor set v1 quantised, but re-allocates
precision: 96 tensors move *up* to BF16 while the remaining 402 are pushed *down* to 1.75-2.13 bpw.
A deliberate re-allocation, not a rewrite.

The full rotation configuration in v2:

```
prism.hadamard.transform             normalized-sylvester-walsh-hadamard
prism.hadamard.block_size            1024
prism.hadamard.axis                  input-last-dimension
prism.hadamard.sign_mode             explicit      (28,672 sign values)
prism.hadamard.sign_widths           [5120, 6144, 17408]
prism.hadamard.weight_names          401 tensors
prism.hadamard.inverse_weight_names  ['token_embd.weight']      <-- exactly one
prism.hadamard.gdn_v_grouped         True
```

## Leading hypothesis: the rotation had to be special-cased for Gated Delta Net

`qwen35.ssm.*` is present throughout: this architecture uses a **Gated Delta Net**, i.e. linear
attention / SSM machinery, not plain transformer attention. `gdn_v_grouped = True` is direct
evidence that the rotation scheme required a **bespoke special case for GDN's V projection**.

Hadamard rotation schemes work by cancellation: rotate a weight by `R` and something downstream by
`R^T` so the product is unchanged in exact arithmetic while the intermediate distribution becomes
easier to quantise. Note the asymmetry here -- **401 forward rotations against exactly one inverse
(`token_embd.weight`)** -- an absorb-into-the-embedding design whose correctness depends on every
downstream consumer handling the rotated basis correctly.

**If the GDN grouping is subtly wrong, the result is a model that is fluent but degraded in
judgement** -- which is exactly what the public reports describe (planning without emitting,
deleting its own work, declaring "verified" falsely), and exactly the kind of damage a
next-token-distribution distance over wikitext may under-report. See
[[EXTERNAL_OBSERVATION_2026-09-19]].

**This is a hypothesis with a named mechanism, not a diagnosis.** It is consistent with the
evidence and it is not established by it.

## Signals consistent with a rushed release

`general.name` is literally **`"Hf"`** -- the placeholder a conversion script emits when reading a
generic HuggingFace directory. v1 carried a deliberate `Bonsai-27B`. With `basename: folded` and
`version: v5`, the v2 artifacts read as pipeline output that nobody curated. That is weak evidence
about process, not about quality, but it is consistent with Mark's reading and it is what the file
actually says.

## Why causal attribution is impossible here, and what still is possible

**Four things changed simultaneously:** quantisation type, rotation, precision split, and target
bpw. Nothing in the artifacts can attribute a regression to one of them. Anyone claiming to know
which, from the files alone, is guessing.

**P-L5 is the one clean cut available.** B-PTQ1 and B-PQ2 are declared to hold the *same* ternary
weights and are verified identical at the header level -- same 851 tensors, same 402/353/96 split,
identical `prism.hadamard.*` configuration, differing **only** in container type 143 vs 142. Their
mean KLD must therefore agree to within the reproducibility floor.

| P-L5 outcome | what it isolates |
|---|---|
| **agree** (<1e-4) | both packings decode correctly. The regression, if any, lies in the *rotation or the recipe*, not in a container. |
| **disagree** | one packing has an **implementation defect**, independent of rotation and recipe. Directly actionable and reportable upstream. |

That is a narrow question, but it is the only one these artifacts can answer cleanly, and it costs
one already-downloaded file and about seventeen minutes.
