# IQ2_S stacking, redone with turbo actually on K — the conclusion survives, the old evidence didn't

**2026-08-28**, control plane **RX 9070 XT (gfx1201, RDNA4, ROCm/HIP)**, `moe-cache-test` HIP
build (`giveen/llama-cpp-turboquant`, the same build as the original receipt).
Model `Qwen3.8-27B-AD-IQ2_S.gguf`. `-ngl 99 -c 8192 -fa on`, temp 0, `top_k 1`, `n_predict 200`,
`cache_prompt` off. 10 items (T2-01..T2-10, the tier-2 arithmetic set from `f16_control.py`).

Follow-up to `RESULT_N9_TURBO3_AUDIT.md`, which established that the original section-2 table in
`RESULT_IQ2S_DESKTOP_PRELIM.md` was measured with the auto-asymmetric guard silently rewriting
**K to `q8_0`** — so turbo never touched K, the side the GQA broadcast amplifies and the exact
arm the stacking hypothesis is about.

## Design

Every turbo codec run twice: once at the guard's default, once with `TURBO_AUTO_ASYMMETRIC=0`.
The server log was checked each arm for the guard's warning, as a positive control that the
manipulation actually took.

## Results

| arm | guard fired | identical to f16 | **correct** | degenerate |
|---|---|---|---|---|
| f16 (reference) | — | 10/10 | **9/10** | 0/10 |
| turbo4 | **yes** | 3/10 | 9/10 | 0/10 |
| turbo3 | **yes** | 3/10 | 10/10 | 0/10 |
| turbo2 | **yes** | 1/10 | 9/10 | 0/10 |
| turbo4, `TURBO_AUTO_ASYMMETRIC=0` | no | 4/10 | 9/10 | 0/10 |
| turbo3, `TURBO_AUTO_ASYMMETRIC=0` | no | 1/10 | 9/10 | 0/10 |
| turbo2, `TURBO_AUTO_ASYMMETRIC=0` | no | 0/10 | **9/10** | 0/10 |

"correct" = the gold string appears in the output. "degenerate" = output under 20 chars or
containing a run of 25+ identical characters (the `!!!!` collapse signature).

**Control worked:** the guard fired in exactly the three default arms and in none of the
`=0` arms.

## Findings

### 1. The stacking-collapse prediction is still not supported — but now it has been actually tested

**Correctness is flat at 9-10/10 in every arm**, including **turbo2 on K at 2 bits** over IQ2_S
weights. Zero degeneration anywhere. The f16 reference itself scores 9/10, so the single miss is
a model limitation, not a KV artifact — it is wrong at f16 too.

The registered 0.75 prediction ("a static low-bit weight + low-bit KV pairing would be badly
degraded or collapse") **remains unsupported at this context length**, and this time the test
exercised the mechanism the prediction is about. The original conclusion was right; its evidence
was not.

### 2. But "byte-identical to f16" does **not** hold, guard or no guard

The original reported turbo4 and turbo3 as *byte-identical to f16*. Here identity runs
**3/10, 3/10, 1/10** with the guard on and **4/10, 1/10, 0/10** with it off. Identity decays
monotonically with bit depth, as one would expect, and it decays **further** once turbo reaches K
(turbo3 3/10 -> 1/10; turbo2 1/10 -> 0/10).

So the K codec **does** change the output — measurably and in the predicted direction — it just
does not damage answer quality at this depth. That is a more precise result than either the
original claim or its retraction.

### 3. Scope, stated plainly

- **Not a reproduction of the original table.** Different prompt set (the original's prompts were
  not recorded) and `n_predict 200` vs its 80. My guard-on arms do not reproduce its 100% identity,
  so its stronger phrasing fails independently of the guard.
- 10 items, one model, one quant, 8k context, greedy. This is a smoke panel, not a fidelity panel.
- **Depth is still untested.** KV error accumulates with context; everything here is 8k. The honest
  claim remains *"the catastrophe does not appear at short context"*.

## Status of the retraction

`RESULT_IQ2S_DESKTOP_PRELIM.md` section 2 stays **retracted** — its evidence did not test turbo on
K, and its byte-identity claim does not reproduce. Its *conclusion* is now independently supported
by this receipt, on a proper test.
