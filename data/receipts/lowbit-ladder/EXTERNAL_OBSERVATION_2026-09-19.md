# External observation logged mid-experiment: a public report on the P-L2 pair

**Logged 2026-09-19, while the P-L0 gate was still running and before a single ladder cell had
produced a number.** Recorded here, with that timing stated, so it cannot later look like a
prediction shaped by evidence.

## What arrived

Alexey Fateev (@superalesha) posted a user report attacking the "98.2% of Qwen3.8 27B" claim made
for Bonsai. Summarised, not quoted at length:

- He ran an agentic coding job (a three.js FPS) for 6 hours on a 3090. It spent ~32K tokens
  planning without writing a file, then produced a black screen, two shaders that do not compile,
  and a player that spawns dead -- and wrote "verified" in its own final report.
- A much easier task (a voxel pagoda garden in one HTML file) took 3 hours, during which it
  deleted its own file and spent an hour debugging a raycaster nothing had asked for.
- The **same base model, same task**, using **ISTA-DASLab GSQ-RCO IQ2_XS** on a 12 GB 3080 Ti,
  succeeded: real shadows, working scene. He reports 8.4 GB on disk, ~2.50 bpw, 131072 ctx with
  q4_0 KV, 47 tok/s at 128K.
- His conclusion: *2.5 bits beats 2.13 bits when the 2.13 is this bad*; with >= 12 GB VRAM, use
  GSQ-RCO.

## Why it matters here

This is **exactly the P-L2 pair**, from the outside:

| | his report | our cell |
|---|---|---|
| Bonsai container | PQ2_0, 2.13 bpw | **B-PQ2**, 2.13 bpw, 7.21 GB |
| GSQ-RCO | IQ2_XS, ~2.50 bpw, 8.4 GB | **G-IQ2XS**, 2.58 bpw, 8.77 GB |

**Our preregistered P-L2 predicts the opposite of his conclusion**: that Bonsai has the *lower*
KLD despite being 1.56 GB smaller and 0.45 bpw lower. That prediction stands exactly as written.
It is not amended, softened, or hedged in response to this post.

## The reason it is not a refutation (and not a confirmation either)

**The two measure different quantities, and the gap between them is the interesting part.**

- He measured **agentic task completion** over multi-hour sessions: planning, tool use, file
  management, knowing when to stop.
- The ladder measures **KLD over ~10,200 tokens of wikitext** against a fixed Q8_0 reference.

Nothing forces those to agree. This project has already measured a case where they did not: the
Puzzle-75B vs Laguna panel found the gap was **a stopping-rule failure, not an answering failure**
(`data/receipts/humaneval-plus/`). Every failure Fateev describes is that same family -- planning
without emitting, deleting its own work, chasing an unasked-for bug, and declaring "verified"
falsely. Those are behavioural and stopping-rule failures, which a next-token distribution
distance over wikitext is not designed to detect and has no particular reason to predict.

So there are three possible outcomes, and all three are worth having:

1. **KLD agrees with him** (GSQ lower) -- P-L2 is falsified, and cheaply.
2. **KLD disagrees** (Bonsai lower, as predicted) -- then the finding is not "he is wrong", it is
   that **KLD on wikitext fails to predict agentic usability**, which is a more useful result than
   either number alone and would apply well beyond these two codecs.
3. They are within 5% -- P-L2 is falsified by its own stated margin.

## What it is not

A controlled comparison. It is a single-operator report, N=1 per arm, with unknown sampling
parameters, unknown chat template, unknown Bonsai build, and two different pieces of hardware.
That is not a criticism of him -- he is reporting use, not running a panel. It is the reason the
ladder is worth running: same model, same corpus, same reference, same binary per family, one
variable.

**No prediction in `PREREG_CODEC_LADDER.md` is modified by this post.**

---

## Addendum, same day, still before any cell result

Further reports arrived while the P-L0 gate was mid-run (gate reached chunk 17 of 40). Logged for
the same reason as above: all of it predates our first number.

**Corroborating reports on Bonsai 2:**

- @eplurubusnullus: lost trust in the releases, *"particularly after the first Bonsai 27B being so
  useful. This one's a dud."*
- @princeoithilien: matches his experience since the release -- basic math and coding, little more.
- Mark's own prior testing: **Bonsai v1 gave good results**, and he was surprised it did not carry
  over to the Qwen3.8 build.

**The discriminator this creates.** Three independent sources now say the same structured thing:
**v1 good, v2 bad, same team and same technique family.** That is evidence against "ternary
quantisation does not work" and evidence for "something is wrong with this particular port." A
method that worked once and fails on a new base model is the signature of an implementation
problem, not a fidelity ceiling.

**This is precisely what P-L5 is built to detect**, and it was preregistered before any of these
reports existed. B-PTQ1 (1.75 bpw, dense trits) and B-PQ2 (2.13 bpw, 2-bit slots) are declared by
the model card to hold the *same* ternary weights -- same 851 tensors, same `prism.hadamard.*`
keys. If both containers decode correctly, their KLD must agree to within the P-L0 floor, which
this gate is measuring at effectively zero. **If they diverge, one packing has a defect**, and
that is a concrete, reportable finding rather than a vote in a sentiment thread.

**What nobody in these threads has measured.** Every report is agentic task outcome. Not one is a
fidelity measurement against a fixed reference. The ladder is, as far as this record shows, the
only same-model same-reference quantitative comparison of these codecs -- which is what makes it
worth finishing even if it merely confirms what the crowd already believes.

