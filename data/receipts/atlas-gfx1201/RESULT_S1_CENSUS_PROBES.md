# Result -- Atlas gfx1201 bring-up, S1 (compile census + hardware probes) complete

**2026-09-17.** Milestone S1 of Avarok-Cybersecurity/atlas#1126. Runs inside the S0 container
(Ubuntu 24.04, glibc 2.39, SCALE 1.7.1) against `TheTom/atlas` branch `amd/r9700-target` at
`68b26331`. Artifacts in `/mnt/TG_2TB/experiments/atlas-gfx1201/logs/`.

## Both S1 acceptance criteria met

| criterion | baseline (PRD) | measured | verdict |
|---|---|---|---|
| kernel compile census | 180 of 180 clean | **180 of 180 clean, 0 failed** | MATCH |
| largest static `__shared__` | 65536 bytes | **65536** (65537 rejected) | MATCH |
| `__nv_cvt_float_to_fp8` | compiles | compiles | MATCH |
| inline `cvt.rn.satfinite.e4m3x2.f32` | rejected | rejected | MATCH |
| e4m3 `mma.sync` | rejected | rejected | MATCH |
| bf16 `mma.sync m16n8k16` | compiles | compiles | MATCH |

No divergence from the r9700 baseline on any axis. The 16 GB consumer board behaves identically
to the 32 GB workstation part at the toolchain level, which is the expected result given the ISA
is the same, but it had not been shown.

## Correction (appended after reading kernels/r9700/HARDWARE.toml)

**The census result is weaker than this receipt first stated, and the number 180 was never at
risk.** `kernels/r9700` is documented in its own `HARDWARE.toml` as a **subtractive mirror** of
`kernels/gb10`: whole-directory symlinks *minus* the sources SCALE 1.7.1 cannot compile on
gfx1201. The "180 of 193" figure in PR #1107 is a census over the **gb10** tree, and the 13
failures it found are exactly the names the r9700 tree omits.

So censusing the r9700 tree can only ever return N of N. The tree is *defined* as the set that
compiles. A result of 180/180 is a tautology of the tree's construction, not a discovery.

What it does still establish, which is not nothing: the same 180 sources that compile on a
32 GB R9700 also compile on a 16 GB RX 9070 XT. A board-specific compile failure would have
appeared here and did not. That is a confirmation of portability across boards within gfx1201,
not evidence about the toolchain's coverage. The original framing above oversold it; this
correction stands rather than editing the claim away.

## Blocker worked around, and it needs reporting

**Neither script the PRD invokes exists in the repo.** `kit/kernel-census.sh` and
`kit/probe-lds-fp8.sh` are absent from `amd/r9700-target`, and `git log --all --diff-filter=A --
"kit/*"` shows `kit/` was never added on this branch's history. TheTom presumably has them
locally. Both were reconstructed here:

- `kernel-census.sh` -- **semantics pinned rather than guessed.** The two src-dirs the PRD names
  hold exactly 168 + 12 = **180 `.cu` files**, matching the stated 180 baseline precisely, so
  "the census" is "compile every `.cu` in these trees" and nothing else. Device-only compilation
  (`--cuda-device-only -c`), mirroring the HIP-side census in atlas#1122.
- `probe-lds-fp8.sh` -- one small compile per stated baseline.

Getting the real scripts is still worth doing: a matching number is good evidence the
reconstruction is faithful, but only TheTom's implementation makes the figures strictly
comparable.

## Instrument control

Two probes expect *rejection*, which is only informative if the rejection is about the
instruction rather than about malformed inline asm on my part. The bf16 `mma.sync` probe is the
control: same inline-asm shape, expected to pass. **It passed**, so the e4m3 rejections are real
capability limits rather than a syntax error of mine producing a false negative.

SCALE's diagnostics are specific enough to be worth quoting:

```
cvt.rn.satfinite.e4m3x2.f32:
  error: this implementation does not provide a suitable definition for
         __nv_cvt_floatraw_to_fp8, which is needed to codegen this PTX instruction

e4m3 mma.sync:
  error: this implementation does not know how to codegen the PTX type: e4m3
```

That names the missing piece rather than failing opaquely, which is a notable contrast with the
`cuModuleGetFunction` defect filed as scale-validation#68.

## Two incidental findings

**`kernels/r9700` is entirely symlinks** -- 191 symlinks, **zero** real `.cu` files. The target is
already an aliasing view over shared sources, which is the mechanical reason the PRD's decision to
reuse the `r9700` key for the 9070 XT costs nothing: there is no per-board source tree to fork.

**LDS diagnostics say "local memory" for shared memory.** Exceeding the ceiling reports
`error: local memory (65537) exceeds limit (65536)` for a `__shared__` array. The limit is right
and the rejection is correct; only the noun is wrong. Cosmetic, worth a line in the next Spectral
report rather than a ticket of its own.

## Note on the 64 KB LDS ceiling

Confirmed at 65536 bytes, carried over from gfx1151. Relevant beyond this milestone: atlas#1116
wants the W4A16 prefill GEMM retiled for RDNA 4, and an LDS ceiling below what the hardware
offers constrains exactly that retiling. Now measured on this board rather than assumed.

## Next

S2: kernel compilation (176 kernels for the r9700 target).
