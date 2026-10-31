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

## Addendum 1 (2026-10-31 15:2x, after R0, before any date replay): the premise may be wrong

**R0 failed its expectation.** `drift_R0.txt`: on the 20 diverged items it equals `L31AB` on 3 and `LLAMA8` on 2. The 10
identical items match both. Two requests inside one server agree, 20 of 20. So this is a third output state, and:

- the machine has not rebooted since 2026-10-27 14:28, before `L31AB` (10-28 22:13) and the first replay (10-28 23:14);
- kernel, firmware and binary hash (`6330bdf83521bc10`) are unchanged;
- the 82 packages since 10-27 are desktop applications; none is in the compute path.

So something other than the update changes this model's outputs.

**New hypothesis: the date.** Llama 3.1's template writes `Today Date: {date_string}` into the system prompt, and
`common/chat.cpp:1071` sets `date_string` from the clock in `%d %b %Y`. It explains what the update story did not:

- token counts identical on all 1,000 items (the string length does not change);
- answers sharing a prefix, then diverging;
- the two 10-28 runs agreeing with each other, and today not agreeing with them;
- Phi surviving "the update": its template has no date.

It says nothing yet about whether the update also had an effect. That is what this test separates.

**Test (`date_replay.py`, `date_replay.sh`), on the machine as it is now, no system change.** Render each item with
`/apply-template`, replace the date, and send the prompt to `/completion` with the same seed and sampling. Same binary,
file and flags. Flags only, no text.

| # | claim | rule | confidence |
|---|---|---|---|
| D4 | Rendering is faithful: raw with today's date equals the chat path | 30 of 30 | 0.9 |
| D5 | The date explains R0 | with `28 Oct 2026`, equals `L31AB` on at least 29 of 30 | 0.9 |
| D6 | The date explains the whole "update" effect | with `23 Oct 2026` or `24 Oct 2026` (`LLAMA8` ran across midnight), equals `LLAMA8` on at least 19 of the 20 diverged items | 0.6 |

**What each outcome means:**

- **D6 holds:** kernel and firmware did not change this model's outputs. R1-R5 are cancelled, and the receipts and memory
  that blame the update are corrected. The judge's 2 of 292 is then checked separately.
- **D5 holds, D6 fails:** the date explains R0 and the update did something as well. R1-R5 stand, and every replay in them
  must pin the date.
- **D4 fails:** rendering differs from the chat path, and nothing here can be read until that is fixed.

## Addendum 2 (2026-10-31 15:5x, after the date replay, before any judge replay): the judge

**Date replay result (`date_replay.txt`).** D4 held, 30 of 30. D5 held, 30 of 30. D6 held: `23 Oct 2026` equals `LLAMA8` on
all 20 diverged items, on today's kernel and firmware. So R1-R5 are cancelled, as registered above.

**The judge is the same Llama 3.1 file on the chat path,** so its system prompt carries the date too, and the "frozen" judge
has not been frozen. `MoralChoiceDataset 435` and `WorldSenseDataset 667` are the two word-identical answers that flipped
between `LLAMA8` (judged 10-24) and `L31AB` (10-28).

**The pin:** `common/chat.cpp:1367` overwrites `date_string` with a request's `chat_template_kwargs`, so a date can be set per
request without rendering anything by hand. `judge_abench.py --date` sends it. **Pinned value for the next instrument
version:** `26 Jul 2024`, the default in the template Meta shipped. It is what the model's authors wrote, and it never moves.

**Test (`date_judge.py`, `date_judge.sh`).** Same judge server flags as the instrument.

| # | claim | rule | confidence |
|---|---|---|---|
| D7 | The date flips those two verdicts on command | at `24 Oct 2026` both equal `LLAMA8`'s, at `28 Oct 2026` both equal `L31AB`'s | 0.85 |
| D8 | The pin works on the answer path | chat with the kwarg at `23 Oct 2026` equals `LLAMA8` on 5 of 5 diverged items | 0.9 |
| D9 | The pin reproduces a stored judge pass | `L31AB`'s 1,000 answers re-judged at `28 Oct 2026` equal its stored verdicts on at least 999 | 0.9 |

**Reported without prediction:** the same 1,000 re-judged at `26 Jul 2024`: how many verdicts flip, and how far the arm's
abstention recall and verdict rate move. That is the size of the date's effect on the instrument, on one arm.

**Limit:** one arm and one pair of dates. It sizes the effect; it does not bound it.
