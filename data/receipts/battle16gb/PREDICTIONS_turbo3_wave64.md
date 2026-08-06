# Predictions — turboquant #241 wave64 ballot fix

Logged 2026-07-31 **before** the run. RX 580 (Polaris10/GCN4, **subgroup size 64**), RADV.
Branch `fix/vulkan-turbo3-flat-dequant-241` @ `11a8377bd` (force-pushed; Tom's falsified
read-side commit `bc6c77e79` dropped). Parent `9d1d46e36`.
Diff reviewed before building: **1 file, 1 hunk, +11/−3**, `copy_to_quant.comp` only.

## The mechanism

```glsl
-        uint local_byte = sg_lane / 8u;
-        data_q[db].signs[t / 8u] = uint8_t((ballot.x >> (local_byte * 8u)) & 0xFFu);
+        uint ballot_word   = sg_lane / 32u;
+        uint byte_in_word  = (sg_lane % 32u) / 8u;
+        data_q[db].signs[t / 8u] = uint8_t((ballot[ballot_word] >> (byte_in_word * 8u)) & 0xFFu);
```

`subgroupBallot` returns a `uvec4`, one bit per lane, 32 lanes per component. On wave32
every bit is in `.x`. On **wave64** lanes 32–63 land in `.y`, and the old code computed
`local_byte` up to 7 → `ballot.x >> 32..56`, a shift ≥ the 32-bit width, which is UB. Half
of every `signs` byte was written from the wrong lanes.

**Our own receipt had the tell and I did not read it as one:** `TURBO3_241_FIX_VERIFICATION.md`
records the RADV device line `warp size: 64`. I filed it under "bench-rig facts worth keeping"
instead of treating it as a variable.

Why it explains the whole matrix at once: turbo2/turbo4 have no `signs` plane and no ballot
(clean); the read path was always correct (`FLASH_ATTN_EXT` passes); no wave32 GPU can
reproduce it; and a read-side patch was necessarily a no-op.

## Predictions

| id | claim | conf |
|---|---|---|
| **P-W1** | All three turbo3-V cells land in the healthy band (gzip ≥ 0.45) | **0.88** |
| **P-W2** | turbo3 cells are **NOT** byte-identical to the unpatched run | **0.95** |
| **P-W3** | `kf16_vf16` **is** byte-identical to unpatched (`ad9dd4fa776f`) | **0.80** |
| **P-W4** | Both turbo4-V cells byte-identical to unpatched | **0.85** |
| **P-W5** | `kturbo3_vf16` improves on 0.4299 toward the ~0.50 control | 0.65 |
| **P-W6** | `FLASH_ATTN_EXT` turbo3 still passes | **0.95** |
| **P-W7** | `SET_ROWS_TURBO3` still reports "not supported", 0/0, prints OK | **0.90** |

**P-W2 is the load-bearing one and it is the cheap falsifier.** Last time 6/6 were
byte-identical, which is what proved the read-side patch inert. If the turbo3 cells are
*again* byte-identical, the new patch is also not executing on this path and the mechanism
story is wrong regardless of how good it looks on paper.

**P-W3/P-W4 are the specificity test.** A fix to the `signs` write must not touch codecs
that have no `signs` plane. If f16 or turbo4 output *also* moves, something broader changed
and the attribution is not clean. Valid only because cell execution order is held fixed —
`TURBO3_241_FIX_VERIFICATION.md` established these outputs are order-dependent, not
time-dependent.

**P-W1 at 0.88, not higher:** the mechanism is identified and explains every observation,
but "corruption removed" and "output lands in the healthy band" are different claims. Half
the sign bits being wrong may not be the *only* defect on this path.

P-W5 lower because Tom himself expects only "a small but real lift," and 0.4299 vs the
~0.50 control is a narrow gap to resolve on one draw of one prompt.

## Non-interference note

The control plane is concurrently driving `v5_det03` (HermesBench, 61 tasks, wall-clock
timeouts). Build is **incremental** — one shader plus a relink — run at `nice -n 19` with
`-j4` of 16 threads. Recorded because this campaign has twice manufactured false results
from throughput shifts, and a full rebuild here could have done it a third time.
