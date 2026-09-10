# SYS-01 rep1 — VOID as a model measurement (harness defect, not model failure)

**2026-08-30.** `Qwen3.8-27B-Q6_K` on `.73`, `reasoning_effort: medium`, temp 0, K=1.

## Outcome

**No answer. Hit the 25-turn limit.** 25 commands, of which **10 returned `not captured`** — 40 %
of the model's investigation was spent on evidence I never recorded.

This run is **not evidence about the model** and is not scored. The item measured my capture set.

## What it got right before running out of turns

Worth recording, because it contradicts the SYS-02 result and shows the two items discriminate
differently:

- Reached `modprobe exfat` and probed the module tree — the correct diagnostic path.
- **Hit the empty `/boot`, then retried with `sudo` and got the real listing.** That is trap T1,
  the one **Claude failed** on the live system. The model recovered where I did not.
- Followed up with `sudo find /boot -name "*vmlinuz*"` and read the Limine directory — the right
  way to check a rollback path exists.

## The gaps, and which are honestly fixable

| command | fixable? |
|---|---|
| `find /lib/modules/$(uname -r) -name "*exfat*"` | **yes** — derivable: the parent directory is proven absent, so the find matches nothing |
| `ls /lib/modules/$(uname -r)/kernel/fs/` | **yes** — same derivation, ENOENT |
| `findmnt` (no args) | partly — only `findmnt /boot` was captured |
| `dmesg` | **no** — pre-reboot ring buffer, gone forever |
| `pacman -Qs linux` | **no** — searches package *descriptions*; only `pacman -Q` was captured |
| `sudo cat /boot/limine.conf` | **no** — rewritten by the 2026-08-30 upgrade |

Reconstructed only the two strictly-derivable ones, documented in `state/00_capture_meta.txt`.
The rest are recorded as permanent gaps rather than invented — a fabricated `dmesg` would make the
item measure fiction, which is worse than a smaller item.

## The lesson for the corpus

**Capture must be driven by what an investigator would plausibly run, not by what the person who
already knows the answer ran.** My capture set retraced my own successful path. The model took a
reasonable different route and fell off the edge of it.

Concrete rule going forward: before an item is considered ready, run it once at a **high turn
limit purely as a capture probe**, collect every `not_captured` command, and either record the
real output *while the fault is still live* or declare the gap explicitly. A capture probe is
cheap and it is the only way to find these.

That also means **SYS-01 should have been captured with a probe run before the reboot**, and was
not. The reboot was needed to fix the machine, so some of this was unavoidable — but the probe
would have caught `dmesg` and `limine.conf` while they still existed.

## Status

SYS-01 is **not retired**. With the two derivable gaps filled it is worth rerunning, and the
`/boot` T1 recovery above is a genuine signal. But any rerun must be reported as "on a
partially-reconstructed item" until a live re-capture is possible — the next kernel upgrade that
lands without a reboot will provide one naturally.
