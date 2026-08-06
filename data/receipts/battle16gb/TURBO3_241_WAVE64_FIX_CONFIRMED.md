# turboquant#241 SOLVED — wave64 subgroup ballot packing, confirmed on Polaris

RX 580 8 GB (Polaris10/GCN4, **subgroup size 64**), Vulkan/RADV, CachyOS live USB.
Date 2026-07-31. Fix `11a8377bd` on parent `9d1d46e36`; build 9981.
Predictions: `PREDICTIONS_turbo3_wave64.md` (logged pre-run). Prior:
`TURBO3_ISSUE241_POLARIS_REPRO.md`, `TURBO3_241_FIX_VERIFICATION.md`.

Root cause found by **TheTom**, from the reframe our null result produced.

## The bug

```glsl
-        uint local_byte = sg_lane / 8u;
-        data_q[db].signs[t / 8u] = uint8_t((ballot.x >> (local_byte * 8u)) & 0xFFu);
+        uint ballot_word   = sg_lane / 32u;
+        uint byte_in_word  = (sg_lane % 32u) / 8u;
+        data_q[db].signs[t / 8u] = uint8_t((ballot[ballot_word] >> (byte_in_word * 8u)) & 0xFFu);
```

`subgroupBallot` returns a `uvec4` carrying one bit per lane, **32 lanes per component**. On
wave32 every bit is in `.x` and the old code is correct. On **wave64** lanes 32–63 report in
`.y`, while `local_byte` reaches 4–7 — so `ballot.x >> 32..56` is a shift at or beyond the
32-bit width, which is undefined. **Half of every `signs` byte was written from the wrong
lanes' bits, at write time.**

One commit, one file, one hunk, +11/−3, in `copy_to_quant.comp` — the KV **write** shader.

## Result: 7-cell matrix, wave64 fix vs unpatched

Cell order held identical to the prior run (these outputs are execution-order dependent).

| cell | unpatched gzip / sha | **fix 11a8377bd** | |
|---|---|---|---|
| kturbo4_vturbo3 | 0.2736 / 173da68272cc | **0.4866** / b031d9c337e8 | **CHANGED → healthy** |
| kf16_vf16 | 0.5097 / ad9dd4fa776f | 0.5097 / ad9dd4fa776f | identical (control) |
| kturbo4_vturbo4 | 0.5024 / 9e33a09474a1 | 0.5024 / 9e33a09474a1 | identical |
| kturbo4_vturbo2 | 0.5021 / 0b3b5c4235d5 | 0.5021 / 0b3b5c4235d5 | identical |
| kturbo3_vturbo3 | 0.3474 / 65e01d083c83 | **0.5152** / 4cb388a93d6d | **CHANGED → healthy** |
| kf16_vturbo3 | 0.1753 / b539962f600d | **0.5251** / 169b27a7251c | **CHANGED → healthy** |
| kturbo3_vf16 | 0.4299 / 4dfeae533123 | **0.5199** / e89131fbe39d | **CHANGED → healthy** |

**Every cell containing turbo3 changed; every cell without turbo3 is byte-identical.** That
is the specificity result, and it is what makes the attribution clean: turbo2/turbo4 have no
`signs` plane and no ballot, so a correct fix to `signs` packing must leave them untouched.
It did, to the byte.

All four previously-corrupt cells now land in the 0.4866–0.5251 band against a 0.5097
control, and all seven cells now open with the same coherent reasoning shape
(`1. **Analyze the Request:** ... Topic: Linux`). Before the fix, turbo3-V cells opened with
unrelated text — a different essay premise each time.

**`kturbo3_vf16` (K-side) went 0.4299 → 0.5199.** Tom expected "a small but real lift"; it
recovered the full remaining gap to the control. Consistent with the mechanism: K corruption
perturbs pre-softmax scores (degraded but coherent), V corruption feeds garbage directly into
the output sum (incoherent).

## Prediction scoring

