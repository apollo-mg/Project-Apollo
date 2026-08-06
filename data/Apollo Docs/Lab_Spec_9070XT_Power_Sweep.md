# Lab Spec — RX 9070 XT Power-Efficiency Sweep (2026-07-18)

## Setup
- Desktop, gfx1201, kernel 7.1.3-2-cachyos. Card cap discovered at **374W max** (AIB uncorked;
  reference TBP 304W), hwmon floor 212W.
- **Held constant (pre-existing, receipted):** OD sclk offset −100MHz, vddgfx offset −30mV,
  stock mclk states (max state 1259MHz), fan auto.
- Model/build: Gemma-4-12B QAT UD-Q4_K_XL, turboquant build_rocm 9966 (f27268914),
  llama-bench `-fa 1`, r=3. tg leg: `-p 0 -n 128`; pp leg: `-p 512 -n 0`.
- Measured per leg: t/s, mean live draw (rocm-smi 2s sampling during the bench window only),
  sclk under load. Efficiency = t/s ÷ mean-draw.
- Caps: 374 / 330 / 290 / 250 / 212 W. Restore 374W after.

## Predictions (logged before run)
- **P-PWR1 (conf 0.7):** 212W holds ≥90% of 374W tg128 (decode is bandwidth-bound; cap
  mostly shaves compute headroom decode doesn't use). [Original docket phrasing said
  "220W"; hwmon floor is 212 — prediction maps to the 212 point.]
- **P-PWR2 (conf 0.6):** pp512 at 212W drops to 70–80% of 374W (prefill is compute-bound,
  rides the V/f curve down).
- **P-PWR3 (conf 0.75):** best decode tok/J lands at the 212W floor (no knee visible above
  it — unlike the P100s, whose knee at 150W was *above* their 125W floor).

## Phase 2 (separate run, math-validated): mclk offset
OD_MCLK exposed to 1500MHz on Linux. Windows "fast timings" toggle is NOT exposed (vBIOS
timing tables, driver-side selector; no amdgpu knob on RDNA4). Plan: +50MHz steps,
`test-backend-ops -p q2_0` + full-suite spot check as bit-level validation, llama-bench
delta, back off one step from first failure. NOT run in this sweep.

### Phase 2 OUTCOME (2026-07-19): INFEASIBLE — memory OC is a silent no-op on this stack

**No stable overclock frequency was established, because the memory clock never moved.**
`OD_RANGE` advertises `MCLK: 97Mhz 1500Mhz`, and writing `m 1 <MHz>` + `c` to
`pp_od_clk_voltage` is *accepted* — the OD table reads back the requested value — but the
live DPM table's top state stays pinned at **1258MHz**, confirmed by both `pp_dpm_mclk`
and `rocm-smi --showclocks`. Reproduced with **lactd fully stopped** and
`power_dpm_force_performance_level=manual`, so this is not a LACT conflict: amdgpu/SMU on
GFX1201 (Sapphire Pulse, vBIOS 023.008.000.068) takes the write and ignores it. There is no
other upward path — `pp_dpm_mclk` only *masks* existing states, it cannot redefine their
frequencies.

Windows could raise it because the Windows driver carries its own OD path and timing tables;
that capability is simply not wired up in amdgpu for this SKU. **Nothing to encode in a LACT
profile** — the Inference/Gaming profiles differ only in power cap (and the existing
−100MHz / −30mV offsets, which do apply).

#### Hardened 2026-07-19 (three ways the first conclusion could have been wrong, all checked)

The initial finding rested on an idle table read with LACT confounding the under-load leg.
Re-tested properly; it survived all three challenges:

1. **Missing OverDrive kernel param?** No — `/etc/modprobe.d` sets
   `amdgpu ppfeaturemask=0xFFF7FFFF`; PP_OVERDRIVE_MASK (0x4000) is SET. Consistent with the
   sclk/voltage offsets on the same interface working.
