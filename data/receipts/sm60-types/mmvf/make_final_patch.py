#!/usr/bin/env python3
"""PREREG_MMVF_SHORTROW.md phase B: turn the tuning patch into the final rule. Usage: make_final_patch.py R KMAX
Run in a buun tree that has mmvf_tune.patch applied; edits mmvf.cu in place (then `git diff` is the final patch)."""
import re, sys
R, KMAX = int(sys.argv[1]), int(sys.argv[2])
p = "ggml/src/ggml-cuda/mmvf.cu"
s = open(p).read()
tune = re.search(r"    // TUNING ONLY.*?\n    GGML_ASSERT\(rows_per_block == 1 \|\| block_size_best == warp_size\);\n", s, re.S)
assert tune, "tuning block not found"
final = f"""    // Short rows: one block per row leaves most of its threads with a single multiply-add and pays a cross-warp
    // shared-memory reduction for every row. Give each row one warp instead (block_size == warp_size has no barrier)
    // and put several rows in a block, as MMVQ's small_k path does. Measured on sm_60 only, so other GPUs keep the
    // existing launch.
    constexpr int64_t short_row_max_ncols      = {KMAX};
    constexpr int     short_row_rows_per_block = {R};
    int rows_per_block = 1;
    if (GGML_CUDA_CC_IS_NVIDIA(ggml_cuda_info().devices[device].cc) && warp_size == 32 && ncols <= short_row_max_ncols) {{
        block_size_best = warp_size;
        rows_per_block  = short_row_rows_per_block;
    }}
"""
s = s[:tune.start()] + final + s[tune.end():]
assert "getenv" not in s[tune.start():tune.start() + len(final)]
open(p, "w").write(s)
print(f"final rule written: R={R} KMAX={KMAX}")
