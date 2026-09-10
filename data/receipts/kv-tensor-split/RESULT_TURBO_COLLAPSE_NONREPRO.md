# The turbo-KV collapse does NOT reproduce on current turboquant HEAD

**2026-09-03.** RX 9070 XT (gfx1201, ROCm), `engines/tq_head` **`f97400563`**.
Raw: `raw_repro_v2.jsonl` / `.log`, `raw_gsq_model_legs.jsonl`, `raw_repro_c4096.jsonl`.

## What was being re-tested

`RESULT_TCQ_2BIT_RDNA4.md` (2026-08-19, buun `02f8581c65`) recorded **8 of 8 turbo KV
configurations collapsing generation** on `Qwen3.8-27B-AD-IQ2_S`, gfx1201, `-c 4096` —
degenerate from the first request, trigger = prompt length. `turboquant#311` (poshih,
RTX 3090, **CUDA**, `qwen35moe`, GQA 8:1) reports the same family of symptoms and has sat
**open with zero replies since 2026-08-19**.

## v1 of this test was blind — recorded because it nearly became a false negative

First attempt used `max_tokens=200`. Qwen3.8-27B defaults to `xhigh` reasoning effort
(AFM-23), so **all 200 tokens were consumed inside the thinking block and every arm returned
empty content**. Fifteen of fifteen cells had `contentlen=0`. Had I read only
`finish_reason` and token counts I would have written "no collapse" off a detector that could
not have seen one. v2 fixes it: `max_tokens=1200`, `reasoning_effort=medium` (which injects
no system text), and a detector aimed at the reported symptoms.

## v2 detector

Model `Qwen3.8-27B-AD-IQ2_XS` (nearest surviving file to the receipt's `AD-IQ2_S`, same
packager, same `qwen35` / GQA 6:1 / D=256), `-c 4096`, `-fa on --jinja --kv-unified -np 1`,
**temperature 0, seed 42**. Arms: `f16`, `turbo4`, `turbo3`, `q8_0`-K + `turbo4`-V.

The copy probe deliberately targets poshih's exact failure mode — a `json_schema` request
whose fields must reproduce fixed vocabulary character for character, including
`intimate_proximity_threshold`, chosen because #311 reports `intimate_proximiti`.

## Result: every arm is clean

| arm | schema copy, 3 terms verbatim | note field | identical to f16? |
|---|---|---|---|
| f16 (control) | 3/3 exact | ACKNOWLEDGED | — |
| turbo4 | **3/3 exact** | ACKNOWLEDGED | **byte-identical** |
| turbo3 | **3/3 exact** | ACKNOWLEDGED | **byte-identical** |
| q8_0-K / turbo4-V | **3/3 exact** | ACKNOWLEDGED | **byte-identical** |

No structure-soup. No split or misspelled tokens. No exact-copy degradation. No no-EOS
runaway — every arm finished `stop`.

On the 2,175-token free-prose probe the turbo arms diverge from f16 at character 44–46 and
differ in length (f16 684 chars, turbo4/q8turbo4 549, turbo3 857). **That is ordinary
low-precision KV drift, not corruption** — all four paragraphs are coherent, on-topic and
correct. Divergence at temp 0 is expected when the cache precision changes; I flag it only
because it is the signal I would have used had the copy probe failed.

**Dead cell, stated plainly:** the `long3000` probe returned `ERR` on all four arms — the
prompt exceeded the 4096 context. It measured nothing. Identical failure across arms, so it
biases nothing, but it is not evidence.

## Second model, wider context — also clean

`Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp` (ISTA, 3.05 bpw), `-c 8192`, prompts to 3,574 tokens:

| arm | short | mid | long (3,574 tok) | decode |
|---|---|---|---|---|
| f16 | stop | length | **stop, coherent** | 29 t/s |
| turbo4 | stop | length | **stop, coherent** | 28 t/s |
| q8_0-K / turbo4-V | stop | length | **stop, coherent** | 28 t/s |

## Reading

Four explanations remain, and this test does not separate them:

1. **Fixed upstream** between buun `02f8581c65` (2026-08-19) and turboquant `f97400563`.
2. **Fork-specific to buun** — the VBR machinery, not the turbo codecs themselves.
3. **Specific to the `AD-IQ2_S` weights**, which are no longer on disk.
4. **Needs a longer prompt** than anything tested here.

Everything in this receipt is `tq_head`. **No claim about buun's fork is supported by it.**
A gfx1201 build of buun at `7a918624b` (later found 81 commits stale) is compiling to run the identical v2 detector; until
that lands, nothing here should be reported to buun as "works now".

## Side finding — the KV write path has no AMD coverage

`test-backend-ops support -b ROCm0` on gfx1201, all 28,563 cases: **42 `SET_ROWS_TURBO3` /
`SET_ROWS_TURBO4` cases, every one `NOT SUPPORTED`**, at ne0 = 128, 256 and 512.

This is jasstrong's observation from `turboquant#294` on 2026-08-13 —
*"`SET_ROWS_TURBO4` reports 'not supported' on gfx1030 and falls back to CPU... will check"* —
never followed up in the thread. **It reproduces on RDNA4.**

Scope it honestly: `ggml-cuda.cu:5218` accepts SET_ROWS with a turbo destination when
`ne0 % 64 == 0` (turbo2/3) or `ne0 % 128 == 0` (turbo4), so the *runtime* KV write at
D=256 is supported — and the measured 28–30 t/s confirms nothing is falling back to CPU
during inference. What is broken is the **test**: these 42 cases look like coverage of the
KV-write path and deliver none on any AMD GPU. `src/llama-kv-cache.cpp:1632/1685/1712` shows
the runtime writes the cache through exactly this op, so it is the path worth covering.

Not yet established: which node in the round-trip graph the backend declines.
