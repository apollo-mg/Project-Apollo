# Speculative decoding does not reproduce non-speculative output on this stack

**2026-08-15, RX 9070 XT (RDNA4, ROCm), `moe-cache-test` HIP build.** Target
`Qwen3.5-9B` `Q8_0` (unsloth MTP variant), `-ngl 99 -c 8192 --jinja`, temperature 0,
`top_k 1`, `seed 1234`, one prompt (`code`), `n_predict 320`. Raw: `raw/`.

## The claim being tested

Verify-and-reject speculative decoding is described everywhere — including in our own
`qwen38-splitmode/NOTE_PRECISION_VS_SPECULATION.md` — as **lossless by construction**:
rejected drafts are discarded, so the output is what the target would have produced anyway,
and a worse drafter costs speed and nothing else.

At temperature 0 with `top_k 1` that predicts a strictly testable thing: speculative output
should be **bit-identical** to non-speculative output. It is not.

## Result

Same prompt, six runs per condition, SHA-256 of the full response (content + reasoning):

| condition | distinct outputs | hash | chars | draft n/accepted | vs `off` |
|---|---:|---|---:|---|---|
| `off` | **1** | `829016f4` x6 | 1284 | — | reference |
| `mtp_n3` | **2** | `62b80194` x3 | 1284 | 308/216 | **differs** |
| | | `06ad1b1c` x3 | 1279 | 296/219 | **differs** |
| `dfl_n3` | **1** | `06ad1b1c` x6 | 1279 | 275/227 | **differs** |

**Three findings, in order of importance.**

### 1. Neither drafter ever reproduced the non-speculative output — 0/6 and 0/6

Not "usually matches". Never matched, in twelve speculative runs. The unspeculated baseline is
itself perfectly stable (6/6 identical), so this is not a noisy control.

### 2. DFlash's output is bit-identical to one of MTP's two

`06ad1b1c` appears in both arms. Two drafters with nothing in common — a 1-token-at-a-time
head that is a layer *inside* the target, and a separate 1.3 B masked-block denoiser with its
own context — converge on the same non-reference text.

That is the load-bearing clue. Independent floating-point noise in two unrelated drafters
would not land on the same alternative string. It points at the deviation being **target-side**:
both arms make the target verify a batch of *n+1* tokens where the baseline processes 1, and
GPU matmul kernels are not batch-invariant, so reduction order and therefore the last bits of
the logits depend on batch shape. Where two candidates sit inside the rounding margin, the
argmax flips, and from there the runs diverge permanently.

Under that reading the drafters are not the source of the deviation. The *presence* of
verification is.

### 3. MTP is additionally unstable run-to-run; DFlash is not

`mtp_n3` alternates between two outputs with different draft counts (308/216 vs 296/219);
`dfl_n3` produces one output with one draft count (275/227) every time. So there are **two
separate phenomena**, and the earlier `AFM-9` entry conflated them:

| phenomenon | MTP | DFlash | likely locus |
|---|---|---|---|
| deviates from non-speculative | yes | yes | target verification batch shape |
| varies between identical runs | **yes** | **no** | drafter-specific |

Hypothesis for the second, untested: the MTP head is `blk.64` of the target — it reads the
target's hidden states and shares its KV cache, so rejected drafts must be rolled back out of
that shared cache and the head's own inputs sit downstream of the batch-shape variation.
DFlash is an external model with its own `ctx_dft` and its own cache, and it denoises a
constant-size block of 16 regardless of what was accepted — constant shape in, constant
arithmetic out. If that is right, **DFlash's stability is a property of being an external
fixed-shape drafter, not of diffusion**, and any external drafter should show it. Not tested.

## Corrections this forces

- **`qwen38-splitmode/NOTE_PRECISION_VS_SPECULATION.md`** states losslessness is "a property
  of the method, not an achievement" and concludes "a worse draft head costs speed and nothing
  else. None of this measures model quality, because it cannot." **The second half is
  falsified on this stack.** Draft configuration demonstrably changes output text.
- **`qwen35-drafters/RESULT_MTP_VS_DFLASH.md`** states flatly "It is **lossless**." Needs the
  same qualification: lossless in distribution under exact arithmetic, not bit-exact in
  practice here.
- **`FAILURE_MODES.md` AFM-9** recorded the MTP/DFlash asymmetry from draft *counts* only. The
  entry was right about the asymmetry and wrong about what had been measured — text was never
  compared until now.

The distinction that survives: the losslessness theorem is about the output **distribution**
under exact arithmetic. It is not a claim of bitwise reproducibility on a real GPU, and at
greedy decoding those two come apart.

## Magnitude: real, early, and confined to docstring prose

A second run retaining full text (4 reps per condition) reproduced the same three hashes and
locates the divergences. Both are **early** — around character 155–226 of a 1284-character
response — which fits an argmax flip at a single position rather than drift accumulating over
the generation.

**Variant `62b80194` (MTP only) — pure whitespace reflow.** Similarity 0.9930, identical
length. The entire difference:

```
ref : '\n    item'
alt : ' item\n   '
```

A docstring line wrapping after "used" instead of before "item". Same words, same code.

**Variant `06ad1b1c` (MTP and DFlash) — a shorter docstring.** Similarity 0.9107. It omits two
sentences from the class docstring:

```
ref : "The cache maintains a fixed capacity and evicts the least recently used
       item when the capacity is exceeded."
alt : (absent)
```

That is a genuine content difference — the model wrote something different, not merely wrapped
it differently — but it is explanatory prose, not logic.

**Stripping docstrings and whitespace, `62b80194` is byte-identical to the reference** (751
chars of code both). `06ad1b1c` is not (724 vs 751), **but that comparison is confounded**: by
spending ~118 fewer characters on the docstring it reaches further into the class within the
same 320-token budget, so both responses are truncated at different points in the program. The
shortfall is a truncation artefact, not different code.

**So the calibrated claim is: speculation changed the output, and in this sample the change is
confined to docstring prose.** The algorithm was unaffected everywhere it was generated. That
tempers — but does not remove — the correction below: it establishes that draft configuration
changes *what the model emits*, and does **not** establish that it changes quality. Asserting
the latter would need a benchmark and a completion-length budget, neither of which this test
has.

## What this does NOT establish

- **One prompt, one model, one build, one GPU.** No claim about generality.
- **This may be a fork artefact.** The build is `moe-cache-test`, turboquant-derived. Whether
  stock upstream `llama.cpp` reproduces this is unknown and is the obvious next test — if
  stock is bit-exact, this is a bug worth reporting rather than a property of the method.
- **Responses are truncated at `n_predict=320`.** No claim that the *complete* programs would
  be identical; the test cannot see past the budget. A completion-length rerun is the obvious
  strengthening, and is what a quality claim would require.
- **One prompt of one kind.** `code` was chosen because it was the cell most likely to
  separate the arms. Prose or tool-calling might diverge more, less, or differently.
- **Nothing here says which output is "right".** Non-speculative is the reference by
  convention, not by correctness. All three may be equally good answers.
- **Not a quality claim.** That speculation changes the output does not mean it degrades it.
  Measuring that needs a benchmark, not a hash.

## Why it matters anyway

Every published speculative-decoding speedup — ours included — carries an implicit "and the
output is unchanged". On this stack that is false at the level a user could actually observe:
run the same prompt twice at temperature 0 with MTP on and get two different programs. For
reproducible evaluation the practical rule is that **the speculative configuration is part of
the experimental condition and must be recorded**, exactly like the quantization and the KV
cache type already are. A benchmark that changes `--spec-type` between arms is not running the
same model.
