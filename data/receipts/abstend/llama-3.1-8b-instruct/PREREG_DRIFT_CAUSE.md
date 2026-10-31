# Pre-registration -- which part of the 2026-10-27 update changed Llama 3.1 8B's outputs on the 9070?

**Registered 2026-10-31, before any replay in this file.**

**Background.** The 10-27 update changed T 0.8 answers on 708 of 1,000 AbstentionBench items and 2 of 292 greedy judge
verdicts, with the same binary and no ROCm package change (`RESULT_llama-3.1-8b-instruct.md`). It changed four things at
once:

- the kernel, `linux-cachyos` 7.2.9-2 to 7.3.0-4;
- the GPU firmware, `linux-firmware-amdgpu` 1:20260916-1 to 1:20261019-1;
- mesa 26.2.4 to 26.2.5;
- LLVM 23.1.1 to 23.1.4.

**Prior art checked:** `ledger_precheck.py "kernel firmware update changes outputs reproduction"` -> receipts found: the
result above established that the change exists and is deterministic. **What this adds:** which change caused it.

**Read from the cached packages before any reboot.** Firmware cannot be ruled out offline. For this card (gc 12.0.1, PCI
device 0x7550) the update replaced the compute and gfx microcode:

| blob | 20260916 | 20261019 | loaded now (`fw_version/`) |
|---|---|---|---|
| `gc_12_0_1_mec` | 0xd7a (451,552 B) | 0xda2 (259,584 B) | 0xda2 |
| `gc_12_0_1_me` | 0xc12 | 0xc26 | 0xc26 |
| `gc_12_0_1_pfp` | 0xc76 | 0xc94 | 0xc94 |

`uni_mes`, `psp_14_0_3_ta`, `dcn_4_0_1_dmcub` and `vcn_5_0_0` also changed. No package touching the kernel, firmware, mesa,
LLVM or ROCm has changed since 10-27 (pacman log).

## Method

`drift_replay.sh <label>` replays the 30 items of `replay_abench.py` (20 that diverged across the update, 10 that did not)
on a fresh server with the same binary, file and flags as `LLAMA8` and `L31AB`. Clef is paused and restored around it. It
writes `drift_<label>.json`, `.txt` (equality flags, no item or answer text) and `.state` (kernel, packages, every
`fw_version` file, PCIe link).

Mark performs every system change. Each state is one boot:

| label | case | kernel | firmware | expected if nothing else moved |
|---|---|---|---|---|
| R0 | old | 7.3.0-4 | 20261019 | equals `L31AB`, 30 of 30 |
| R1 | new | 7.3.0-4 | 20261019 | equals `L31AB`, 30 of 30 |
| R2 | new | 7.3.0-4 | 20260916 | the test of firmware |
| R3, only if R2 does not restore | new | 7.2.9-2 | 20260916 | the test of the kernel |
| R4, only if R3 restores | new | 7.2.9-2 | 20261019 | separates the kernel from the pair |
| R5 | new | 7.3.0-4 | 20261019 | equals `L31AB`, 30 of 30: the machine is back |

**The case move is one change and gets its own boot.** The GPU stays in the same slot, with no new riser. R1 clears the move
before anything is blamed on software.

**Gate on every firmware step: a rollback must prove it loaded.** The pacman hook rebuilds the initramfs on a firmware path
change, and the `kms` hook carries the blobs. A rollback that does not take would read as "firmware is innocent", so:
- R2 and R3 count only if `.state` shows `mec_fw_version` 0x00000d7a;
- R1, R4 and R5 count only if it shows 0x00000da2;
- R3 and R4 count only if `uname -r` shows the older kernel.

**Decision rule, "restores":** `n1_eq_LLAMA8` on at least 19 of the 20 diverged items. Between 1 and 18 is partial and is
reported as such. If R3 does not restore, kernel and firmware are not the cause, and mesa and LLVM (both cached) are next,
under a further addendum.

## Predictions

| # | claim | rule | confidence |
|---|---|---|---|
| D1 | Moving cases changes nothing | R1 equals `L31AB`, 30 of 30 | 0.95 |
| D2 | The firmware alone did it. The compute microcode is the piece that runs the work | R2 restores | 0.55 |
| D3 | The change is reversible | R5 equals `L31AB`, 30 of 30 | 0.95 |

## Limits stated now

- **One model, one binary, one card, 30 items.** Phi on buun survived the same update bit for bit, so whatever the cause
  is, it does not reach every code path.
- **This finds the package, not the mechanism.** A firmware result would say which update did it, not why.
- **The reference is stored output.** `LLAMA8` is the only record of the pre-update state, and it cannot be regenerated
  unless a rollback restores it.
