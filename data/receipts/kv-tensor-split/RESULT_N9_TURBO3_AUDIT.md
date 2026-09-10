# N9 audit — which of our own turbo numbers were silently measured with a `q8_0` K cache

**2026-08-28.** Audit, not an experiment. Backlog N9: *"With the guard at default,
`-ctk turbo3 -ctv turbo3` measures `q8_0` K + turbo3 V. Any of our own turbo3 receipts on such a
model may be mislabelled."*

## The guard, exactly

`src/llama-kv-cache.cpp:139-173`. Fires only when **all five** hold:

1. `type_k` is `GGML_TYPE_TURBO2_0`, `TURBO3_0`, or `TURBO4_0`
2. model is **not** MLA and **not** `LLM_ARCH_DEEPSEEK4`
3. `TURBO_AUTO_ASYMMETRIC` is not `0`
4. **`gqa_ratio >= 6`** (`n_head(0) / n_head_kv(0)`)
5. **`type_k == type_v`** (symmetric)

Effect: `type_k = GGML_TYPE_Q8_0`, with a `LLAMA_LOG_WARN`.

### Three scoping facts that shrink the blast radius

- **`TURBO3_TCQ` is NOT in the trigger list.** Per backlog U7, `-ctk vbr` is a CLI alias for
  `GGML_TYPE_TURBO3_TCQ`. **All VBR / tcq receipts are therefore unaffected.**
- **Asymmetric configs are unaffected** — the guard requires `type_k == type_v`. Everything run as
  `-ctk turbo4 -ctv turbo3` (which is most of the `battle16gb` issue-241 work) is clean.
- **buun's fork does not contain the guard at all** (`grep -c TURBO_AUTO_ASYMMETRIC` on
  `engines/buun-llama-cpp/src/llama-kv-cache.cpp` = **0**). Any receipt produced on a buun build
  is clean regardless of GQA.

### Date bound

Guard introduced **2026-07-31** (`1f7946026`, "llama : port TurboQuant KV-cache..."), amended
2026-08-12 (`6d4a1db28`, MLA guard fix). **Anything measured before 2026-07-31 is unaffected** —
this exonerates the `battle16gb/turbo3_repro*` logs, dated 2026-07-30.

## Confirmed by measurement, not inference

Ran the current Tom's-fork build on `.194` against `Qwen3.8-27B-UD-IQ4_XS`
(`n_head 24 / n_head_kv 4 = GQA 6:1`) with `-ctk turbo3 -ctv turbo3`:

```
W llama_kv_cache: auto-asymmetric: GQA ratio 6:1 (n_head=24, n_head_kv=4)
  — upgrading K from turbo3 to q8_0 to prevent quality degradation.
```

**The guard fires on our most-used model.** Qwen3.8-27B sits exactly on the threshold.

## Affected models in this fleet

| model | `n_head` / `n_head_kv` | GQA | affected? |
|---|---|---|---|
| **Qwen3.8-27B** (all quants, incl. AD-IQ2_S) | 24 / 4 | **6:1** | **YES — at threshold** |
| **Qwen3.8-Flash-Next** (qwen4exp) | 24 / 2 | **12:1** | **YES** |
| Qwopus3.6-27B-Coder | 24 / 4 | **6:1** | **YES** |
| Qwen3.5-9B / 3.5-4B | — | 4:1 | no |
| Llama-3.2-3B | 24 / 8 | 3:1 | no |
| DeepSeek-V4-Flash | 64 / 1 | 64:1 | **no** — MLA, explicitly excluded |

## Findings

### 1. CONFIRMED mislabelled — one log caught in the act

`p100-lab-harvest/slots/server_log_100k_restore_leg.log:13` is the only file in the tree that
records the guard firing:

```
auto-asymmetric: GQA ratio 6:1 (n_head=24, n_head_kv=4) — upgrading K from turbo4 to q8_0
```

Model `Qwopus3.6-27B-Coder-heretic-Q6_K`. That leg requested **turbo4 symmetric** and got
**q8_0 K + turbo4 V**. It is a slot save/restore leg, so no *codec fidelity* claim rests on it —
but any KV-size or throughput number from it is for `q8_0 K`, not turbo4 K.

