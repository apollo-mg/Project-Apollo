# PREREG: DavidAU TURBO IQ2_M on the 9070 — VBR isolated, MTP disabled

**Written 2026-09-09 before the run.** Predictions logged with confidence; scored honestly after.

**Model:** `Qwen3.8-27B-TurboFCFusion-735-882-Here-Uncen-NEO-CODER-MAX-MTP-IQ2_M.gguf` (11.29 GiB)
**Hardware:** RX 9070 XT · **Build:** buun `3823c9eb6` · **Bench:** hermesbench, 61 tasks, fixed grader
**Config:** `-ngl 99 -c 32768 -np 1 -fa on --kv-unified -ctk vbr -ctv vbr --vbr-floor t2
--vbr-vram auto --reasoning-effort medium --min-p 0 --jinja` — **no `--spec-type`**

## Why MTP is off

Deliberate isolation, per Mark: **VBR > MTP in priority.** VBR is the subsystem we want working; MTP
is an optimisation carrying a known defect (`RESULT_TIMEOUT_WALL_ROOT_CAUSE.md` — draft acceptance
collapses to zero once the VBR degrade order clamps at the floor, and never recovers without a
restart). Running with MTP would contaminate a VBR measurement with that failure.

With no draft head there is no acceptance to collapse, so the wall cannot form by that mechanism.
This also removes speculative-decoding variance from the measurement entirely.

## Predictions

- **P1: the run completes all 61 tasks without a contiguous timeout wall.** 75%.
  No MTP means no acceptance collapse. VBR checkpoint pressure still exists and could bite by some
  other route, which is the residual 25%.
- **P2: decode lands 27–32 t/s.** 60%. Healthy MTP gave ~43 t/s on the sibling model and the measured
  multiplier is ~1.6×, so the baseline should be ~27. Wide-ish band because this is a different model
  at a much lower quant.
- **P3: IQ2_M shows degradation the IQ3_XXS did not** — looping, malformed tool calls, or incoherence
  on multi-turn tasks. 55%. CLAUDE.md records heavily-quantised models as structurally brittle under
  multi-turn JSON tool schemas ("2-Bit Drunk"). This is the first sub-3-bit agent run of the campaign.
- **P4: `valid_pass_rate` below the IQ3_XXS baseline of 0.943.** 70%. Two bits is a large step down.

## What would make this the campaign's first trustworthy Hermes number

- fixed grader (dispatcher normalisation) — **yes**
- no MTP acceptance collapse — **by construction**
- fresh server (AFM-26) — **yes**
- known-good sampling — hermesbench sends none; server defaults apply, verified at launch
- verdict schema still collapses INFRA/FAIL — **outstanding**, report all three separately

## Watch for

VBR checkpoint accumulation is *not* removed by disabling MTP. Track `created context checkpoint`
count and the `VBR_RETIER_PREFLIGHT ... watermark=` value. If the watermark climbs past ~21,500 and
`prepare_with_slots` reports the floor clamp **without** MTP present, that isolates the clamp itself
as harmful independent of speculative decoding — which would be a stronger finding than tonight's.
