# PREREG -- what three weeks of Strata releases bought: v0.2.7 against our v0.1.39 receipts, on .194 and the RX 9070 XT

**Registered 2026-10-28, before either rerun.**

**Prior art checked:** our own baselines. `strata-194/RESULT_STRATA_194_SPILL.md`: Strata v0.1.39 on 4x P100, Unsloth
Flash-Next UD-IQ4_XS spilling, installer config (`--spec 4 --spec-min-p 0.5`, MTP), reasoning-v1 **37.1 and 37.3 tok/s**
(two starts; acceptance ~0.84). `strata-9070/RESULT_STRATA_9070.md`: v0.1.39 on the RX 9070 XT, Flash-Next Coder IQ1_M,
installer config with MTP, code-v1 **52.6** (53.0 / 52.2), reasoning-v1 **65.5**. Strata's release notes since then
claim P100 decode +7-11 % (0.1.43), +6 % (0.1.43.1) and Pascal-specific decode switches (0.2.0); up to +38 % decode on a
16 GB Radeon (0.1.43). **What this adds:** a measured before/after on two of the hardware classes those notes name,
on the same packs and files, by a third party.

## Design

- **Engine:** Strata v0.2.7 (`5e8a4cca`). .194: built from source with CUDA 12.4 + gcc-13 for sm_60, as v0.1.39 was.
  Desktop: the engine already compiled from v0.2.7 for gfx1201.
- **Same weights and packs as October** (hashes as recorded there), the same canonical prompts, lmx custom remote,
  `--max-tokens 256`, temperature 0.
- **Config:** whatever v0.2.7's setup writes for that model and card, plus a `sampling` block with presence,
  repetition and frequency penalties off. Without it, 0.2.7's server adds the model card's presence penalty 1.5 to a
  temperature-0 request, which switches MTP drafting off (found on 2026-10-27, `strata-9070/q36`). October's runs
  drafted, so drafting must be on for a like-for-like rerun. Drafts accepted are reported per request.
- **Arms:** .194: reasoning-v1 x2 fresh starts (primary), code-v1 x1. Desktop: code-v1 x2 fresh starts (primary),
  reasoning-v1 x1. Each arm is two lmx passes (6 timed samples, median). Desktop runs in a `MemoryMax=26G` unit with Clef
  paused; kernel allocation failures are counted per arm.
- **If v0.2.7 cannot use the October packs** (re-pack or re-download needed), the rerun stops and is reported as such,
  rather than silently changing the weights.

## Predictions

| # | claim | rule |
|---|---|---|
| R1 | .194 got faster as the release notes claim | median reasoning-v1 >= 40.0 tok/s (+7.5 % over 37.2) |
| R2 | the 9070 got faster | median code-v1 >= 57.9 tok/s (+10 % over 52.6) |
| R3 | MTP still drafts at October's rate | acceptance within 0.05 of October's (~0.84 on .194; desktop as recorded there) |
