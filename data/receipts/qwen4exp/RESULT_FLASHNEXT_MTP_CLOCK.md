# Result -- Mark was right: the 1063 MHz pin costs speculative decoding twice what it costs plain decode. MTP on fully resident Flash-Next: 28.0 tok/s pinned, 34.1 at 1328 MHz (+22 %), where plain gains +11 %. The pin is still the most efficient setting, by less.

**2026-09-28.** Pre-registration `PREREG_FLASHNEXT_MTP_CLOCK.md` (`db4bba5`) with Deviation 1 (`354997d`: MTP-on first
ran GPU 3 out of VRAM; both halves rerun at `-ts 1,1,1,0.6`). Runner `run_mtp_clock.py`, analysis
`analyze_mtp_clock.py` (self-tested on synthetic data before any row). Raw `mtp_clock/rows.jsonl` (84 rows) and
`mtp_clock/power.csv` (all 4 GPUs at 200 ms). Run 1's MTP-off rows and its OOM log are kept beside them. The
efficiency config was restored and read back after both runs.

**Setup:**
- .194, 4x P100, buun `0b2789f23`, Flash-Next UD-Q2_K_XL, `-ngl 99 -sm layer -ts 1,1,1,0.6 -c 8192`, f16 KV,
  `-np 1`;
- MTP via the shared sidecar head, `--spec-draft-n-max 3`;
- 6 fixed prompts x 384 tokens per block (temp 0, thinking off), blocks E P B B P E.

## Results (decode medians of 12 requests; tok/J = generated tokens / whole-box GPU energy in the window)

| config | plain decode | MTP decode | MTP speedup | tok/J plain | tok/J MTP | mean W (4 GPUs) plain / MTP |
|---|---:|---:|---:|---:|---:|---|
| **E** 150 W, pinned 1063 | 21.05 | **28.03** | 1.33x | 0.110 | **0.130** | 178 / 181 |
| **P** 150 W, pinned 1328 | 23.40 | **34.09** | 1.46x | 0.091 | 0.111 | 242 / 257 |
| **B** 250 W, autoboost | 25.03 | 33.74 | 1.35x | 0.096 | 0.115 | 239 / 248 |

- **Acceptance** 0.70 at every config (09-02 under offload: 0.75).
- **Live SM clock** (sampled) sits exactly at the set clock: 1063 at E, 1328 at P and at B.
- **Per-GPU peak power:** 100-109 W at E, **152-164 W at P**, 160-183 W at B.
- **Prefill:** clock-driven and unaffected by MTP. 123-128 tok/s at E, 142-148 at P, 150-156 at B.

## Registered verdicts

| # | claim | result |
|---|---|---|
| M1 | MTP >= 1.4x at E | **does not hold.** 1.33x at E; 1.46x at P. The first MTP block after load was slow (26.6 vs 28.6 tok/s in block 5); block 5 alone gives 1.36x |
| M2 | the pin costs MTP more than plain decode (P/E ratio gap >= 0.05) | **holds.** P/E is 1.216 with MTP, 1.112 without |
| M3 | the 150 W cap does not bind for decode (B within +/-3 % of P) | **does not hold.** Plain: B is +7 % over P. With MTP: B = P (-1 %). At 1328 MHz single GPUs peak at 152-164 W, so the cap now clips, where at 1063 it never did |
| M4 | the pin's tok/J edge shrinks under MTP | **holds.** E over P: +21 % plain, +17 % with MTP |

## What it means (the answer to N11)

- **The July efficiency curve undersold speculative decoding.**
  - The pin costs plain decode 10 % of its speed, and MTP 18 %.
  - Verifying three drafted tokens per step is compute work, and compute scales with the clock; plain decode is
    mostly memory-bound.
- **MTP is also an efficiency win in its own right.**
  - At the pin, MTP gives +33 % speed and +18 % tok/J (0.110 to 0.130) at the same power (178 to 181 W).
  - MTP at the pin is the most efficient cell measured.
- **The practical choice for Flash-Next MTP serving:**

| goal | setting | decode | tok/J |
|---|---|---:|---:|
| efficiency | keep the pin (E) | 28.0 | **0.130** |
| speed | pin at 1328 (P) | **34.1** | 0.111 |

  - Going from E to P is +22 % speed for -15 % tok/J.
  - P with MTP is still as efficient per token as the OLD plain-decode config (0.111 vs 0.110), at 1.62x its speed.
  - Raising the cap (B) buys plain decode ~7 % and MTP nothing.
- **Mark's call, not changed here.** `p100-efficiency.service` still sets E. Whether speculative serving on .194
  should use P is a policy choice.

## Not established

- **One model and one node.** The 27B daily driver on .73 (MTP, 2 GPUs, tensor split) is where the same question
  matters most day to day. Not measured here.
- **Only 1063 and 1328.** Nothing in between (1189/1250 might be the efficiency knee under MTP).
- **Power is whole-box GPU power** from 200 ms samples. Sub-sample cap clipping at P is inferred from peaks, not
  observed directly.
- **Placement:** `-ts 1,1,1,0.6` (Deviation 1). Run 1 at the default split gave the same plain-decode E speed
  (21.07), so the placement change does not move the baseline.

## Adopted 2026-09-28 (Mark's plan): keep the 150 W cap, uncap the clock when serving speculatively

- **A quick A/B on .73 before adopting it.** The 27B-class Hemmingway, tensor split on 2 P100s, MTP on, through
  the wake proxy; 3 prompts x 256 tokens at temp 0; clocks 1063 / 1328 / 1328 / 1063; one warm-up discarded.
  - Median decode rose 23.34 -> 25.82 tok/s (**+10.6 %**); each prompt +9-11 %.
  - Draft acceptance was identical at both clocks.
  - About half of Flash-Next's +22 %, consistent with tensor split keeping both cards busy at once, so the 150 W
    cap clips more. Not measured here.
- **.73** (the daily driver always runs MTP): `p100-efficiency.service` now sets `-pl 150 -ac 715,1328`. The old unit
  is kept as `p100-efficiency.service.bak-1063`. Settings survive S3 (the old values read back after 24 resumes in
  one boot).
- **.194** (the test box) keeps 150 W / 1063 as its default. A speculative serving session sets `-ac 715,1328` at
  launch and records it. Receipt comparability with pre-09-28 runs depends on that default.