| id | claim | conf | outcome |
|---|---|---|---|
| P-W1 | three turbo3-V cells reach gzip ≥ 0.45 | 0.88 | **CONFIRMED** (0.4866 / 0.5152 / 0.5251) |
| P-W2 | turbo3 cells NOT byte-identical to unpatched | 0.95 | **CONFIRMED** (4/4 changed) |
| P-W3 | `kf16_vf16` byte-identical | 0.80 | **CONFIRMED** (`ad9dd4fa776f`) |
| P-W4 | both turbo4-V cells byte-identical | 0.85 | **CONFIRMED** |
| P-W5 | `kturbo3_vf16` improves on 0.4299 | 0.65 | **CONFIRMED** (0.5199) |
| P-W6 | `FLASH_ATTN_EXT` turbo3 still passes | 0.95 | **CONFIRMED** (6/6 OK) |
| P-W7 | `SET_ROWS_TURBO3` still skipped, 0/0, prints OK | 0.90 | **CONFIRMED** |

7 of 7 — the first clean sweep of the campaign, and only because the mechanism was
*identified* before the run rather than guessed at. The prior two rounds scored badly for the
opposite reason: they tested hypotheses about where the bug might be.

**Method error worth recording:** the first P-W7 attempt used `-o SET_ROWS`, which filters on
op *name* and selected zero turbo3 cases (365 lines, 0 matches). `SET_ROWS_TURBO3` is an
`op_desc`. Re-run with the correct filter to get the result above. A wrong filter here reads
as a pass.

## The test-coverage trap persists, and is independent of this bug

On the **fixed** build:

```
SET_ROWS_TURBO3(type_idx=i32,ne0=128,ne1=16,r=1): not supported [Vulkan0]
...
  Backend Vulkan0: OK
2/2 backends passed
OK
```

Every case still skipped, zero tests executed, green summary. `supports_op` lists `TURBO3_0`
for `SET_ROWS` and all shapes clear the `%128` gate, so the rejection is elsewhere in the test
graph — most likely the `ggml_cpy(written → F32)` readback. **The write path that carried this
bug is still not covered by a test on this backend**, which is plausibly how it shipped. Tom
is filing it separately.

## What our null result contributed

`TURBO3_241_FIX_VERIFICATION.md` was 6/6 byte-identical — a pure negative on the read-side
theory. It was still the step that solved this: falsifying the read path forced the write-path
reframe, and the receipt's own device line carried the tell —
`warp size: 64` — which had been filed as bench-rig trivia rather than treated as a variable.

**Generalisable:** any `subgroupBallot` result indexed as if it were 32 bits wide is a
latent wave64 bug. It is invisible on NVIDIA (warp 32), invisible on RDNA in wave32 mode, and
fires on GCN. Worth grepping for beyond this shader.

## Scope

- One GPU (Polaris10/GCN4), one driver (RADV), one model (Crow-9B IQ4_XS), one prompt.
- The fix is validated on **wave64**. It should be a no-op on wave32 (`ballot_word` is always
  0, `byte_in_word` == the old `local_byte`) — inspected, not measured. No wave32 arm was run.
- gzip ratio is a degeneracy proxy, not a fidelity metric. "Healthy band" means "not
  degenerate"; it does not establish turbo3 KV is lossless.

## Provenance

- `turbo3_w64_artifacts/` — `w64_verify.log`, `mx_w64/` (7 responses + server logs),
  `tbo_w64_fa.log`, `tbo_w64_srt3.log`, `tbo_w64_sr.log` (the mis-filtered run), script
- Build: worktree `/mnt/TG_2TB/tmp_turbo3_fix` @ `11a8377bd`, `build_vk_v2`, Vulkan,
  `-march=x86-64-v2`, `.note.gnu.property` stripped for the G3258.
  `libggml-vulkan.so.0.15.1` md5 `c6adf991…` (old) → `5f09a85b…` (fixed)
- Bench rig binaries: `/mnt/usb/tqbin_w64` on `.76`
