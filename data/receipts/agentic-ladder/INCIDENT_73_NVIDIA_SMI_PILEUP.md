# Incident -- `.73` load 770 from an unbounded `nvidia-smi` pileup, 2026-09-19 ~14:38-14:55

**Node recovered by Mark**: power button, disabled guiTop polling on the telemetry Pi, killed the
stuck `nvidia-smi` processes. Load fell 770 -> 7, processes 3888 -> 364.

## What was observed

At 14:46, `.73` carried **862 stuck `nvidia-smi` processes, 1,762 sshd sessions, load average
769.95, 13 of 15 GB RAM consumed**. SSH degraded from slow, to timeout, to `No route to host`.

## Timeline, from `sar -q` on the node itself

| time | load-1 | plist-sz |
|---|---:|---:|
| 14:30:00 | 0.88 | 740 |
| **14:40:03** | **54.88** | **1342** |
| 14:50:59 | 568.98 | 5235 |

**The cascade was already underway at 14:40:03. The agentic-gate setup script ran at 14:41:52.**

## Correction to my own first account

I initially told Mark *"`.73` is down and I put it there"*, reasoning that killing a
26 GB llama-server had left the GPU unable to answer `nvidia-smi`. **That was wrong, and it was
asserted from a plausible story rather than from evidence.**

The evidence against it:

1. **The kill never executed.** The script's first action inside its ssh block was
   `nvidia-smi --query-compute-apps=pid`, to *identify* the holder before signalling. It hung
   there. No `~/argus_*.pid` exists and no arm server was ever started.
2. **The running llama-server predates the script.** PID 2808170, started **14:38:55**, three
   minutes before the script ran.
3. **`sar` shows the climb starting before the script.** Load 54.88 and 1342 processes at
   14:40:03, against 0.88 and 740 at 14:30.

**The script's contribution was additive, not causal:** its drain loop would have issued up to 60
further `nvidia-smi` calls into an already-hanging driver, and it held an ssh session open. It
arrived about two minutes into a degrading situation.

## Probable chain, stated as probable

The llama-server running since 14:07 died around 14:38; the wake proxy restarted it at 14:38:55
(`WP_START_CMD`), which is exactly when `plist-sz` begins climbing. Most likely: GPU enters a state
where `nvidia-smi` blocks instead of returning -> the telemetry Pi polls it at roughly 1 Hz over
ssh -> every poll becomes a resident process -> ~840 accumulate in ~14 minutes, matching the
observed 862. **What put the GPU into that state first is not established** and should not be
claimed.

## The actual defect, and the one-line guard

**`nvidia-smi` can block indefinitely.** Every caller that does not bound it turns a stuck driver
into an unbounded process leak. A 1 Hz poller with no timeout is a fork bomb waiting for a GPU
fault.

```bash
timeout 10 nvidia-smi --query-gpu=... || echo "GPU NOT ANSWERING"
```

Any hung call then dies in 10 s instead of living forever, the pileup cannot form, and -- just as
important -- **the caller learns the GPU is unhealthy instead of hanging silently.**

**Every `nvidia-smi` invocation in this repo's harnesses should be `timeout`-wrapped.** The
telemetry Pi's poller is outside this repo; Mark has disabled it for now, and it is the component
that most needs the guard since it is the one running unattended at 1 Hz.

## A second lesson, about the verification and not the GPU

The setup script's drain check was:

```
for i in $(seq 1 60); do sleep 2
  HI=$(nvidia-smi --query-gpu=memory.used ...)     # <-- the thing being verified
  [ "$HI" -lt 500 ] && break
done
```

**The check was built out of the component that had failed.** When `nvidia-smi` hung, the
verification did not report a problem -- it became another hung process. This is the same shape as
`readiness-probes-lie`: a probe must be able to *fail*, and a probe that shares a failure mode with
its subject cannot. A drain check should confirm the process is gone (`kill -0`) and treat an
unanswerable `nvidia-smi` as its own distinct alarm.

## Cost

No data lost. The fidelity ladder was complete and committed (`bd0804c`); the agentic panel had
produced no measurements; the `argus/agent-home/config.yaml` edit never happened, verified by the
absence of the `.orig` backup the script writes before touching it.

---

# ROOT CAUSE FOUND -- 2026-09-19 15:00: the proxy suspended the node mid-load

The "probable chain" above is superseded. The proxy's own log names it:

```
14:38:55  suspend: stopping llama-server before suspend (VRAM spill would not fit)
14:38:56  start: launching llama-server          <-- a request arrived MID-SUSPEND
14:39:04  suspend: suspended                     <-- the suspend committed anyway
14:41:54  start: llama-server EXITED after 178s
```

The idle timer expired exactly 1800 s after the daily driver was restored at 14:07. The proxy
began suspending; **one second later a request triggered a load; the suspend completed anyway and
the machine entered S3 with llama-server mid-load.** The GPU came back in a state where
`nvidia-smi` blocks instead of returning, and the telemetry Pi's unbounded ~1 Hz poll then
accumulated 862 resident processes.

## Three defects, all in `wake_proxy.py`

1. **The suspend path took no lock.** `idle_monitor` called `N.sleep_node()` directly while
   `ensure_ready()` acquires `self.lock`. Wake and suspend could interleave freely.
2. **The suspend was armed and uncancellable.** `systemd-run --on-active=2` with no `--unit`
   creates an anonymous transient timer. Once armed, nothing could stand it down -- not even a
   wake request arriving in the 2 s window.
3. **No last-moment re-check.** `sleep_node()` unloads llama-server, sleeps 8 s, *then* arms the
   suspend. That 8 s window is ample for a request to arrive and a load to begin, and nothing
   revalidated before committing.

## Fixes applied

1. `idle_monitor` now holds `N.lock` across the suspend and **re-verifies idle after acquiring
   it** ("stood down -- a request arrived while acquiring the lock").
2. The transient unit is **named** `apollo-suspend`, and `ensure_ready()` stops
   `apollo-suspend.timer/.service` before waking or loading. Verified the node's sudoers permits
   the stop.
3. `sleep_node()` **aborts** if a request arrived within 10 s of the unload window closing.

## What this reframes

The `timeout 10` guard on `nvidia-smi` -- the first fix, and a correct one -- addresses the
**amplifier**, not the cause. Without it a GPU fault becomes an unbounded process leak. But the
fault itself was **self-inflicted by the proxy suspending a machine mid-load**, which no timeout
would have prevented.

Both fixes are worth having, and it is worth being clear about which is which: **one stops a fault
becoming a catastrophe, the other stops the fault.**
