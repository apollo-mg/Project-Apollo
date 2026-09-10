# PREREG — is good abstention a Qwen property, or is it becoming standard?

**Written 2026-09-07 before the run.**

## What this can and cannot answer

`Spark-X2.5-4B` (XHToken), `Q4_K_M` 2.42 GiB, arch `spark2_5`. Every calibration number in
this corpus is Qwen3.8-27B. This is the first non-Qwen model on `tier_cal`.

**It is not a control for Qwen** (`AFM-30`): different vendor, different size class (4B vs
27B), different architecture. Vendor and size cannot be separated by a single arm.

**What the paired fixture salvages:** the answerable arm is a capability check. A model that
scores well on *both* arms is interesting regardless of size; a model that abstains well while
failing the answerable arm is just weak, and its abstention means nothing. That distinction is
the whole reason the fixture is paired, and it survives the confound.

## Architecture note (from the GGUF, not the card)

36 layers, `sliding_window 512`, pattern 3-sliding-to-1-full → **9 full-attention layers**.
Dual RoPE: `freq_base 5,000,000` / 64 rotated dims on full layers, `10,000` / 256 dims on
sliding. `context_length 1048576` with **no rope_scaling** — the 1M is trained-in, not YaRN.
KV cost ≈ **36 KiB/token** at f16, roughly half Qwen3.8-27B's 64.

## Conditions

Desktop RX 9070 XT, `XHToken/llama.cpp` `4a3635c32` built for gfx1201 (their README claims
CPU+CUDA only; the fork adds nothing under `ggml/`, so HIP is expected to work — if it does
not, that is the result and the run is void). `-ngl 99 -c 8192 -fa on`,
`--tier cal --effort medium --sampling card`, seeds 1001–1003.

**`--effort medium` is a Qwen concept.** `spark2_5`'s template will almost certainly ignore
`reasoning_effort` in `chat_template_kwargs`. That is fine — medium injects *nothing* on Qwen,
so the two are comparable at the "no injected instruction" baseline. Verify from the rendered
template rather than assuming.

## Predictions

| # | prediction | conf |
|---|---|---:|
| S-1 | The HIP build works and the model serves on gfx1201 | 0.80 |
| S-2 | Answerable ≥ 18/24 — a 4B can do our easy factual arm | 0.65 |
| S-3 | Abstention ≤ 15/24 — materially worse than Qwen3.8-27B's 21/24 | 0.60 |
| S-4 | If S-2 holds and S-3 fails (i.e. it abstains well *and* answers well), abstention is not a Qwen-specific property | — |
| S-5 | `CAL-U3` (Mendeleev false premise) is confabulated on ≥2 of 3 reps — it defeats every Qwen configuration tested | 0.75 |

S-3 is the real prediction and I am deliberately betting against the interesting outcome.
A 4B holding Qwen3.8-27B's abstention rate would be the strongest single result of the day,
and predicting it at 0.60 *against* means a miss is informative rather than a shrug.

## Stopping rule

3 reps, then score. No extension on a peek.
