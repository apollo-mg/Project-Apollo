# The turbo-KV collapse is BUUN-SIDE: same card, same model, same probe, opposite result

**2026-09-03. SUPERSEDED IN ITS HEADLINE — READ THIS FIRST.**

> **The commit tested here is NOT buun's HEAD.** The local checkout was detached at
> `7a918624b` and `origin/master` had not been fetched: it was **81 commits behind**. That
> count overstates it — most of those are upstream llama.cpp commits pulled in by
> `a71ca2fd2 "merge: sync upstream through 0f3a71be"`. In wall-clock terms the checkout was
> `7a918624b` (2026-09-01) against HEAD `3823c9eb6` (2026-09-02): **about one day of buun's
> own work.** Among
> the missing commits is **`424c3361e` "hip: fix Turbo KV prefill attention dispatch"
> (spiritbuun, 2026-09-02 17:03)** — HIP, Turbo KV, prefill dispatch, which is exactly the
> failure mode measured below. buun stated on 2026-09-03 that he has RDNA4 hardware and
> fixed an RDNA4 bug locally the previous day.
>
> Everything below is therefore a reproduction on a **stale commit**, not on buun's current
> code, and the title's claim that the bug "is buun-side" is unsupported as written — the
> honest version is that it *was* present at `7a918624b` and is very likely already fixed.
> Re-test at `3823c9eb6` is in progress; result goes in `RESULT_TURBO_FIXED_AT_HEAD.md`.
>
> **Cause of the error:** I read `git log --oneline -1` and the words "HEAD detached at
> origin/master" and called it HEAD, without fetching. A stale remote-tracking ref looks
> exactly like a current one. **Fetch before claiming a commit is HEAD.**
RX 9070 XT (gfx1201, ROCm). Raw: `raw_repro_v2_buun.jsonl` / `.log` (buun),
`raw_repro_v2.jsonl` / `.log` (turboquant).

## The controlled comparison

Everything is held constant except the fork and the KV codec:

- model `Qwen3.8-27B-AD-IQ2_XS.gguf` (`qwen35`, hybrid, GQA 6:1, D=256)
- `-c 4096 -fa on --jinja --kv-unified -np 1`, **temperature 0, seed 42**
- identical `json_schema` prompt requiring three fixed terms copied verbatim
- `max_tokens 1200`, `reasoning_effort medium`

| fork | commit | KV | finish | completion tokens | content |
|---|---|---|---|---|---|
| turboquant `tq_head` | `f97400563` | f16 | stop | 269 | valid JSON, **3/3 terms exact** |
| turboquant `tq_head` | `f97400563` | **turbo4** | stop | 269 | valid JSON, **3/3 terms exact** |
| turboquant `tq_head` | `f97400563` | **turbo3** | stop | 171 | valid JSON, **3/3 terms exact** |
| turboquant `tq_head` | `f97400563` | **q8_0-K/turbo4-V** | stop | 269 | valid JSON, **3/3 terms exact** |
| buun (STALE, 81 behind) | `7a918624b` | f16 | stop | **114** | valid JSON, **3/3 terms exact** |
| buun (STALE, 81 behind) | `7a918624b` | **turbo4** | **length** | **1200 (capped)** | **EMPTY** |

### Full buun matrix, both prompt lengths

| KV config | 71-token prompt | 2,133-token prompt |
|---|---|---|
| f16 (control) | stop, 114 tok, 3/3 exact | stop, 618 tok, coherent |
| `turbo4` / `turbo4` | **COLLAPSE** (1200, empty) | **COLLAPSE** (1200, empty) |
| `turbo3` / `turbo3` | **COLLAPSE** (1200, empty) | **COLLAPSE** (1200, empty) |
| `q8_0`-K / `turbo4`-V | stop, 256 tok, 3/3 exact | **COLLAPSE** (1200, empty) |
| `turbo8` / `turbo8` | stop, 256 tok, 3/3 exact | **COLLAPSE** (1200, empty) |

**Every turbo configuration collapses at 2,133 tokens.** What differs is the threshold:
turbo-as-**K** fails even on a 71-token prompt; turbo-as-**V** behind a `q8_0` K, and
`turbo8` on both sides, survive the short prompt and die by 2k.

