# `.194` power economics: 216 s to boot, 218 W to idle, and the BMC was never on the wire

**2026-09-03.** `.194` (Supermicro, 2x Xeon E5-2650 v3, 4x P100, 60 GB DDR4-2133 ECC).

## Measured

| | |
|---|---|
| graceful shutdown (`systemctl poweroff` -> chassis off) | **16 s** |
| cold boot (`chassis power on` -> SSH answering) | **216 s (3 m 36 s)** |
| idle, no models loaded, load 0.14 | **218–226 W** |
| of which 4x P100 idle | ~109 W (27.6 / 28.8 / 26.1 / 26.4) |
| peak observed | 494 W |
| standby | ~27 W (DCMI reports **0 W** when off — that is a measurement floor, not a reading) |

**Idle-to-load is only ~100 W.** Everything this machine has ever done costs about 100 W over
doing nothing, so there is no meaningful idle optimisation to find — the only real lever is *off*.

## Consequences

- **Wake-on-demand is not viable.** `.73` works because S3 resume is ~10 s, so a request stalls
  briefly and succeeds. At 216 s a proxy converts "machine is off" into "machine is broken."
- Economics at ~$0.14/kWh: **~$267/yr** left running versus **~$72/yr** if off except ~4 h/day use.
- Design: manual control (`tools/s194.sh on|off|status`). Idle-shutdown deferred — the failure mode
  is killing an overnight run, and `uptime` reports stale SSH sessions so session count is a bad
  idle signal.

## The BMC was configured correctly the whole time — into an unplugged port

`Port mode 02 = failover` and a static IP on the wrong subnet (`192.168.100.76/16`, gateway
`192.168.9.1`). Fixing the address was not enough; forcing `01` (shared) and a warm reset was not
enough either. Cause:

```
enp4s0f0 (LAN1)  DOWN, NO-CARRIER   <- BMC shares THIS port
enp4s0f1 (LAN2)  UP, 10.0.0.194     <- the cable was here
```

Supermicro shared/failover BMC mode shares **LAN1**. The cable was in LAN2, so the BMC was
faithfully sharing a port with nothing plugged into it. Invisible to every diagnostic that only
inspects the BMC.

**Trap avoided:** netplan configured `dhcp4: true` on LAN2 only, and `10.0.0.194` was a *dynamic*
lease. Moving the cable naively would have left the host with no address, in a closet. Fixed by
giving LAN1 a **static** `10.0.0.194` first (plus `accept-ra`/`dhcp6` for parity), then moving the
cable. Host moved ports without dropping — uptime continued unbroken.

Backup: `/root/netplan-backup-1788461857.yaml`. Recovery if ever needed: restore it and
`netplan apply`, or just move the cable back to LAN2, whose DHCP config is untouched.

## Also fixed

`.194` was on `Etc/UTC` while the control plane is `America/Indiana/Indianapolis`. This caused a
real misreading during the session (file timestamps read as local, producing a wrong claim about
when work happened). Now `America/Indiana/Indianapolis`, matching the desktop to the second.
**Receipts written earlier today carry UTC timestamps.** `.73` still unchecked — it was asleep.

## Tooling

`tools/s194.sh {on|off [--force]|status}`. Credentials in `~/.ipmi_194` (0600, **never** in the
repo), read literally with `sed` rather than sourced — sourcing executes the file, so a password
containing a quote, backtick or `$` breaks parsing or runs as code. IPMI errors are surfaced, not
swallowed: a blank field was indistinguishable from "off", which is the wrong failure mode for a
power tool. `off` refuses when `llama-server` is running unless given `--force`.
