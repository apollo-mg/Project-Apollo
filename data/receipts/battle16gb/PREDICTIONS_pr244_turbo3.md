# Predictions — PR #244 (fork rebase) turbo3 regression matrix on Polaris

Logged **before** the run, 2026-08-01. Build under test: PR #244 worktree
`/mnt/TG_2TB/tmp_pr244` @ `c86e57d82`, **build 10240**, Vulkan, `-march=x86-64-v2`,
`GGML_BMI2=OFF`, `.note.gnu.property` stripped for the G3258. Staged at
`.76:/mnt/usb/tqbin_pr244`.

Hardware `.76`: RX 580 8 GB (Polaris10/GCN4, **subgroup size 64**), RADV (Mesa 26.1.6,
freshly reinstalled after reboot), CachyOS live USB, Pentium G3258.
Model Crow-9B IQ4_XS, prompt "Write a 500-word essay about Linux", temp 0, 500 max tokens.

Reference: `TURBO3_241_WAVE64_FIX_CONFIRMED.md` (build 9981 @ `11a8377bd`).
**K=3**, because `F16_CONTROL_BISTABLE.md` established K=1 is not a valid instrument on this
box — the f16 control produced two distinct states with cell order held fixed.

**Cell order is load-bearing** and copied verbatim from `turbo3_merge_verify.sh`. These
outputs are execution-order dependent, not time dependent. Do not reorder to group cells.

## What this run is actually testing

PR #244 rebases the turboquant fork onto a much newer upstream (**9981 → 10240**, 259 build
numbers). The wave64 ballot fix is *textually* present — I diffed `copy_to_quant.comp` and the
three fixed lines (`ballot_word` / `byte_in_word` / `ballot[ballot_word]`) are intact. This
matrix asks whether it is still *functionally* present after everything around it moved.

**Scoring is on the gzip band, not SHA equality.** Byte-identity to the 9981 references is not
expected and is not the criterion — 259 upstream builds of sampling/graph changes make
divergence the default. The corruption signature is what matters: healthy 0.48–0.53 vs the
wave64-corrupt band of 0.175–0.347 measured on this exact rig.

| id | claim | conf |
|---|---|---|
| P-R1 | all three turbo3-V cells reach gzip ≥ 0.45 in **all 3 reps** | **0.85** |
| P-R2 | no cell in any rep lands in the corrupt band (< 0.40) | **0.80** |
| P-R3 | outputs are **not** byte-identical to the 9981 references | **0.85** |
| P-R4 | the f16/f16 control is bistable across reps (≥ 2 distinct SHAs) | **0.55** |
| P-R5 | turbo2/turbo4 cells are self-consistent across reps (same SHA all 3) | **0.45** |

## Reasoning

**P-R1 = 0.85.** The shader hunk is verbatim. Held below 0.9 because a rebase can break a fix
without touching its lines — the two compile errors I had to fix in `ggml-vulkan.cpp` were
both in exactly this region, and one of them had *deleted the body* of the `SET_ROWS` type
check. That is direct evidence the rebase mangled surrounding code rather than merely moving
it.

**P-R2 = 0.80, deliberately lower than P-R1.** P-R1 covers only the three turbo3-V cells.
P-R2 covers all seven across all reps, including the K-side `kturbo3_vf16` cell that recovered
0.4299 → 0.5199 under the fix, and is the likeliest place for a partial regression to show.

**P-R3 = 0.85.** Divergence is the expectation. Scored explicitly so that "the SHAs don't
match" is not later mistaken for a regression signal — that would be the same class of error
as reading `0/0 tests passed → OK` as a pass.

**P-R4 = 0.55.** Bistability is established for the f16 control on this box, but at K=3 the
chance all three reps land in the same state is real. A *stable* control does not falsify
bistability; it would just mean three draws of the same state.

**P-R5 = 0.45.** turbo2/turbo4 have no `signs` plane and no ballot, so they were byte-identical
across the fix. But that was cell-to-cell within one build, not rep-to-rep — and if the f16
control is bistable, the mechanism (whatever it is) may well touch these too. Genuinely
uncertain, hence below even odds.

## What would falsify "the rebase preserved the fix"

Any turbo3-V cell landing in 0.175–0.347 in any rep. That is the specific corruption
signature, and one occurrence is enough — a bug that fires intermittently is still the bug.
