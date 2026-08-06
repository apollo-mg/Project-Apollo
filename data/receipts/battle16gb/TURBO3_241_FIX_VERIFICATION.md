# turboquant#241: the flat-byte-view fix changes nothing, and the write path is untested

RX 580 8 GB (Polaris10/GCN4), Vulkan/RADV, CachyOS live USB. Date 2026-07-31.
Branch under test: `fix/vulkan-turbo3-flat-dequant-241` @ `bc6c77e79` (build 9981),
parent `9d1d46e36`. Prior: `TURBO3_ISSUE241_POLARIS_REPRO.md`.

## Headline: the patch is a no-op on output

Seven-cell matrix, patched build vs the unpatched 9971 build, same box, same model
(Crow-9B IQ4_XS), same probe, `cache_prompt:false`:

| cell | unpatched 9971 | **fix 9981** | identical? |
|---|---|---|---|
| kturbo4_vturbo3 | 173da68272cc | 173da68272cc | **YES** |
| kf16_vf16 | ad9dd4fa776f | ad9dd4fa776f | **YES** |
| kturbo4_vturbo4 | 9e33a09474a1 | 9e33a09474a1 | **YES** |
| kturbo4_vturbo2 | 0b3b5c4235d5 | 0b3b5c4235d5 | **YES** |
| kturbo3_vturbo3 | 65e01d083c83 | 65e01d083c83 | **YES** |
| kf16_vturbo3 | b539962f600d | b539962f600d | **YES** |

**6/6 byte-identical.** `libggml-vulkan.so.0` md5 differs between the builds, so this is not a
stale binary — the shader really changed and the output really didn't.

**That falsifies the struct-layout hypothesis for the FA read path.** Byte-identical output means
the explicit offsets computed exactly what the struct view was already computing. My theory,
Tom's patch, both wrong. turbo3-V remains corrupt at 0.2736 / 0.3474 / 0.1753 gzip.

## `test-backend-ops` — the read path passes, the write path never runs

**`FLASH_ATTN_EXT`** with `type_K=turbo3, type_V=turbo3, hsk=128, hsv=128`: **passes on both
arms**, all six shape variants, `prec=f32` and `prec=def`. The isolated FA op is numerically
correct on Polaris. Consistent with the patch being a no-op.

**`SET_ROWS_TURBO3`** (and `SET_ROWS_TURBO4`) — the dedicated KV-cache **write** tests:

```
SET_ROWS_TURBO3(type_idx=i32,ne0=128,ne1=4096,r=1024): not supported [Vulkan0]
SET_ROWS_TURBO3(type_idx=i32,ne0=256,ne1=2048,r=512):  not supported [Vulkan0]
SET_ROWS_TURBO3(type_idx=i32,ne0=512,ne1=1024,r=256):  not supported [Vulkan0]
  0/0 tests passed
  Backend Vulkan0: OK
2/2 backends passed
OK
```

**Every case skipped, zero tests executed, and the harness reports OK.** A green
`test-backend-ops` run on Polaris says nothing whatsoever about turbo3's write path. That is
plausibly how this shipped: the read-path test genuinely passes, the write-path test is silently
skipped, and the summary line is green either way.

**The skip reason is not the obvious one.** `ggml_backend_vk_device_supports_op` lists
`GGML_TYPE_TURBO3_0` as supported for `SET_ROWS`, and the only turbo-specific gate is
`src[0]->ne[0] % 128 != 0` — which all three shapes (128/256/512) satisfy. So the rejection comes
from elsewhere in the test graph, most likely the `ggml_cpy(written → F32)` readback the test
uses to compare against CPU. If so, **the write path is unverifiable through this test on any
backend lacking that CPY**, not just Polaris. Worth Tom's eyes.

## Where the bug most likely lives

`copy_to_quant.comp` — the shader that writes the KV cache — still uses struct-member access for
exactly the field in question:

```glsl
261:  data_q[b].signs[j]        = uint8_t(0);
271:  data_q[b].signs[j / 8]   |= uint8_t(hi1 << (j % 8));
457:  data_q[db].signs[t / 8u]  = uint8_t((ballot.x >> (local_byte * 8u)) & 0xFFu);
```

If the driver mislays `signs`, corruption is baked in **at write time** and no read-side fix can
recover it. This explains every observation at once: FA reads correctly (test passes), the
read-side patch changes nothing (addresses were already right), the model still corrupts (the
stored bytes are wrong), and the write path has never been exercised on this hardware.

Note also `dequant_turbo3_0.comp` (non-FA dequant) still reads through the struct view — Tom
flagged this himself.

## Corrections to our own prior reporting

**1. The "deterministic reproduction / same bytes" claim was over-stated, and the drift I
reported was misdiagnosed.** I told Tom the f16/f16 control had drifted 19 h later on the same
boot. It had not drifted with *time* — today's fix-arm f16/f16 is `ad9dd4fa`, matching both of
yesterday's runs. The odd value (`22d6baa6`) came from the K-side script, whose only difference
was **which cell ran immediately before it**. So output depends on execution order / prior server
state, not elapsed time. Reproduction is exact when cell order is held fixed.

**2. The `base` matrix arm never ran — my error.** I built the parent commit with
`--target test-backend-ops`, so no `llama-server` existed in that tree, and all seven cells
reported `SERVER FAILED` in 8 s each. It does not change the conclusion (the fix arm is
byte-identical to yesterday's unpatched run, which is the same comparison), but the intended
same-session control was not obtained.

**3. `TURBO3_ISSUE241_POLARIS_REPRO.md` over-claimed the RDNA4 negative.** I wrote that the clean
RDNA4 Vulkan arm ruled out "the Vulkan turbo3 path is broken." Tom's note corrects this: GCN4 has
no cooperative-matrix support and is the only common config taking the **scalar** `flash_attn.comp`
path, while RDNA4 takes cm1. Both include the same dequant header, so RDNA4 may simply have got a
favourable driver layout rather than being immune.

## Bench-rig facts worth keeping

RADV reports Polaris as: `uma: 0 | fp16: 0 | bf16: 0 | warp size: 64 | shared memory: 65536 |
int dot: 0 | matrix cores: none`. No fp16 at all — a harsher fallback position than assumed.

## Provenance

- `/mnt/usb/turbo3_fix_verify.sh`; local copy `scratchpad/turbo3_fix_verify.sh`
- `/mnt/usb/mx_fix/` (7 cells), `/mnt/usb/tbo_base.log`, `/mnt/usb/tbo_fix.log`
- `/mnt/usb/turbo3_kside/` — K-side isolation (turbo3-K/f16-V: gzip 0.4299, content correct)
- Builds: worktrees `/mnt/TG_2TB/tmp_turbo3_fix` (bc6c77e79), `/mnt/TG_2TB/tmp_turbo3_base`
  (9d1d46e36); Vulkan, `-march=x86-64-v2`, `.note.gnu.property` stripped for the G3258
