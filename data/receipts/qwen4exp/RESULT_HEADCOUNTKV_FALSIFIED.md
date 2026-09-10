# The `head_count_kv` rule is FALSIFIED on current heads — both forks, 2/3/4 devices

**2026-09-02.** `.194`, 4x P100 sm_60 @ **150 W / 405 MHz idle**. Predictions registered in
`PREDICTIONS_headcountkv_controlled.md` before the run.

## What I had been claiming

Since 2026-08-28, in receipts, in `FAILURE_MODES.md`, and in a draft written for Tom:

> `-sm tensor` is correct iff `n_devices <= head_count_kv`. Dense attention splits into exactly
> `head_count_kv` units; fewer units than devices produces zero-width slices and silent garbage.

Flash-Next has `head_count_kv = 2`, and on Tom's `c232282aa` it produced garbage at 3 and 4
devices while working at 2. The rule predicted that, and predicted a 27B success, so it looked
well-supported.

## The controlled matrix

Model `Qwen3.8-Flash-Next-UD-Q2_K_XL` (**the same quant as the original garbage observation**).
Flags identical across all six arms:

```
-c 8192 -ngl 99 -fa on --jinja -np 1 -fit off -ncmoe 44 -sm tensor
GGML_CUDA_ALLREDUCE=internal
```

Only fork and device count varied.

| arm | fork | devs | loaded | VRAM (MiB) | spread | verdict |
|---|---|---|---|---|---|---|
| B2 | buun `7a918624b` | 2 | yes | 4885 / 4519 | 1.08 | **COHERENT** |
| B3 | buun | 3 | yes | 3775 / 3775 / 3593 | 1.05 | **COHERENT** |
| B4 | buun | 4 | yes | 3217 / 3217 / 3401 / 3035 | 1.12 | **COHERENT** |
| T2 | Tom `0629f920e` | 2 | yes | 4945 / 4579 | 1.08 | **COHERENT** |
| T3 | Tom | 3 | yes | 4185 / 4185 / 4003 | 1.05 | **COHERENT** |
| T4 | Tom | 4 | yes | 3661 / 3661 / 3843 / 3479 | 1.10 | **COHERENT** |

**Six for six.** Every spread is 1.05–1.12, so tensor split genuinely engaged in all of them —
layer split on comparable flags was **6.36x** lopsided (2441 / 2611 / 15531 / 15209), so an even
profile is not producible by a silent fallback.

Tom's policy stop (`llama-model.cpp:818`, *"only N splittable units for M devices"*) **did not
fire**, on either 3 or 4 devices.

## Prediction scoring

| # | claim | conf | actual |
|---|---|---|---|
| P1 | T4 aborts at the policy stop | **0.90** | ❌ **coherent** |
| P2 | T3 aborts at the policy stop | **0.85** | ❌ **coherent** |
| P3 | T2 loads, coherent | 0.80 | ✅ |
| P4 | B4 coherent on Q2_K_XL | 0.65 | ✅ |
| P5 | B3 coherent | 0.60 | ✅ |
| P6 | B2 coherent | 0.80 | ✅ |
| P7 | rule is **fork-specific** | 0.65 | ❌ — it is **version**-specific; both forks now pass |

Two predictions at 0.85 and 0.90 were wrong, and they were the two the rule most directly implied.
That is the correct way for a wrong rule to fail: confidently, on its own central claim.

## What was actually wrong with the rule

The August observation was real — Tom's `c232282aa` did produce garbage at 3 and 4 devices. The
error was **generalising a property of one commit into a property of an architecture**. Between
`c232282aa` and today, PR #324 merged (`5ff15401f`), carrying the whole qwen4exp/DS4 split-state
series — the grouped `attn_output_a` placement, the propagated meta splits, the mirrored
unsplittable outputs. Any of those could supply the additional splittable units.

I never re-tested the rule against a newer head. It was written down once and then cited for five
days as established.

## Remaining confound — stated, not hidden

The August run used `-ngl 99 -sm tensor -np 1 -c 4096` with **no `-ncmoe`**; this matrix uses
`-ncmoe 44`. So "the code was fixed" and "`-ncmoe` changes the placement enough to supply units"
are **not yet separated**.

The isolating experiment is a build of `c232282aa` run with *these exact flags*: if it produces
garbage, the code was fixed and the rule is obsolete; if it is coherent, `-ncmoe` was doing the
work and the rule was never about device count at all.

