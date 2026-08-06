# Predictions — Ornith-1.0-35B-A3B IQ2_M on HermesAgent-20 (Battle for 16GB, third contender)

Logged 2026-07-29 **before any scenario was run**. Scored after.

Prior results, same card, same 64k f16 stack, temp 0, K=1:
**Gemma-4-12B QAT 14/20 PASS** (1 runaway) · **Ternary-Bonsai-27B 15/20 PASS** (0 runaways).

## The contender

`Ornith-1.0-35B-UD-IQ2_M` (deepreinforce-ai, Unsloth imatrix quant), 10.77 GiB, ~2.5 bpw.
`qwen35moe`: 40 layers, **256 experts, 8 active** (~3B active params), hybrid — SSM layers plus
`full_attention_interval 4` ⇒ 10 growing-KV layers × 2 kv heads × (256+256).
**Derived 20 KiB/token**, i.e. comparable to Gemma (18.5 measured) and **3.2× cheaper than
Bonsai (64.5 measured)** despite being the largest model of the three.

Measured at launch before predictions were sealed:
- Loads `-c 65536` f16 KV: **12.17 GiB** server footprint (idle 1.62 → 13.79 GB).
- **77.13 t/s decode** — fastest of the three (Gemma 59.3, Bonsai 46.0). MoE sparsity.
- Tool calling: clean (`finish_reason=tool_calls`, `{"city":"Tokyo"}`, 351 chars reasoning).
- Determinism on this build: **3/3 byte-identical** 1200-tok greedy, sha `7c5bac70bae09cd2`.
  K=1 is earned here, not inherited.

## P-O1 — Ornith scores 15–17 PASS, i.e. ties or narrowly beats Bonsai (conf 0.60)

Not a strong claim, and that is the point. Two models 23B apart in size and 2.6 bpw apart in
precision landed one scenario apart (14 vs 15). A third architecture landing in the same
narrow band is the single most likely outcome, and it is *evidence about the benchmark*, not
about the models.

## P-O2 — The suite is near its ceiling: ≥8 of the 9 never-failed scenarios pass again (conf 0.85)

**Mark's hypothesis, made falsifiable.** Across 5 model-observations (Gemma temp 0, 3 Gemma
sampled draws, Bonsai), **9 of 20 scenarios have never once failed**: HA-01, 03, 04, 09, 10,
11, 13, 15, 18. Only **HA-07 and HA-17** have defeated every model tested.

If a fourth model — different architecture, different vendor, different quantisation, 2.5 bpw
— also sweeps those 9, they are measuring a floor rather than discriminating between models.
That would mean the effective suite is ~11 scenarios wide, and the 14-vs-15 "result" rests on
an even smaller base than it appears.

Falsified if Ornith fails ≥2 of those 9.

## P-O3 — HA-07 and HA-17 fail again (conf 0.75)

These are the only two scenarios no model has passed. If they fail a third architecture, they
are candidate *real* discriminators — the part of the suite with headroom left — and deserve
to anchor any harder benchmark. If Ornith passes either, that is the most informative single
result of the run, because it would be the first evidence the suite can separate models at
the top.

## P-O4 — No runaway; ≤1 no-verdict (conf 0.80)

Bonsai (0 runaways) already falsified my "low bpw ⇒ non-termination" reasoning from the
previous leg. Ornith is also a Qwen3.5-family hybrid with the same `full_attention_interval`
design and the same trained-in stop behaviour, and it decodes 1.7× faster than Bonsai, so a
520 s ceiling is even less binding. Stated explicitly so it can be scored rather than assumed.

## P-O5 — Ornith's context ceiling is ≥131,072 (conf 0.70)

At 20 KiB/token derived, 131k KV ≈ 2.5 GiB on top of 10.77 GiB of weights ≈ 13.3 GiB — tight
but plausible on a 16 GB card with a desktop running. Bonsai's real ceiling was 64k (it
*loaded* at 131k but decoded at 3.23 t/s over PCIe).

**Ceiling must be confirmed by a decode probe, not by a health check.** Loading and reporting
healthy is not serving — that error was caught once already this session and would have been
published as a working 131k ceiling for Bonsai.

## Controls in place

- Same card, same engine as the Gemma leg (`llama_cpp_turboquant`), same `-c 65536`, f16 KV,
  `-np 1`, `--cache-ram 0`, `-fa on`, `-ngl 99`.
- stevibe's `scripts/run-scenarios.mjs` **unmodified**, temperature 0 (pack default).
  Ornith's GGUF ships `general.sampling.{temp 1.0, top_k 20, top_p 0.95}` as chat defaults;
  the harness overrides with temp 0, per `HA20_SAMPLING_ARMS.md`.
- Per-scenario timeout token-matched, not wall-matched: 77.13 t/s vs Gemma's 59.34 means an
  equal wall clock would hand Ornith a *larger* token budget. 400 s × 59.34 ÷ 77.13 = **308 s**;
  rounded to **310 s** so no model gets a bigger effective budget than the reference arm.