### 2. CONFIRMED MISLABELLED — `desktop-16gb/RESULT_IQ2S_DESKTOP_PRELIM.md`

This is the one that matters, because it carries a **registered prediction and a falsification
verdict**.

- Model `Qwen3.8-27B-AD-IQ2_S` -> **GQA 6:1**, threshold met.
- Dated **2026-08-18**, after the guard.
- Built from `~/moe-cache-test/src`, remote `giveen/llama-cpp-turboquant` (Tom's fork),
  and **the guard is present in that tree** (verified, 2 occurrences).
- No script in `moe-cache-test/` or `desktop-16gb/` sets `TURBO_AUTO_ASYMMETRIC=0`.

Its section-2 table is:

| KV | published result |
|---|---|
| turbo4 | byte-identical to f16 |
| turbo3 | byte-identical to f16 |
| turbo2 | different wording, arithmetic correct |

**All three of `turbo2/3/4` are in the guard's trigger list.** If the runs were symmetric, then
every row measured **`q8_0` K + turboN V**, and the headline —

> "turbo3 — the exact codec in the paper's catastrophic pair — produced output
> indistinguishable from f16 on weights 9x lossier"

— did **not** test turbo3 on K. The paper's catastrophic pairing puts the lossy codec on **K**,
which is the side the GQA broadcast amplifies. That is precisely the arm the guard removes.

**The registered 0.75 "stacking collapse" prediction should not be treated as falsified** until
this is re-run with `TURBO_AUTO_ASYMMETRIC=0`.

**Residual uncertainty CLOSED by measurement (2026-08-28).** Rather than infer, I re-ran that
exact build and model:

```
$ ~/moe-cache-test/src/build-hip/bin/llama-server \
    -m /home/mark/Downloads/Qwen3.8-27B-AD-IQ2_S.gguf -ngl 0 -c 2048 -ctk turbo3 -ctv turbo3
W llama_kv_cache: auto-asymmetric: GQA ratio 6:1 (n_head=24, n_head_kv=4)
  — upgrading K from turbo3 to q8_0 to prevent quality degradation.
```

(`-ngl 0` because the guard runs in the KV-cache constructor regardless of offload, so this
needs no VRAM.) **The guard fires.** The section-2 table is confirmed mislabelled and the
receipt has been annotated with a retraction banner. The registered 0.75 stacking prediction is
**not falsified** — the test never exercised turbo on K.

### 3. CLEAN — checked and cleared

| receipt | why clean |
|---|---|
| `battle16gb/turbo3_repro*`, `TURBO3_ISSUE241*` | dated 2026-07-30, **predates the guard**; and mostly `-ctk turbo4 -ctv turbo3` (**asymmetric**) |
| `BUUN_RDNA4_PASTABLE.md`, `buun_nan_rate.sh` | buun fork — **no guard in that tree** |
| all VBR / `turbo3_tcq` results incl. `RESULT_U5B_BUUN.md` | `TURBO3_TCQ` is **not** a trigger type |
| all DeepSeek-V4 KV work | MLA, explicitly excluded by the guard |
| `rdna4-kernel-census` turbo3-sym row | labelled **GQA 3:1** — below threshold |

## Actions

1. **Re-run the desktop IQ2_S fidelity table with `TURBO_AUTO_ASYMMETRIC=0`** to get the real
   answer (~20 min; model is at `~/Downloads/Qwen3.8-27B-AD-IQ2_S.gguf`). The falsification is
   **retracted**, and the underlying question — does stacking collapse at short context? — is
   now **unanswered**, not answered-no.
2. **Add `TURBO_AUTO_ASYMMETRIC=0` (or an explicit asymmetric pair) to every future symmetric
   turbo run on a GQA>=6 model**, and capture the server log so the warning is on the record
   either way.
3. Feed this into **O6** — Tom's guard is defensible as a crash/quality safeguard, but it
   silently changes what a benchmark measures, and the warning is easy to miss in a long log.
   Worth proposing it be surfaced in `/props` or the startup banner.
