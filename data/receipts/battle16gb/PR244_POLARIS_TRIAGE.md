# PR #244 on Polaris: f16 path is byte-identical to pre-rebase; the 21-cell matrix failure was a cascade from one wedged GPU

`.76` bench rig — RX 580 8 GB (Polaris10/GCN4, **subgroup size 64**), RADV (Mesa 26.1.6),
CachyOS live USB, Pentium G3258 (2 cores, no AVX), 7 GB RAM. Model Crow-9B IQ4_XS (5.0 GB)
on exfat USB. Date 2026-08-02.

Builds compared:
- **ctrl** — `tqbin_w64`, build **9981** @ `11a8377bd` (Tom's wave64 ballot fix; the build
  that produced `TURBO3_241_WAVE64_FIX_CONFIRMED.md`)
- **pr244** — `tqbin_pr244`, build **10240** @ `c86e57d82` (Jabba's fork rebase), built on the
  control plane with `GGML_AVX/AVX2/F16C/FMA/BMI2=OFF`, `-march=x86-64-v2`,
  `.note.gnu.property` stripped

## Headline

| build | load | 80 tokens | decode | prompt eval | output sha |
|---|---|---|---|---|---|
| ctrl 9981 | 101 s | 75 s | 1.12 t/s | 4.05 t/s | `e5a1052c5273` |
| **pr244 10240** | 95 s | **69 s** | **1.23 t/s** | 4.48 t/s | **`e5a1052c5273`** |

`kf16_vf16`, `-c 16384 -b 1024 -ub 512 -fa on -ngl 99 --cache-ram 0`, temp 0, 80 tokens.

**Byte-identical output across a 259-build rebase.** Both servers stayed healthy and shut
down cleanly. On the f16 control path, PR #244 is not a regression — it is indistinguishable
from the pre-rebase build, and marginally faster.

`gpu_busy_percent` sampled **100** throughout. The GPU is doing the work; 1.1–1.2 t/s is
simply what this RX 580 does with IQ4_XS at 16k context. Not a CPU fallback.

## The 21-cell matrix failure was one hang, then a cascade

The first attempt (2026-08-01, 3 reps × 7 cells) returned **zero results** — every cell
logged `SERVER FAILED`. That reads like a build that cannot run. It was not.

Cell 1's server log:

```
0.00.029  load_model: loading model '/mnt/usb/crow9b.gguf'
1.38.177  model loaded
1.38.336  listening on http://127.0.0.1:8143
1.39.367  slot launch_slot_: id 0 | task 0 | processing task
16.39.525 srv stop: cancel task, id_task = 0
```

The server **loaded in 98 s and began generating.** It then ran **15 minutes** until the
900 s `curl` cap cancelled the request. The process would not die — `dmesg` showed
`llama-server` blocked in `dma_fence_wait_timeout` for 245 s and 614 s — so it held port 8143
and VRAM. Every subsequent cell then failed to bind, and all 20 reported `SERVER FAILED`
as a **consequence of cell 1**, not independently.

The same wedge is why `sshd` returned its banner in 0.0 s while sessions never established:
the box was alive, D-state tasks blocked session setup.

**Cell 1 was `kturbo4_vturbo3` — a turbo cell.** The f16 control cell (above) runs fine on
the same build. So the hang, if it is real, is turbo-specific rather than a PR #244-wide
failure. That test is the next step and is not yet complete.

### Corroborating physical evidence

The UPS reported **~30 W** draw for the box during the "run" — above idle but far below the
100–150 W an RX 580 pulls while generating. That is consistent with a stuck GPU rather than
active compute, and it was the first signal that the matrix was not progressing. Worth
keeping as a cheap external health check on this rig: **power draw distinguishes "working"
from "wedged" when ssh cannot.**

## Method errors that made this worse

1. **All artifacts were written to the exfat USB.** The master log came back **952 bytes with
   its beginning missing** — writes were lost. The 5 GB model reads went through the same
   mount. Logs now go to `$HOME` (RAM overlay); only the model stays on USB, since 3 GB free
   RAM cannot hold it.

2. **A 900 s per-cell timeout hid the failure mode for 15 minutes per cell** and let the
   cascade run for 3+ hours. At the measured 1.2 t/s, 500 tokens needs ~420 s, so 900 s was
   not unreasonable — but a hang detector should be tied to *progress*, not total budget.
   Triage now uses 80 tokens with a 240 s cap: healthy finishes in ~70 s, so a hang is
   unambiguous within 4 minutes.

3. **No dirty-box guard.** The runner started a new server after each failure without
   checking whether the previous one had actually died. It now aborts if any `llama-server`
   is alive, and reports explicitly if a PID survives `SIGKILL` instead of stacking servers
   on a wedged GPU.

## Live-USB operational note

`.76` loses `vulkan-radeon` on **every** reboot (live USB, no persistence). A missing RADV
presents exactly like a dead GPU. After any power cycle:

```
sudo pacman -Sy --noconfirm vulkan-radeon
sudo mount -t exfat -o uid=1000,gid=1000,rw /dev/mapper/sdb1 /mnt/usb
ssh-keygen -R 10.0.0.76     # host keys regenerate on each boot
```

Also note the CachyOS toolchain stamps `x86 ISA needed: x86-64-v3` on every locally linked
binary via `crt1.o`, regardless of `-march`. The G3258 has no AVX/AVX2/BMI2, so binaries
built on the control plane need `.note.gnu.property` stripped:
`objcopy --remove-section=.note.gnu.property <bin>`. This was already recorded in
`TURBO3_241_WAVE64_FIX_CONFIRMED.md`'s provenance and re-derived from scratch anyway.

## Limits

- **K=1 per build** on one cell. Adequate for "does it run and produce the same bytes,"
  not for a performance claim. The 75 s vs 69 s difference is a single draw and should not be
  read as PR #244 being faster.
- `F16_CONTROL_BISTABLE.md` established the f16 control on this box is **bistable** across
  runs. Two builds landing on the same SHA is therefore a *stronger* coincidence than it
  looks — or evidence both sampled the same state. It is not proof of determinism.
- Only `kf16_vf16` is covered here. **The six turbo cells are untested on PR #244**, and the
  cell that hung was a turbo cell.
- Decode rate has no pre-rebase baseline: `TURBO3_241_WAVE64_FIX_CONFIRMED.md` recorded no
  decode t/s (its 4.04 t/s figure is prompt eval), so whether 1.1–1.2 t/s is normal for this
  rig cannot be checked against the earlier successful matrix.

## Provenance

- `.76:~/t3_triage/` — `{ctrl,pr244}_kf16_vf16.log`, `server_*.log`, `resp_*.json`,
  `~/gpu_busy.txt`
- Script `~/t3_singlecell.sh`; local copy `scratchpad/t3_singlecell.sh`
- Failed matrix remains at `/mnt/usb/pr244_verify.log` (truncated) and
  `/mnt/usb/mx_pr244/rep{1,2}/` (server logs intact, no responses)
- Binaries: `/mnt/usb/tqbin_pr244` (10240), `/mnt/usb/tqbin_w64` (9981)
