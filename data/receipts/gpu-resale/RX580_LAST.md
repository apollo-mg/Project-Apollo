# RX 580 (last of three) -- pre-sale test report (XFX 8GB, ex-mining BIOS)

**Date:** 2026-10-15, 15:11-15:48 EDT. **Rig:** the control-plane desktop (5700X3D, CachyOS, kernel 7.2.9),
card on the RAGEER PCIe 4.0 riser in place of the RX 9070 XT. **Script:** `gpu_presale_test.sh rx580_last`
(commit `a4d08554`). Raw output: `rx580_last_report.txt`, `rx580_last_soak.csv`.

Which of the three cards this is is not recorded: only card #1 has an earlier report (`RX580_CARD1.md`), and the
two cards sold since (08-18, ~10-06) were not logged by serial. Its identity matches card #1 exactly, so it is
either card #1 or a sibling flashed with the same mining BIOS.

## Verdict

**Healthy, with the same mining BIOS as card #1.** Zero VRAM errors, no crashes, no driver errors, all five
outputs present. The core clock is capped at 1150 MHz (~14 % under stock); that is the disclosure item.

| | this card | card #1 (07-29) | stock RX 580 |
|---|---|---|---|
| model | XFX RX 580 8GB (`1682:c580`) | same | |
| VBIOS | `113-58085SHD1-M80` | same | |
| VRAM | 8 GB (8,589,934,592 B) | 8 GB | 8 GB |
| core max | 1150 MHz | 1150 MHz | ~1340 MHz |
| memory max | 2100 MHz | 2100 MHz | 2000 MHz |
| power cap | 145 W | 145 W | 185 W |
| outputs | DP-1, DP-2, DP-3, HDMI-A-1, DVI-D-1 | all present | |
| link | PCIe 8.0 GT/s x16 (Gen3) through the riser | 5.0 GT/s x16 on the bench rig | |

## Soak -- 30 minutes, PASS

`glmark2-wayland --run-forever`, telemetry every 10 s (180 rows). glmark2 cycles scenes, so this is a moderate
load (22 of 180 samples at >= 90 % busy), the same method as card #1.

- temperature mean 61.5 C, max 70 C
- core held at exactly 1150 MHz whenever busy; memory 2100 MHz
- power max 91.2 W
- load crashes: 0; amdgpu errors in dmesg: none
- glmark2 score at stop: 14201

## VRAM integrity -- PASS

`memtest_vulkan`, ~7 minutes, 5,699 iterations, write ~199 GB/s, verify ~135 GB/s:
"memtest_vulkan: no any errors, testing PASSed."

## Setup note (not a card fault)

Plugging in the desktop's 3440x1440 OLED froze KWin: its saved output config from the 9070 XT (165 Hz, HDR, wide
colour gamut) cannot be applied on Polaris (`[drm] *ERROR* Unsupported screen format RA24`, then KWin "Applying
output configuration failed!"). Both 1080p monitors (DisplayPort and HDMI) worked throughout.
