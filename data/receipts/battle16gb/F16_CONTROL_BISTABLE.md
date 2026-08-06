# The f16 control on Polaris is bistable within a single build — byte comparison at K=1 is invalid there

RX 580 8 GB (Polaris10/GCN4, subgroup 64), RADV, CachyOS live USB. Date 2026-07-31.
`vulkan-radeon 3:26.1.6-1`, `mesa 3:26.1.2-1`, kernel `7.0.11-1-cachyos`.
Probe: Crow-9B IQ4_XS, `-ctk f16 -ctv f16 -fa on -np 1 -c 16384`, temp 0, `cache_prompt:false`,
"Write a 500-word essay about Linux.", 500 max tokens.

**No turbo codec is involved anywhere in this test.** Whatever it finds is a property of the
rig, not of turbo3.

## Result — BOTH builds bistable, 5 of 6 cells scored

The run reached rep 3 before `.76` lost power at the bench (physical — a cat, not software).
The driver log stops at 4 cells, but the response files on disk go further; these were scored
from the artifacts directly.

| cell | build | sha | state |
|---|---|---|---|
| w64_rep1 | `11a8377bd` | ad9dd4fa776f | STATE-A |
| merge_rep1 | `8a891f4b5` | ad9dd4fa776f | STATE-A |
| w64_rep2 | `11a8377bd` | ad9dd4fa776f | STATE-A |
| **merge_rep2** | **`8a891f4b5`** | **22d6baa6872c** | **STATE-B** |
| **w64_rep3** | **`11a8377bd`** | **22d6baa6872c** | **STATE-B** |
| merge_rep3 | `8a891f4b5` | — | truncated JSON (killed mid-write by power loss) |

**Each build produced both states.** `11a8377bd`: A, A, B. `8a891f4b5`: A, B. Same binary, same
RADV, same session, same 7884 MiB free at every cell.

**The f16/f16 control is bistable within a single build, on both builds tested.** Two states,
`ad9dd4fa776f` (1903 chars, gzip 0.5097) and `22d6baa6872c` (1893 chars, gzip 0.5024).

This is stronger than a single build flipping. If only the merge arm had varied, "the merge
introduced instability" would remain live. Both arms varying eliminates the build entirely —
matching the diff, which touches no Vulkan source.

Pooled across both builds: **3 STATE-A, 2 STATE-B in 5 draws.** Not a rare glitch; the two
states are of comparable frequency. Too few draws to call the ratio.

## What this retracts

**1. My "execution-order dependent" explanation to Tom is falsified.** I told him the f16
control does not drift with time but depends on which cell ran immediately before it, and that
fixing cell order makes reproduction exact. Here, position and predecessor were held fixed and
the output still flipped. That explanation is dead.

**2. `TURBO3_241_MERGE_HEAD_INCONCLUSIVE.md`'s framing of the changed control is superseded.**
That receipt raised the merge build as one candidate for the `kf16_vf16` change. It was not the
merge: the merge build produces *both* states on its own. Nothing in `8a891f4b5` shifted the
Vulkan path — consistent with the diff, which touches no Vulkan source (the 7,440-line delta
between `11a8377bd` and `8a891f4b5` is entirely the DSV4 port).

## What survives

**The #241 wave64 confirmation stands.** It never rested on a single draw: 4/4 turbo3 cells
moved out of the corrupt band while 3/3 turbo4 cells stayed byte-identical, a seven-cell
pattern with a mechanism that explains it. Bistability of one control cell does not touch that.

**But the phrasing I sent Tom was stronger than the evidence.** I described a byte-identical
baseline. The baseline is bistable, so the correct claim is "3/3 turbo4 cells reproduced
byte-identically in this run" — a per-run observation, not a stable property of the rig. Owed
as a correction, and it is small.

## Standing rule for this hardware

**Single-draw byte comparison on `.76` is invalid.** Any future GCN work there needs K≥3 per
arm, and any cross-run byte difference must clear the bistability floor before being
attributed to a build, a patch, or a driver.

Cause unknown and not investigated. Candidates: RADV/ACO scheduling nondeterminism, a
wave64-related reduction ordering, or the same unexplained temperature-0 nondeterminism this
project has now documented across six configurations on sm_60 Pascal
(`hermesagent20/SUMMARY.md`). Assuming Polaris was immune was an assumption, never a
measurement.

## Environment hazards recorded (both bit this session)

- **The live USB has amnesia.** A reboot lost `vulkan-radeon` entirely — `/usr/share/vulkan/icd.d/`
  held only `nvidia_icd.json` and `virtio_icd.json`, and `llama-server --list-devices` printed
  "Available devices:" with nothing under it. The GPU was fine (PCI present, `amdgpu` bound,
  `/dev/dri/card1` there); the driver was simply gone. **A missing driver reads exactly like a
  dead GPU.** Reinstalling pulled RADV 26.1.6 against the ISO's mesa 26.1.2, so any receipt
  from this box must record its own driver version in-band or it is not reproducible.
- **The Ventoy USB mounts at `/dev/mapper/sdb1`, not `/dev/sdb1`** — the raw node returns
  `Can't open blockdev`.

## Provenance

- `f16_bistab_artifacts/` — all 6 responses + per-cell server logs + driver log (pulled
  2026-07-31 after the box came back; the log stops at 4 cells, the responses go to 6)
- Script: `scratchpad/f16_bistability.sh` (interleaved by design, so environmental drift
  cannot align with one arm; VRAM-free precondition per cell; 420 s curl cap)
- Reference SHAs: `turbo3_w64_artifacts/`, `turbo3_merge_artifacts/` (both already durable)
