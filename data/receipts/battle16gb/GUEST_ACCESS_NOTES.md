# Guest access to the RX 9070 XT control plane — what recovers itself, what needs Mark

For sharing `mark-desktop-pc` (Tailscale `100.78.69.108`, LAN `10.0.0.5`) with a remote
collaborator. Written 2026-07-29 after offering buun access for RDNA4 turbo work.

## The short version for a guest

```
gpu-recover.sh status     # what's running, VRAM, clocks, temp, driver faults, open ports
gpu-recover.sh kill       # stop stuck llama jobs and free VRAM
gpu-recover.sh watch      # same as status, refreshed every 10s
```

`kill` is safe to run any time. If it reports VRAM still high with no llama process, that is
the one case that needs Mark.

## Why there is no remote GPU reset (deliberate)

The 9070 XT is **`boot_vga=1` with three connected displays** (DP-1, DP-2, HDMI-A-2) driving
a live KDE Wayland session. A PCI bus reset or an `amdgpu` module reload would take Mark's
desktop down — the remote "recovery" would *cause* the outage it is meant to fix.

An earlier draft of this plan proposed exactly that and was wrong. The tool only kills
userspace processes holding the card; it never touches the device.

## What that covers — which is the failure mode that actually happens here

| date | event | outcome |
|---|---|---|
| 2026-07-29 | buun turbo4 perplexity → `[1]nan,[2]nan` | **process died, card kept working** |
| 2026-07-23 | Qwen3.5-35B-A3B → GPU memory access fault | **process died, card kept working** |
| 7-day journal | ring timeouts / amdgpu resets | **zero** |

In every observed case the process died and the GPU stayed healthy — recoverable by killing
userspace, no reboot, no Mark. A wedged *card* needing a bus reset has never happened on this
machine.

Note the NaN case **exits 0**, so a guest's own scripts may record it as a clean pass. Check
for the `Final estimate: PPL` line, not the exit code.

## Hardware watchdog: available, deliberately NOT enabled

The board has a working watchdog (`sp5100_tco`, AMD FCH, 60 s heartbeat) — verified loading
and creating `/dev/watchdog`, then unloaded. Enabling it plus `RuntimeWatchdogSec` would
convert a hard kernel hang into a ~60 s auto-reboot instead of an indefinite wait.

**Mark's call was to skip it**, and the reasoning is sound: a hardware watchdog cannot tell
"kernel hung" from "kernel alive but crawling." Heavy VRAM pressure could trip a reboot on a
machine that would have recovered, killing a long run — trading a failure mode that has
*never* fired for one that plausibly could. Revisit if a real hang ever occurs.

Nothing was persisted: no `/etc/modules-load.d` entry, `/etc/systemd/system.conf` untouched.

## Scheduling, not sharing

One GPU, one experiment at a time — concurrent work corrupts both parties' measurements.
This session has already had to serialise its own runs for exactly this reason.

- Only `mark-desktop-pc` and `ai-p100-sli` are on the Tailnet. **`.194` (quad P100) is not**,
  so guest access means the desktop specifically.
- The desktop is also Mark's daily driver and the control plane these agent sessions run on.
- Gaming is rare; Mark will give notice rather than pre-empt a scheduled run.

## Tool

`/home/mark/bin/gpu-recover.sh` — verified end to end 2026-07-29: detected a live
llama-server, SIGTERM freed 10.24 GiB → 2.06 GiB, no SIGKILL escalation needed, and correctly
reports "none" when idle.

Its process pattern is deliberately narrow
(`(build|build_hip|build-gfx[0-9]+)/bin/llama-(server|perplexity|bench|cli)`): a bare
`pkill -f llama-server` also matches the shell running the script, which silently killed three
probes during this campaign.