2. **Clock only regenerates under load?** No — with lactd stopped, requesting **1500MHz**
   (+19%) the OD table reads 1500 while `rocm-smi` sampled 30× *during* a live benchmark
   shows **1258MHz throughout**, and tg256 is 63.74 → 63.78 t/s (Δ 0.06%, pure noise).
3. **VRAM pinned low by `performance_level=manual`?** Community reports suggested manual mode
   caps RDNA4 VRAM below max. **FALSIFIED for this card** — manual / auto / high all sit at
   1258MHz with tg256 64.21 / 64.06 / 64.40 t/s (identical within noise). `high` does shift
   fclk (1800+2400 vs 2016+818MHz) with no tg effect, so fabric clock is not the decode
   bottleneck either. Mark is not holding it wrong; the card is already at its max memory state.

**Reporting-convention caveat — important before quoting "1259MHz" publicly.** Other RDNA4
reports show `OD_MCLK 1: 2519MHz` and live VRAM ~2516MHz, roughly 2× what this card reports.
This is almost certainly real-DRAM-clock vs doubled/effective reporting (1258 × 2 = 2516), not
a half-speed card: LACT reports the full-spec **644 GiB/s** for 20 Gbps GDDR6 on 256-bit, and
measured decode (64 t/s × 6.24 GiB ≈ 400 GB/s effective, ~62% MBU) is normal-to-good for
llama.cpp. Quoting "my card maxes at 1259MHz" without that context invites a correct-sounding
rebuttal that we're misreading our own hardware.

**Scope the claim accordingly.** Supported: *memory overclocking is accepted-and-ignored on
RDNA4/gfx1201 under amdgpu*, and this reproduces community reports, so it is not local
misconfiguration. NOT supported: that this card underperforms its rated bandwidth, that AMD
regressed something that previously worked here (RDNA3 memory OC reportedly does work — this
looks never-wired-up for RDNA4 rather than broken), or anything about AMD's stack beyond the
memory-OC path.

**Two silent-failure traps this run exposed, both worth carrying forward:**

1. *LACT reasserts every 5s.* `apply_settings_timer: 5` in `/etc/lact/config.yaml` means a
   direct sysfs OD write is reverted within 5 seconds. The v1 read-back at +2s showed the new
   value and the benchmark 30s later ran at stock. Any future sysfs GPU tuning here must
   either stop lactd or go through LACT — and must re-read the *live* table, not the OD table.
2. *Verify the knob moved before trusting the gate.* The ladder reported PASS at 1300/1350/1400
   with bit-exact PPL and flat tg — all of it re-measuring 1258MHz. The tell was physical, not
   logical: +3.3% clock yielding +0.14% tg on a bandwidth-bound decode is not a pass, it is
   evidence the clock did not change. **A stability gate that cannot fail is not a gate.**
   Ladders must assert the live DPM value at each step and abort if it did not move.

### Harness bugs found (llama.cpp b9966-f27268914) — upstream-report candidates
- `llama-cli` no longer supports `-no-cnv` (upstream split raw completion into
  `llama-completion`). It **warns and continues anyway** in interactive mode, then busy-spins
  printing `"> "` on stdin EOF: 104M prompt lines, **241GB into a pipe over 14h**, one core
  pegged, at stock clocks. A REPL at EOF should exit, not spin.
- `llama-completion` **SIGABRTs** on Gemma-4-12B-QAT: uncaught exception in
  `common_chat_templates_apply` reached via `common_chat_format_example` — a raw-completion
  tool aborting while formatting a chat-template *example banner*. Workaround:
  `--chat-template chatml` (runs, but wraps the prompt in the wrong template).
- Consequence for future receipts: the determinism gate is now **`llama-perplexity` over a
  fixed corpus** (`scratchpad/pwr9070/ppl_corpus.txt`), verified bit-reproducible run-to-run
  at stock (PPL = 2171.5359 twice). No chat-template path, no interactive mode, exits clean.
  Every subprocess in a ladder gets `timeout` + `</dev/null`.