### RESOLVED 2026-09-02 — the code was fixed; `-ncmoe` was not doing the work

`c232282aa` rebuilt for sm_60 (`build_sm60_c232`, 0 errors — note it builds *without* PR #339,
confirming the WMMA breakage postdates it) and run with **the identical flags** used in the matrix:

| head | devs | loaded | VRAM spread | output |
|---|---|---|---|---|
| `c232282aa` (Aug) | 3 | yes | 1.05 | **`////////...`** |
| `c232282aa` (Aug) | 4 | yes | 1.12 | **`////////...`** |
| `0629f920e` (Tom, today) | 3 / 4 | yes | 1.05 / 1.10 | coherent |
| `7a918624b` (buun, today) | 3 / 4 | yes | 1.05 / 1.12 | coherent |

Only the commit differs. **PR #324 fixed multi-device tensor split for qwen4exp.** The August
observation was correct; generalising it from a commit to an architecture was the error, and it
took five days and a controlled matrix to catch.

Note the VRAM spread on the August arms is *identical* to the fixed arms (1.05 / 1.12) — tensor
split engaged the same way in both. The bug was never about placement; it was numerical.

### Classifier defect found by this arm

The automated verdict was **`EMPTY`**, not `GARBAGE`, because the classifier inspected only
`message.content`. The slashes were in **`message.reasoning_content`** and `content` was `''` with
`finish_reason: length`. A garbage arm was one field name away from being recorded as a benign
empty response, in a receipt whose whole purpose is distinguishing those.

Any future grader must scan **every** text-bearing field, not the one the happy path uses.

### Connection to jabba's report

The garbage appears *inside the reasoning block*, with `content` never reached — which is exactly
his description: *"it starts thinking and then collapses."* Same failure shape. On sm_60 that shape
was fixed by the #324-era work; he is on current buun master on a 5090 and still sees it, so an
arch-specific instance of the same class may survive in a path Pascal never executes
([[pascal-never-uses-cuda-graphs]] and the other `cc >=` gates).

## Consequences

1. **Do not restate the rule.** Not to Tom, not to buun, not in `FAILURE_MODES.md`, until the
   archaeology arm resolves the confound. The draft for Tom that contains it must not be sent.
2. `FAILURE_MODES.md` and `DRAFT_pr324_update2.md` both carry the unqualified claim and need
   amending.
3. **Tom's policy stop may be too conservative** — but note it did not fire here, so whatever
   condition triggers it is narrower than the rule I attached to it. That is a separate question
   from whether the rule holds.
4. The general lesson is the one already written down as AFM-27 and violated again: a finding
   measured once, on one commit, is a fact about that commit. Five days of citation did not make
   it more true.

---

## 2026-09-03 addendum — this configuration is now refused

`-sm tensor` on **qwen4exp (Flash-Next)** was added to the `llm_arch_supports_sm_tensor` deny list
by upstream PR **#27941** (Daniel Han, 2026-09-01 10:22 UTC, `36b101543`), carrying the comment
`// TODO: fix test-llama-archs`. It reached buun's master via the later upstream sync, *after* the
commit this run used (`7a918624b`, 2026-09-01 23:40 UTC). Current buun and current upstream both
refuse the config with `LLAMA_SPLIT_MODE_TENSOR not implemented for architecture 'qwen4exp'`.

**Unaffected:** `deepseek4` and `qwen35` are NOT on the deny list. All DS4 tensor-split work and
all Qwen3.8-27B work stand, and 27B `-sm tensor` was re-verified working on 2026-09-03.

**What still stands here:** the measurements are accurate records of what that binary did, and any
*falsification* they carry is permanent -- a rule shown false is not made true by a later gate.

**What does not:** the numbers describe a configuration no one can run today, so they are
historical, not a basis for recommendation. And any positive reading of "tensor split works on
Flash-Next" is weaker than it appeared at the time: upstream had already concluded the path fails
`test-llama-archs`, and on 2026-09-03 the same path was found to **segfault deterministically** in
`ggml_backend_meta_graph_compute` on a prefix-extension prompt
(see [RESULT_META_BACKEND_SEGFAULT.md](RESULT_META_BACKEND_SEGFAULT.md)). Coherent output on
independent prompts did not mean the path was correct -- it meant the bad case had not been reached.
