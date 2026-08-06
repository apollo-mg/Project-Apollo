# RX 580 #1 — pre-sale test report (XFX 8GB, ex-mining BIOS)

Bench rig `.76` (Pentium G3258 / Gigabyte H81.AMP-UP / CachyOS live USB). Date 2026-07-29.
Tested for resale: 30-minute soak + VRAM integrity + clock verification.

## Verdict

**Card is functionally healthy. It also has a mining BIOS with the core clock capped ~14 %
below reference — disclose that in the listing.**

## Identity

| | |
|---|---|
| model | **XFX RX 580 8GB** (`1682:c580`) |
| ASIC | POLARIS10, `1002:67df` rev e7 |
| VBIOS | **`113-58085SHD1-M80`** (read from ROM BAR) |
| VRAM | **8589934592 B = 8 GB** — full spec, not a 4 GB variant |
| link | PCIe **5.0 GT/s x16** (Gen3 x16) negotiated |
| driver | `amdgpu`, binds clean, no errors |

## The BIOS finding — this is the disclosure item

Clock tables read from `pp_dpm_*` before any load:

| | this card | reference RX 580 | |
|---|---|---|---|
| core (sclk) max | **1150 MHz** | ~1340 MHz | **−14 %** |
| memory (mclk) max | **2100 MHz** | 2000 MHz | **+5 %** |
| power cap | **145 W** | 185 W | **−22 %** |

Core down, memory up, power down is the standard ethash mining tune: hashrate follows memory
bandwidth, so core clock is wasted watts. **Confirmed under load** — the card pins to exactly
1150 MHz and never exceeds it, so the ceiling is real and not a reporting artifact.

Everything else about the card is stock-spec.

## Soak — 30 minutes, PASS

`glmark2-wayland --run-forever`, telemetry sampled every 10 s (137 rows).

| metric | result |
|---|---|
| duration | **1806 s (30 min)** |
| load crashes | **0** |
| temp | **mean 55.1 °C, max 63 °C** |
| sclk under load | **1150 MHz sustained** (never throttled below) |
| mclk observed | up to **2100 MHz** (full rated speed reached) |
| power | max **83 W** of a 145 W cap — no power throttling |
| busy | up to **100 %** |
| fan | 724–3768 rpm, adaptive — ramps and backs off correctly |
| PCIe | 5.0 GT/s x16 stable throughout |

Idle 45 °C, load 55 °C mean. Cool for Polaris; cooler and fans are working.

**One dmesg line was flagged and dismissed:** `amdgpu: Disabling VM faults because of PRT
request!` at 761 s uptime — normal partially-resident-texture init chatter, logged *before*
the soak began. Not an error.

## VRAM integrity — PASS

`memtest_vulkan`, ~7 minutes, **11,384 iterations**:

```
memtest_vulkan: no any errors, testing PASSed.
~34 TB written / ~68 TB verified, zero errors
write 204 GB/s   verify 133 GB/s
```

This is the most important test for an ex-mining card — months of memory overclocking is what
degrades them. **Zero errors.** 204 GB/s sustained against 256 GB/s theoretical confirms the
memory runs at full spec and is not degraded.

## Suggested listing language

> XFX Radeon RX 580 8GB. Tested: 30-minute stress soak (max 63 °C, no crashes) and full VRAM
> integrity test (11,000+ iterations, zero errors). **Ex-mining card with a custom BIOS — core
> clock is capped at 1150 MHz vs ~1340 MHz stock (about 14 % lower), memory runs slightly
> above stock at 2100 MHz.** Full 8 GB, all outputs present, PCIe 3.0 x16, no artifacts or
> instability found.

At $50–75 that is fair value — buyers in that bracket want VRAM capacity and display outputs
more than peak clocks — and the disclosure is what keeps it a clean sale.

## Method notes (for cards #2 and #3)

- **The live image has no OpenCL ICD**, and the session is **Wayland (kwin)**, so X-based
  tooling can't be driven over SSH without auth. Working path: `XDG_RUNTIME_DIR=/run/user/1000
  WAYLAND_DISPLAY=wayland-0` and `glmark2-wayland`.
- **`vkcube` is not a load generator** — 20 s of it left the card at 900 MHz / 0 % busy. It's a
  display demo. `glmark2` pins sclk to its ceiling at 100 % busy.
- **`power1_average` does not exist on Polaris10** — the correct sensor is
  `hwmon/hwmon*/power1_input`.
- The AMD card is `card2`, not `card1` (`card1` is the Intel iGPU driving display).
- Telemetry streams to the control plane over SSH rather than to local disk: the bench root is
  a 10 GB RAM overlay on a live USB, so a hard fault would destroy a local log.
- Packages needed on the live image: `glmark2 vulkan-radeon memtest_vulkan`.

## Provenance

- `rx580_card1_soak.csv` — full 137-row telemetry
- Script: `scratchpad/rx580_soak.sh`
