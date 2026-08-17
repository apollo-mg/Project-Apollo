# Pre-registered prediction — Qwen3.8-27B HumanEval+ 2x2, cell 4 of 4

**Written 2026-08-17 ~14:05 EDT, while cell 4 was at 18/164 and ~2.5 h from finishing.**
Logged before the result exists so it can be scored honestly. Nothing below was written
after seeing the outcome.

## The design (discovered, not designed by me — this run was already in flight)

`.194`, quad Tesla P100 (sm_60), `moe-cache-cuda` @ `bb3c3fa` on `giveen/moe-cache`.
Server: `-ngl 999 -c 20000 -fa on -np 1`, **no `-ctk`/`-ctv`** so KV is `f16+f16`.
Harness `~/hep/hep_eval.py`, HumanEval+ full N=164, temp 0.7 / top_p 0.95 / top_k 20, **K=3**.

A clean 2x2: **{IQ2_M, Q6_K} x {thinking OFF, thinking ON}**. The `t0`/`t1` in the file
prefixes is the *thinking* factor, not temperature — every cell is temp 0.7.

**The factor separated perfectly**, which is the first thing worth recording because it is
the failure mode that kills experiments like this:

| cell | `enable_thinking` | thinking fired | mean reasoning chars | median out_tok |
|---|---|---:|---:|---:|
| IQ2_M OFF | `false` | **0 / 492** | 0 | 192 |
| IQ2_M ON | `true` | **492 / 492** | 7012 | 696 |
| Q6_K ON | `true` | **492 / 492** | 4960 | 561 |

`enable_thinking:false` is **honored** by the Qwen3.8 template. This was not obvious: 3.8
moved the reasoning dial to `reasoning_effort` (8 sites in the embedded template) and we had
already been bitten by that on HLE. But `enable_thinking` survives (4 sites) and still works.
Had it been inert, the 2x2 would have silently collapsed into two duplicated arms — and it
would have looked like a real null.

## Results in hand (3 of 4 cells)

| cell | pooled pass@1 | per-sweep (K=3) |
|---|---:|---|
| IQ2_M OFF | 88.21 % | 88.21 % ± 0.76 |
| IQ2_M ON | 92.68 % | 92.68 % ± 0.50 |
| Q6_K ON | **93.90 %** | 93.90 % ± 0.86 |
| Q6_K OFF | *running* | — |

So: thinking is worth **+4.47 pp at IQ2_M**, and the quant gap **with** thinking is
**1.22 pp** (93.90 − 92.68).

## The prediction

The mechanism under test is our own, from `battle16gb/PUZZLE_LADDER_FA_ON.md` (07-17):
*"thinking compensates for quantisation damage — gap collapses 25.0 pp → 3.3 pp from Q2 to
IQ4."* If that generalises to Qwen3.8 on HumanEval+, then removing thinking should **widen**
the quant gap.

**Primary prediction: the thinking-OFF quant gap exceeds the thinking-ON gap of 1.22 pp.**
Equivalently, **Q6_K OFF > 89.43 %**. Confidence **65 %**.

**Point estimate: Q6_K OFF lands 90–92 %**, i.e. an OFF gap of ~2–4 pp. Confidence **50 %**
for that narrower band.

**Stated in advance as the reason this could fail:** HumanEval+ is near saturation for this
model family — every cell so far sits between 88 % and 94 %. Ceiling compression works
directly against the effect, because the headroom that a large gap would need does not
exist. This is the same instrument-validity problem that produced
`qwen38-lowbit/RESULT_2x2.md` ("all four cells 8/8, the instrument saturated"), only partial
here rather than total.

**Resolution is marginal by construction and I am saying so now, not afterwards.** Per-sweep
std across cells is 0.50–0.86 pp. A predicted gap change of 1.22 pp → ~3 pp is roughly
2–3 sigma of a single sweep, so a *direction* is readable but a *magnitude* is not. If the
observed OFF gap lands between about 1 and 2 pp, the honest verdict is **UNRESOLVED**, not a
weak confirmation.