`turbo8` is 8.125 bpv — it fails exactly like `turbo3`. **Bit depth is irrelevant**, which
is what `RESULT_TCQ_2BIT_RDNA4.md` said in August and what this independently confirms on a
newer commit with a better detector.

**Detector caveat worth recording:** the automated temp-0 divergence check flagged the two
clean cells as `identical=False, first_diff_char=1`. That is **formatting only** — f16
emitted compact JSON, the turbo arms pretty-printed it. All three fixed terms are
character-perfect in every non-collapsed cell. A divergence metric alone would have
mis-scored these two as failures; the content had to be read.

**buun turbo4 never leaves the thinking block.** 1,200 tokens of reasoning, zero content, on
a prompt its own f16 arm answers in 114 tokens. Live server log while it ran:

```
n_gen =  705, tg = 28.71 t/s
n_gen =  963, tg = 28.66 t/s
n_gen = 1135, tg = 28.64 t/s   <- still generating, same 71-token prompt
```

Decode speed is *normal* throughout — this is not a hang or a stall. It is
`turboquant#311`'s **"no-EOS runaway"**, and only the `max_tokens` cap stopped it. poshih
reported 12k+ tokens to client timeout on an RTX 3090 over CUDA.

## Why this matters

1. **It is not the turbo codecs as turboquant ships them.** Same card, same model file, same
   probe, same codec name — turboquant HEAD is clean on all four KV configurations.
2. **It is not the flash-attention kernels.** `RESULT_TURBO_FA_GQA_SWEEP.md`: 50 turbo FA
   cases at hsk=256 across GQA 1/2/4/6/8 on this card, zero failures.
3. **It is not AMD-specific.** poshih hit the same symptoms on CUDA. #311 has been open with
   **zero replies since 2026-08-19**.
4. **It blocks VBR, not just the `-ctk/-ctv` flags.** buun's degrade ladder
   (`llama-vbr-degrade-orders.inc`, order `q27`) puts a **turbo tier at step 1**, so any
   budget pressure at all puts turbo tensors in the cache. If every turbo tier is unsafe on
   this model class, f16 is the only safe rung and VBR has nothing to degrade into.
5. **buun's fork has zero turbo flash-attention test coverage** — its `test-backend-ops` FA
   sweep lists no turbo type at any head size, and skips all non-F16 KV above hsk=72.

## Root-cause hunt: one real fork delta found, and FALSIFIED

**The delta is real.** buun enables the fused turbo MMA kernel on AMD WMMA at D=256;
turboquant gates the identical path to NVIDIA Turing MMA only.

`buun ggml/src/ggml-cuda/fattn.cu:2345`
```cpp
if (turbo_mma_fused && (turbo_matched || turbo_fused_asym || turbo1_tcq_matched) &&
    (Q->ne[1] <= 4 || turbo_fused_prefill) &&
    (Q->ne[0] == 128 || Q->ne[0] == 256) &&
    (turing_mma_available(...) ||
     // AMD RDNA WMMA: trying D=128 AND D=256 (gemma) after lifting the upstream DKQ<=128 cap.
     amd_wmma_available(...))) {
```

turboquant's comment on the same dispatcher: *"Only reached from the gate for turbo4 K==V,
D in {128,256}, Q->ne[1] <= 4, **turing MMA**."* Its `amd_wmma_available` uses are all capped
at `Q->ne[0] <= 128` and sit in the f16/general path, not the fused turbo path.

So on gfx1201 at D=256 with turbo KV, buun runs a decode kernel turboquant never enables on
AMD — active exactly where the runaway happens (`Q->ne[1] <= 4` is decode).

**Hypothesis: this is the cause. Confidence 0.7. FALSIFIED.**

`GGML_TURBO_MMA_FUSED=0`, latch confirmed active in the server log
(`"GGML_TURBO_MMA_FUSED=0: fused turbo MMA kernel disabled"`), same binary, same probes:

| KV | 71-token prompt | 2,133-token prompt |
|---|---|---|
| `turbo4` fused OFF | **COLLAPSE** (1200, empty) | **COLLAPSE** (1200, empty) |
| `turbo3` fused OFF | **COLLAPSE** (1200, empty) | **COLLAPSE** (1200, empty) |

