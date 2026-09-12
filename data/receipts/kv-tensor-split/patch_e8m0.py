#!/usr/bin/env python3
"""Guard the Float8E8M0 specialisation behind a CUDA 12.8 toolkit check.

__nv_fp8_e8m0 / __nv_fp8x2_e8m0 / __nv_fp8x4_e8m0 were introduced in CUDA 12.8 (MXFP8 /
microscaling). On CUDA 12.4 they do not exist, so humming-vendor's base_conversion.cuh fails to
parse and ggml-cuda cannot be built FOR ANY ARCHITECTURE -- this is a toolkit floor, not a Pascal
problem. Neither humming-fp8.cu nor humming-fp8-block.cu references E8M0; the specialisation is
pulled in purely by the include, so omitting it on older toolkits is safe.

This is the patch buun would need upstream. Applied locally only so the actual Pascal
qualification (the thing he asked for) is not blocked by an unrelated toolkit requirement.
"""
import re, sys, pathlib

p = pathlib.Path(sys.argv[1])
src = p.read_text()

OPEN = "#if defined(CUDART_VERSION) && CUDART_VERSION >= 12080  // __nv_fp8*_e8m0 need CUDA >= 12.8\n"
CLOSE = "#endif  // CUDART_VERSION >= 12080\n"

if "CUDART_VERSION >= 12080" in src:
    print("already guarded; nothing to do")
    sys.exit(0)

# The specialisation is one contiguous block: "template <>\nclass F8Conversion<Float8E8M0> {" .. "};"
m = re.search(r"template\s*<>\s*\nclass F8Conversion<Float8E8M0>\s*\{", src)
if not m:
    sys.exit("FATAL: could not locate the F8Conversion<Float8E8M0> specialisation")

start = m.start()
# walk braces from the class body to find its closing "};"
i = src.index("{", m.start())
depth = 0
while i < len(src):
    if src[i] == "{":
        depth += 1
    elif src[i] == "}":
        depth -= 1
        if depth == 0:
            break
    i += 1
else:
    sys.exit("FATAL: unbalanced braces")
end = src.index(";", i) + 1
while end < len(src) and src[end] == "\n":
    end += 1
    break

block = src[start:end]
if "e8m0" not in block:
    sys.exit("FATAL: located block does not contain e8m0 -- refusing to patch the wrong thing")

p.write_text(src[:start] + OPEN + block + CLOSE + src[end:])
print(f"guarded {len(block)} chars of the Float8E8M0 specialisation")