## Scoring rule, fixed in advance

- **CONFIRMED** — Q6_K OFF ≥ 90.0 % (OFF gap ≥ ~1.8 pp, clear of one sweep sigma)
- **UNRESOLVED** — Q6_K OFF in 89.0–90.0 % (OFF gap ~1–2 pp, inside noise)
- **FALSIFIED** — Q6_K OFF < 89.0 %, and *strongly* falsified if Q6_K OFF < 88.21 %, which
  would mean the better quant is no better at all without thinking

## What this cell cannot settle regardless of outcome

- **`-fa on` is on in every cell.** `battle16gb/FA_EQUIVALENCE_SM60.md` measured `-fa on` as
  costing more fidelity than BF16→Q8_0 on sm_60. Constant across the 2x2, so the *contrasts*
  are valid, but the absolute numbers carry that tax and are not comparable to any `-fa off`
  arm.
- **`cache_prompt` is at its default `true`** and all 164 problems share an instruction
  preamble. At temp 0.7 with K=3 this is far weaker than the temp-0 case in
  `hermesagent20/PREFIX_CACHE_CHANGES_OUTPUT.md`, but the three sweeps are not strictly
  independent draws — they share a cached prefix. Backlog **B1**.
- **One bench, one model, one node.** HumanEval+ is short-form code with executable ground
  truth; it is the friendliest possible case for a no-thinking arm. A reasoning-heavy bench
  would likely show a much larger thinking effect and possibly a larger quant gap.
- **Nothing here measures the KV codec.** KV is `f16+f16` throughout — see below.

## Not exposed to the two KV bugs found on `.73`

Recorded because the question was asked directly. `kv-tensor-split/RESULT_TWO_KV_BUGS.md`
found (1) stock quantized KV codecs collapsing and (2) a hard abort on mixed f16/quantized
pairs. Neither can touch this run:

- The server passes **no `-ctk`/`-ctv`**, so both caches are `f16` — the one cell that was
  clean in the full matrix, and not a mixed pair.
- **`TURBO_AUTO_ASYMMETRIC` cannot fire here.** The gate at `src/llama-kv-cache.cpp:147-153`
  requires `k_is_turbo` (`TURBO2_0` / `TURBO3_0` / `TURBO4_0`) *before* it evaluates the GQA
  ratio. `f16` is not a turbo type, so the auto-upgrade branch is dead in this
  configuration — no silent rewrite of the cache type. Verified by reading the source on the
  node, not inferred.

## Throughput note, for a later thread

Decode is **7.8 t/s**. All four P100s hold ~6.1–6.5 GiB (layer-split, the default — `-sm` is
not passed) and sit at 19–39 % utilisation drawing 31–95 W against a 150 W cap. That is the
serialisation signature `qwen38-splitmode/RESULT_P100_SM_TENSOR.md` documented: `-sm layer`
across P100s is inert, `-sm tensor` is 1.62x.

**Do not change it mid-ladder.** Three cells are already recorded under layer-split and
`-fa on`; switching now would make cell 4 incomparable to the other three, which costs more
than the ~1 h it would save. The 1.62x belongs to the *next* ladder, set at the start.

`blk.64` is loaded and ignored (`model has unused tensor blk.64.*`), confirming
`battle16gb/MTP_UPSTREAM_ROOT_CAUSE.md` — MTP tensors load even when never requested. MTP is
available but off, and **should stay off for a quality ladder**: per
`spec-decode-determinism/RESULT_SPECULATION_IS_NOT_BIT_EXACT.md` (PROVISIONAL) speculation
changes emitted text, which is a confound for a benchmark and not for a throughput test.

## Filing note

`HEP_PREFIX=hep_Q6_K_t0` while `HEP_TEMP=0.7`, so the output lands at
`hep_Q6_K_t0_results_t0.7_k3.json`. The `t0` reads as "temp 0" and is not; it is
"thinking 0". Rename at write time or the next reader will misquote the temperature — the
three finished cells have the same ambiguity.
