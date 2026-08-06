# Predictions — DS4 tensor-split fix (Jabba `42974d12`), quad-P100

Logged **before** the run, 2026-08-01. Build `42974d12` "llama : support DeepSeek-V4 tensor
split" on `giveen/feature/turboquant-kv-cache-rebase`. Hardware `.194`, 4× Tesla P100-PCIE-16GB,
**1063 MHz / 150 W** standing config (405 MHz idle, 0 MiB resident at launch).

Baseline to beat, from `DS4_FLASH_P100_LOAD.md`: `-sm layer -ts 3,4,4,1 -fit off -fa on
-ncmoe 40` → 2.16 t/s, gzip 0.469–0.567. Prior failure on `8a891f4b5`: `-sm tensor` asserted
`GGML_ASSERT(!suffix_fallback.empty())` at `llama-model.cpp:416` at **every** offload level.

**Two independent questions.** Q1 can pass while Q2 fails; they must be scored separately.

| id | claim | conf |
|---|---|---|
| P-T1 | **Q1.** `-sm tensor -ncmoe 40` gets past the `suffix_fallback` assert | **0.75** |
| P-T2 | It also *generates* coherently — gzip inside 0.42–0.60, CJK 0 | **0.55** |
| P-T3 | **Q2.** `-ncmoe 30` loads under tensor-split (the 20 GB wall breaks) | **0.35** |
| P-T4 | If it loads at 40, decode ≥ 2.16 t/s (beats layer-split) | **0.45** |
| P-T5 | A *new*, different assert appears at some rung (Jabba's predicted "secondary meta-split" on an unexercised DS4 op) | **0.40** |

## Reasoning, so these can be scored honestly

**P-T1 = 0.75, not higher.** The patch targets exactly the regex I diagnosed as the root
cause, and the diff matches the failure mode line-for-line. Held below 0.8 because Jabba has
no quad-P100 — the fix is reasoned, not empirically confirmed on hardware that reproduces the
assert. It clears the *first* assert; nothing guarantees it is the only one on the path.

**P-T2 = 0.55.** Loading is not passing, and this is the failure mode I most expect to be
missed. Tensor-split changes *where* the math happens and re-homes reshaped views; a name-
resolution fix makes allocation succeed without proving the shards are recombined correctly.
IQ1_S at ~1.6 bpw has no headroom to absorb an axis error. Precedent for the concern: turbo3
loaded fine under the wave64 bug and produced gzip 0.175–0.347.

**P-T3 = 0.35 — below even odds, and this is the prediction I most want falsified.** The whole
reason to want tensor-split on this box is to shard the ~20 GB expert tensor across four cards.
But `-ncmoe` offloads *MoE expert* tensors, and llama.cpp's TP code splits by explicit
tensor-name patterns — attention and FFN. Jabba's patch adds DS4 **attention** patterns
(`attn_q_[ab]`, `attn_kv`, `attn_output_[ab]`); it says nothing about routed experts. If expert
tensors aren't in the split set, they are still placed whole and the wall is untouched. I would
be glad to be wrong here.

**P-T4 = 0.45.** Tensor-split adds a cross-device reduction per layer. On PCIe 3.0 with two
E5-2650 v3 sockets and no NVLink, that sync can cost more than the placement wins — and at
2.16 t/s decode is already dominated by DDR4-2133 expert reads over the bus, which sharding
GPU-resident attention does nothing to relieve.

**P-T5 = 0.40.** Jabba explicitly anticipated this ("if unexercised DS4 operators like
compressor/indexer trigger secondary meta-split assertions, share the stack trace"). He is
closer to that code than I am, and treating his own hedge as likelier than not seems right —
but the ladder only reaches those ops if the earlier rungs load, so P-T5 is conditional on P-T1.

## Scoring rule, fixed now

- Q1 (P-T1/P-T2) is answered at `-ncmoe 40`, the level that already works under layer-split.
  Anything at 40 is a clean fix-works / fix-doesn't test with capacity held constant.
- Q2 (P-T3) is answered at 30/20 only. **An OOM at 30 falsifies nothing about the fix** — it
  is the pre-existing capacity wall and must be reported as such, not as a fix failure.
- Jabba's exact line runs first, verbatim, with no `-fit off`, so any report back to him
  describes his command rather than a variant of it.
