# Merge-head confirmation — INCONCLUSIVE (rig degraded mid-run), plus a correction owed

RX 580 / Polaris10 / RADV, `.76`. Date 2026-07-31.
Build under test: **merge head `8a891f4b5`** (build 9999), which contains the validated fix
`11a8377bd` (`git merge-base --is-ancestor` → yes). Reference = the `11a8377bd` results from
`TURBO3_241_WAVE64_FIX_CONFIRMED.md`.

**This run does not confirm or refute anything about the merge. Reported because a partial
result presented as a pass would be worse than none.**

## What happened

| cell | ref (`11a8377bd`) | merge `8a891f4b5` | |
|---|---|---|---|
| kturbo4_vturbo3 | 0.4866 / b031d9c337e8 | 0.4866 / b031d9c337e8 | identical |
| **kf16_vf16** | 0.5097 / **ad9dd4fa776f** | 0.5024 / **22d6baa6872c** | **CHANGED** |
| kturbo4_vturbo4 | 0.5024 / 9e33a09474a1 | 0.5024 / 9e33a09474a1 | identical |
| kturbo4_vturbo2 | 0.5021 / 0b3b5c4235d5 | 0.5021 / 0b3b5c4235d5 | identical |
| kturbo3_vturbo3 | 0.5152 / 4cb388a93d6d | **PARSE FAIL** (task cancelled) | — |
| kf16_vturbo3 | 0.5251 / 169b27a7251c | **SERVER FAILED** | — |
| kturbo3_vf16 | 0.5199 / e89131fbe39d | **SERVER FAILED** | — |

**Free VRAM at each cell's start:**

```
kturbo4_vturbo3   7868 MiB      kturbo3_vturbo3   7868 MiB
kf16_vf16         7868 MiB      kf16_vturbo3      3588 MiB   <-- 4.3 GB never released
kturbo4_vturbo4   7868 MiB      kturbo3_vf16      3587 MiB
kturbo4_vturbo2   7868 MiB
```

Cell 5 (`kturbo3_vturbo3`) decoded normally at 4.04 t/s to 458 tokens, then hung: a 13-minute
gap in its log ending in `srv stop: cancel task, id_task = 0` at the 900 s curl timeout. Its
process never released VRAM, so cells 6 and 7 started with 3.6 GB and failed during
`-fit` device-memory fitting.

**Three failures, one root cause: a single hung cell.** Not three independent results.

The GPU is now wedged — subsequent `llama-server --list-devices` probes hang unkillable in the
`amdgpu_vm_fini` D-state pattern this project already documented (see the `vulkaninfo` hang in
the earlier Polaris work). `.76` needs a reboot before it can be used again.

## The finding that survives, and it is a correction I owe Tom

**`kf16_vf16` — pure f16, no turbo codec, no `signs` plane, no ballot — changed.**

The new value `22d6baa6872c` / 1893 chars is **not new**. It is the exact anomalous value
recorded in `TURBO3_241_FIX_VERIFICATION.md`: `ad9dd4fa` twice, then `22d6baa6`. The f16/f16
control has exactly two known states and has now produced each of them twice.

That matters because of what I told Tom to explain the first occurrence:

> *"the f16/f16 control doesn't drift over time, it depends on **which cell ran before it**.
> Fix the cell order and reproduction is exact."*

**That is now falsified.** In both the `11a8377bd` run and this one, `kf16_vf16` ran second,
immediately after `kturbo4_vturbo3`, from an identical 7868 MiB starting state — and produced
different output. Cell order was held fixed and reproduction was *not* exact.

So the f16 control is bistable for a reason we have not identified. Candidates not yet
separated: the build difference itself (`ggml.c` and shared headers moved between
`11a8377bd` and `8a891f4b5`, and `libggml-vulkan.so` md5 changed from `5f09a85b…` to
`895f324a…` despite zero Vulkan source changes), or genuine run-to-run nondeterminism on this
hardware independent of build.

**The second is not exotic** — this session established at length that temperature-0
nondeterminism survives six configurations on the P100 fleet. Assuming Polaris is immune was
an assumption, never a measurement.

**Consequences for the confirmed result:** none. `TURBO3_241_WAVE64_FIX_CONFIRMED.md` rests on
turbo3 cells moving while turbo2/turbo4 cells stayed byte-identical, and all three turbo4 cells
reproduced byte-identically here too. But the *strength* of that specificity argument is now
weaker than stated: it assumed a byte-stable baseline, and the f16 baseline is bistable. The
attribution still holds — 4/4 turbo3 cells changed, 3/3 turbo4 cells didn't — it is just no
longer "byte-identical baseline" in the strict sense I claimed to Tom.

## What a valid merge-head confirmation would need

1. Reboot `.76` (GPU wedged).
2. Per-cell VRAM-free assertion before launch; abort the run rather than continue degraded.
3. A hang guard: bound decode wall time well under the 900 s curl timeout so one stuck cell
   cannot strand the rest.
4. **K≥3 on `kf16_vf16` alone, same build**, to establish whether the f16 control is bistable
   within a single build. Until that is known, no single-draw byte comparison on this rig can
   be read as a build difference.

Item 4 should come first, and it is cheap — it is the same "measure the instrument's jitter
before measuring the effect" lesson that the V5/V6 leg produced today
(`hermesbench-v5v6/V5_V6_INDISTINGUISHABLE.md`).

## Status for the issue thread

Tom explicitly framed this run as *"belt-and-suspenders, not a blocker,"* and #241 is already
closed as merged. **Nothing here reopens it.** The Vulkan diff between the validated commit and
the merge head is empty; the entire 7,440-line delta is the DSV4 port. The fix in the merged
tree is byte-for-byte the commit that was validated.

What is worth sending him is the correction on the f16 control, since I gave him a confident
mechanism ("execution-order dependent") that has now failed its own test.

## Provenance

- `/mnt/usb/merge_verify.log`, `/mnt/usb/mx_merge/` on `.76` — **not yet pulled**, GPU wedged;
  pull after reboot
- `/mnt/usb/tqbin_merge` (build 9999, `8a891f4b5`), `/mnt/usb/turbo3_merge_verify.sh`
- Reference: `turbo3_w64_artifacts/` (already durable, pulled before this run)
