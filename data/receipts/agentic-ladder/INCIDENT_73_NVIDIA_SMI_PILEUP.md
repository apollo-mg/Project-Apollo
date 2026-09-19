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