**Note on the bit figures being quoted publicly:** the two containers are **1.75 bpw** (PTQ1_0)
and **2.13 bpw** (PQ2_0). The build most people are running and criticising is PQ2_0 at 2.13.

---

## Header evidence: what actually changed between Bonsai v1 and Bonsai 2

**Measured 2026-09-19, still before any Bonsai cell has run.** Both files are on this machine and
their GGUF headers were read directly.

| file | arch | tensors | tensor type histogram | `prism.hadamard.*` |
|---|---|---:|---|---|
| `Ternary-Bonsai-27B-Q2_g64.gguf` (**v1**) | qwen35 | 851 | 353 x F32 + **498 x type 42** | **absent** |
| `Ternary-Bonsai-2-27B-PTQ1_0.gguf` (**v2**) | qwen35 | 851 | 353 x F32 + 96 x BF16 + **402 x type 143** | **present** (version, block_size, transform, axis, sign_mode, weight_names) |

The v2 file matches the prereg's header description exactly (851 tensors, 402 quantised + 353 F32
+ 96 BF16, `general.architecture = qwen35`).

**The difference is not only the container.** v1 is type 42 with no rotation metadata whatsoever.
v2 introduces a **Hadamard-rotated basis** and a different quant type entirely. Three independent
sources report v1 as good and v2 as a dud; the rotation is among the things that changed between
them, and it is the part that requires new inference-side code rather than just a new unpacker.

This is a **hypothesis generated from file headers, not a result.** It is recorded now because it
is checkable and because it predates our measurements:

- If the regression were a pure fidelity cost of going lower-bit, KLD should degrade smoothly and
  **P-L5 should hold** (both v2 containers agreeing, since both carry the same rotated weights).
- If the rotation is implemented wrongly on the inference side, the damage need not be identical
  across the two containers, and **P-L5 would break** -- which is exactly the signal P-L5 exists
  to catch, and which no sentiment thread can produce.

It also connects to an earlier finding in `FINDING_TERNARY_Q2_0.md`: Atlas reads type 42 (Bonsai
v1) but does not read `prism.hadamard.*`, which is why v2 support there was never a one-line
change. The same boundary -- rotation metadata that older engines ignore -- shows up here as the
v1/v2 divide.

**Inventory correction to the prereg.** The prereg's "on disk" column is now backwards:
B-PTQ1 (1.75 bpw) **is** present at `/mnt/TG_2TB/AI/Models/bonsai2/`, 5,946,648,928 B, fetched
2026-09-19 09:24. B-PQ2 (2.13 bpw) is **not** on this machine under any name searched. P-L2 and
P-L5 both need it, so it remains to be fetched. This is an inventory note, not a change to any
prediction.

## B-PQ2 acquired; the P-L5 control pair is structurally confirmed

**2026-09-19 11:42.** `Ternary-Bonsai-2-27B-PQ2_0.gguf` fetched from
`prism-ml/Ternary-Bonsai-2-27B-gguf` (Apache 2.0), 7,206,168,928 B, sha256
`3907dc1658db1f78a9826bf8d5bcb8dc65db0d466388937af57f2294fae62ec1` -- **an exact match to the
hash `PREREG_CODEC_LADDER.md` recorded before the file was ever on this machine.** Provenance
(url, timestamps, byte count, hash) written to `FETCH_PROVENANCE.txt` beside the file at fetch
time.

Headers of the two containers, read directly:

| | B-PTQ1 | B-PQ2 |
|---|---|---|
| tensors | 851 | 851 |
| type histogram | 353 F32 + 96 BF16 + **402 x type 143** | 353 F32 + 96 BF16 + **402 x type 142** |
| `general.architecture` | qwen35 | qwen35 |
| kv count | 49 | 49 |
| `prism.hadamard.*` | present | present |

**Identical in every respect except the quantisation type.** The prereg's structural claim is
verified independently rather than taken from the model card, which is what P-L5 requires: the two
files must be containers for the same weights for a KLD difference between them to mean
"implementation defect" rather than "different model".

(B-PQ2 additionally carries `sign_values` / `sign_widths` / `inverse_weight_names` /
`gdn_v_grouped` hadamard keys. Noted, not yet interpreted -- if P-L5 breaks, the sign encoding is
the first place to look.)

## Build requirement, established rather than assumed

The local `engines/prism_llama_cpp` checkout **cannot read either file**: it defines
`GGML_TYPE_Q1_0 = 40`, `GGML_TYPE_Q1_0_g128 = 41`, `GGML_TYPE_COUNT = 42` -- a Bonsai v1-era tree.
Bonsai 2 needs 142/143.

`origin/prism` is **2520 commits ahead** (HEAD `9a9394a89`, 2026-09-18) and defines:

```
GGML_TYPE_PQ2_0  = 142,
GGML_TYPE_PTQ1_0 = 143,   // Prism-private ternary, group 128
```

with CUDA coverage including a dedicated `template-instances/mmq-instance-ptq1_0.cu`, plus CPU
paths. The MMQ config present is Ampere-targeted (`mmq-config-ampere.cuh`), so on sm_60 the
expectation is a dequantise + BLAS fallback rather than a fused MMQ path: slower, but correctness
is what a KLD measurement needs. The model card states plainly that stock llama.cpp rejects these
types as unknown, which matches the enum evidence.

**So the Bonsai cells are a fetch-and-rebuild of the fork at sm_60, not a rebuild of what is here.**
