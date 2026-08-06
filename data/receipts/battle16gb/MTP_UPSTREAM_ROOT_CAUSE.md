# MTP: upstream knows the mechanism, and MTP tensors load even when you never ask for MTP

Date 2026-07-30. Triggered by JabbaTheDuck asking "are you referring to that MTP bug where it
forces MTP in upstream?" and then linking [#26290](https://github.com/ggml-org/llama.cpp/issues/26290).
He was right, and it is a *different* thing from the determinism issue. Both matter.
Updates `MTP_DETERMINISM.md`, `MTP_STRUCTURED_OUTPUT.md`, `MTP_HA20_AND_MARGIN.md`, all written
while treating the cause as unknown.

## Two separate upstream facts, easy to conflate

| | what it is | status |
|---|---|---|
| **A. Determinism** | batch-size-dependent kernel selection changes logits | explained by maintainer, both issues CLOSED |
| **B. Tensor loading** | NextN/MTP tensors load whenever present in the GGUF, no runtime opt-out | **OPEN**, filed 2026-07-29 |

They are unrelated code paths. A is why output changes; B is why VRAM goes up. "Forces MTP" is
about B, and it does **not** mean speculative decoding runs.

---

## A. Determinism — mechanism confirmed by the maintainer

> **ggerganov**, [#23335](https://github.com/ggml-org/llama.cpp/issues/23335), 2026-05-19:
> *"This is expected - we use different kernels for different batch sizes."*

Same claim as our "batched verification changes float reduction order," reached independently
from the acceptance rule at `common/sampling.cpp:621`.

| | [#23302](https://github.com/ggml-org/llama.cpp/issues/23302) | [#23335](https://github.com/ggml-org/llama.cpp/issues/23335) |
|---|---|---|
| closed | 2026-05-19, **by the reporter** (no fixed seed, invalid) | 2026-05-19, **by the reporter** |
| label | `bug-unconfirmed` | `bug-unconfirmed` |
| reporter / hw | carbocation, Apple M4 Pro, **Metal** | same |
| model | Qwen3.6-27B **Q4_K_M**, `nextn_predict_layers = 1` | same |

Blamed on [PR #22673](https://github.com/ggml-org/llama.cpp/pull/22673) (am17an, MTP support).

**Be precise about status.** Both issues were closed *by the reporter*, not triaged shut by a
maintainer, and both still carry `bug-unconfirmed`. ggerganov's line is an explanatory comment,
not a verdict. Do not say "classified as expected behaviour" or "nothing to file" — say the
mechanism is known and explained. Notably, D1rk-D1ggler's regression report (below) landed
**two days after closure and was never answered.**

### What the thread has that we did not

**1. Divergence at 100 % draft acceptance.** At `--spec-draft-n-max 1` the reporter saw
**31/31 tokens accepted** and still got different output from the no-spec run. Cleanest possible
proof that the divergence source is the **target model's batched forward pass**, not the draft
and not the acceptance logic. Independently vindicates our reading that zero steps in the
acceptance path are wrong.

**2. It is quantisation-dependent — that is the knob.**

| weights | reproduces? |
|---|---|
| Q4_K_M | **yes** |
| Q8_0 (`unsloth/Qwen3.6-27B-MTP-GGUF:Q8_0`) | **no** — all widths agree |
| Q6_K_XL (third party) | **yes** |

> **am17an**: *"if you keep everything in F32 for flash attention you may approximate
> batch-invariant behavior. i.e. batch (t1,t2,t3) vs 3 batches (t1),(t2),(t3) are numerically
> close, because we do most other things in F32 accumulation."*

**This explains our severity.** We ran **UD-IQ2_M (~2.5 bpw)**, well below the Q4_K_M that
breaks. Lower bpw ⇒ more near-tied logits ⇒ more of them flippable. Our measured flip margin of
0.03125 at the 99.25th percentile is the quantitative version of exactly that.

**3. Independent confirmation of structured-output degradation.**

> **D1rk-D1ggler**, 2026-05-21: *"strict JSON schema output (Temperature 0)... Qwen3.6-27B
> passes my 150 cases extraction reference benchmark at 100%, but turning MTP on drops that
> number to 97% — it consistently skips or misclassifies a small number of (same) cases. This is
> reproducible across runs. I am using Q6_K_XL."*

Different model size, quant, and harness; same direction as our HA-20 leg (every unstable
scenario but one moved base-PASS → MTP-FAIL; MTP never converted a base failure into a success).
Our result is not an artifact of IQ2_M or of stevibe's runner.

### What we have that upstream does not

**Verified from raw response bodies, 2026-07-30** (re-hashed `mtp_paired/*.json` from scratch;
digests differ from `MTP_DETERMINISM.md` because different fields are hashed — the structure is
identical):

```
base_r1_d1 f43730ef53883d95   mtp_r1_d1 f3d8ae794a65df23
base_r1_d2 f43730ef53883d95   mtp_r1_d2 ce6f4cce8990c174
base_r2_d1 f43730ef53883d95   mtp_r2_d1 ce6f4cce8990c174
base_r2_d2 f43730ef53883d95   mtp_r2_d2 14ec998df3198776
base_r3_d1 f43730ef53883d95   mtp_r3_d1 79c54850e2c9e44e
base_r3_d2 f43730ef53883d95   mtp_r3_d2 ce6f4cce8990c174
```

Two distinct claims, with different evidential strength:

**(i) Cold-start instability across restarts — CLEAN, no confound.** First draw of each fresh
instance: base `f437` ×3 (**1 distinct**), MTP `f3d8`/`ce6f`/`79c5` (**3 distinct**). Each of
those is a fresh process doing a full prefill. Nothing about caching can explain it. This is the
claim to lead with.

**(ii) Within-instance instability — real in the data, but one confound to state.** All three
MTP instances differ between their own two draws. **However**, the probe body
(`scratchpad/detprobe.json`) does **not** set `cache_prompt:false`, so draw 2 hit a warm prompt
cache and skipped prefill — a different execution path. The base arm ran the identical script and
probe and was 6/6 identical, so warm-cache reuse is not *sufficient* to cause divergence here;
but MTP+cache could interact where base does not. **Re-run with `cache_prompt:false` before
repeating (ii) publicly.** Claim (i) stands regardless.

**Upstream never tested repeat draws at a fixed config** — they report one output per config.
That is the gap our paired design fills. (Stated as "never tested," not "found stable" — their
tables show no repeats either way.)

### Open question worth naming

"Different kernels for different batch sizes" fully explains MTP-on vs MTP-off. It does **not**
explain run-to-run variation at a *fixed* config: at temp 0 with no RNG, same prompt, same KV
state, step 1's forward pass and acceptance count should be bit-identical, so the batch-shape
sequence and kernel selection should be too. A feedback loop (varying acceptance → varying batch
shape → cascade) needs an *initiating* nondeterminism it does not supply. **What breaks the tie
on step 1?** First candidates: `-cb` continuous batching, and `n_parallel` auto-sizing. This is
our open question, not upstream's answer.

---

## B. MTP tensors load unconditionally — verified on our own tree

[#26290](https://github.com/ggml-org/llama.cpp/issues/26290), **OPEN**, filed 2026-07-29:
*"NextN/MTP tensors now load by default for existing GGUFs, no load-time opt-out (regression
from #25980)."* Reported against GLM-5.2 (GLM_DSA); reporter notes it likely also affects
`hy_v3`, **`qwen35moe`**, `step35`.

> **am17an**, 2026-07-30: *"This was **always** the case when MTP is involved, starting from the
> initial Qwen3.6 MTP. It's only that no one bothered to check because everyone was using MTP by
> default I guess. It does make sense to not load it in case `--spec-draft draft-mtp` is not
> specified."*

> **Sciguy429**: *"llama.cpp loads MTP tensors regardless of speculative configuration options.
> I have been stripping the tensors from my local quants with a Python script... Saving that
> extra 1-3GB of RAM for prompt cacheing pays off far more for my use cases."*

**Confirmed here**, `llama_cpp_turboquant @ c26cbdffc`, no `--spec-type` passed:

```
print_info: n_layer      = 40          <- effective layers
print_info: n_layer_all  = 41          <- block 40 IS the MTP head
load_tensors: CPU_Mapped model buffer size =   333.44 MiB
load_tensors:      ROCm0 model buffer size = 10988.56 MiB
                                     total = 11322.00 MiB = 11.06 GiB
```

File is **11.057 GiB** of tensor bytes. Loaded 11.06 GiB. **The entire file, block 40 included.**

Cost of the head on this model, from GGUF metadata:

| | |
|---|---|
| `blk.40` total | **0.300 GiB (307 MiB), 2.72 % of the file** |
| largest members | `ffn_down_exps` 110 MiB, `ffn_gate_exps` 84 MiB, `ffn_up_exps` 84 MiB, `attn_q` 11 MiB, `nextn.eh_proj` 8.5 MiB |

### Consequences

- **Our VRAM accounting was mis-attributed.** `MTP_DETERMINISM.md` reports base 12.46 GiB vs MTP
  12.85 GiB, "+0.39 GiB for MTP." The 307 MiB head is resident in **both** arms. The +0.39 GiB is
  draft context/compute buffers only. Correct framing: you pay **0.300 GiB unconditionally** for
  owning an MTP GGUF, then **+0.39 GiB more** to actually switch MTP on. Enabling it is *cheaper
  than it looks*; owning the file is *more expensive than you think*.
- **Battle-for-16GB item.** On a 16 GiB card, 307 MiB is ~1.9 % of the card given away for a
  feature you may never enable — and per Sciguy429 it is 1–3 GB on larger models, OOM-level on
  744B-class GLM-5.2. Anyone sizing a quant to the edge of 16 GiB should know MTP GGUFs carry
  this. The only current escape is stripping tensors or `--no-mtp` at conversion time.
- **Not a turboquant divergence.** Our fork inherits upstream behaviour here.

### Separately: MTP *decoding* is opt-in in our tree

`common/arg.cpp:440-485` — everything gates on `spec_type_draft_mtp`, set only by an explicit
`--spec-type draft-mtp`; `common/speculative.cpp:2147` gates again on `ctx_dft != nullptr`. The
only automatic behaviour is **discovery**: if you already asked for draft-mtp and named no draft
model, it adopts the MTP head sibling of the `-hf` model. So nothing silently *runs* MTP — which
matters, because our base arm's 6/6 determinism would otherwise be suspect. Jabba's "forces MTP"
is real but is about tensor *loading* (B), not decoding.

---

## Corrections to our own prior reporting

- **Withdraw** "not 100 % sure what is causing the MTP unreliability." Known and explained.
- **Withdraw** "MTP costs +0.39 GiB" as stated — see the re-attribution above.
- **Do not claim** it is unreported, unfileable, or officially WONTFIX. Upstream engagement
  remains Mark's call and the existing constraint on that is unchanged.
- **Keep** every measurement. Margin 0.03125, 35 % scenario instability, acceptance-vs-entropy
  curve, runaway generations, cold-start instability — none of it is in the thread, and
  D1rk-D1ggler corroborates the direction.

## Tests this hands us

1. **`cache_prompt:false` re-run** of the paired probe — closes the (ii) confound. ~15 min.
2. **Precision sweep**: paired probe with `-fa off -ctk f32 -ctv f32` vs our f16/`-fa on` result.
   If determinism returns, we have a *recipe* — MTP's +24 % decode without the instability.
3. **Quant sweep**: the thread has two points (Q4_K_M breaks, Q8_0 clean) on one model. `.194`'s
   64 GiB can run a real ladder. Predicted dose-response: instability falls monotonically with bpw.

Log predictions before running any of these.

## Provenance

- `gh issue view 23302 / 23335 / 26290 -R ggml-org/llama.cpp`, fetched 2026-07-30
- Tensor load check: `llama-server -ngl 99 -c 512 -np 1 -lv 4`, no `--spec-type`, tree `c26cbdffc`
- `blk.40` sizes: `gguf-py` GGUFReader over the IQ2_M file, 2026-07-30
- Hashes: recomputed from `~/projects/HermesAgent-20/mtp_paired/*.json`
- `common/arg.cpp:440-485`, `common/speculative.cpp:2147`