Identical to fused ON. The fused MMA path is **exonerated** — independently matching
poshih's own bisection note in #311 (*"Fused MMA decode path ... exonerated —
`GGML_TURBO_MMA_FUSED=0` on b9914 still produced corrupted output"*), which was measured on
CUDA and now holds on RDNA4 too.

The AMD-WMMA-at-D=256 gate remains a genuine, untested fork divergence worth reporting on its
own merits. It is not this bug.

## Second A/B: context checkpoints — ONE cell changed, which is not enough

`--ctx-checkpoints 0`, same binary, same probes (server log confirms zero checkpoints created):

| KV | 71-token prompt | 2,133-token prompt |
|---|---|---|
| `turbo4` ckpt OFF | **CLEAN** — stop, 114 tok, byte-identical to f16 | **COLLAPSE** |
| `turbo3` ckpt OFF | **COLLAPSE** | **COLLAPSE** |

**I called this a root cause off the first probe and was wrong.** One of four cells flipped.
`turbo3` did not improve at all, and `turbo4` still dies at 2k. Turbo codecs are confirmed
active in this run (`TCQ1 decode: K/V codebooks`, `TCQ decode: context-adaptive V alpha
enabled`), so it is not a silent fallback to f16 — but one cell is not a fix.

**The methodological problem this exposes:** poshih describes the symptom as
*"stochastic; rate scales with prompt length and output length"*. Every buun cell here is
**K=1**. A single clean cell cannot distinguish "checkpoints off helps" from "this draw
didn't fail". The turboquant result is stronger only because it is 12 consecutive clean
cells, not because any one cell is better evidence.

**Nothing about `--ctx-checkpoints` should be reported to buun without repeats.** The minimum
honest design is K>=5 per cell on the two configs that disagree.

## What this does NOT establish

- Which buun-side change is responsible. The fork carries VBR transcode, TCQ alpha, context
  checkpoints and slot-reuse machinery that turboquant does not. The server log shows
  `TCQ decode: context-adaptive V alpha enabled` and a 149 MiB context checkpoint created on
  the first request — both are buun-only paths and both are untested suspects.
- Whether it is model-class-scoped. Only `qwen35` GQA 6:1 D=256 has been probed on buun.
- Whether the K-side threshold is genuinely lower or just that turbo-K corrupts more per
  token. Only two prompt lengths were sampled.
- **Any per-cell result at K=1.** The failure is stochastic by poshih's own description. The
  robust claim is the aggregate — 8 of 10 turbo cells collapsed across two independent buun
  runs while 12 of 12 turboquant cells were clean — not any individual cell.
- A root cause. Two suspects tested, two down: fused MMA exonerated outright; context
  checkpoints inconclusive at K=1.

## Relationship to the August receipt — confirmed and refined

`RESULT_TCQ_2BIT_RDNA4.md` (2026-08-19) claimed three things. All three survive:

| claim | status |
|---|---|
| "One turbo tensor anywhere in the cache is sufficient" | **CONFIRMED** at 2,133 tokens |
| "Bit depth is irrelevant — turbo8 at 8.125 bpv fails identically" | **CONFIRMED** |
| "The trigger is prompt length" | **CONFIRMED**, and now quantified per config |

The refinement it could not see, because it sampled a single prompt length: **which side
carries the turbo tensor sets the threshold.** Turbo-as-K collapses on a 71-token prompt;
turbo-as-V behind a `q8_0` K needs a longer one. That asymmetry is the same one jasstrong
established independently in `turboquant#294` for VGPR spills — *"it's turbo-as-K that blows
up, not turbo generally"* — on a different fork and for a different failure mode.

## Correction to an earlier receipt today

`RESULT_TURBO_COLLAPSE_NONREPRO.md` concluded the collapse "does not reproduce on current
turboquant HEAD" and listed four candidate explanations. **Explanation 2 — fork-specific to
buun — is now the answer**, and that receipt's own warning stands vindicated:

> "Everything in this receipt is `tq_head`. **No claim about buun's fork is supported by
> it.**"

Had the buun leg been skipped, the honest-looking conclusion would have been "fixed upstream,
nothing to report" — the exact opposite of the truth.
