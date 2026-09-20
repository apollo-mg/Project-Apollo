p = "/home/mark/exl3quant/lib/python3.13/site-packages/exllamav3/exllamav3_ext/quant/exl3_gemv_int8_kernel.cuh"
s = open(p).read()
old = '    int d;\n    asm ("dp4a.u32.s32 %0, %1, %2, %3;" : "=r"(d) : "r"(a), "r"(b), "r"(c));\n    return d;'
new = ('#if defined(__CUDA_ARCH__) && (__CUDA_ARCH__ >= 610)\n'
       '    int d;\n'
       '    asm ("dp4a.u32.s32 %0, %1, %2, %3;" : "=r"(d) : "r"(a), "r"(b), "r"(c));\n'
       '    return d;\n'
       '#else\n'
       '    // sm_60 (GP100) has no dp4a. Software equivalent: a bytes unsigned, b bytes signed,\n'
       '    // signed accumulate -- matches dp4a.u32.s32 exactly.\n'
       '    int d = c;\n'
       '    #pragma unroll\n'
       '    for (int i = 0; i < 4; ++i)\n'
       '        d += (int)((a >> (8 * i)) & 0xFFu) * (int)(signed char)((b >> (8 * i)) & 0xFF);\n'
       '    return d;\n'
       '#endif')
assert s.count(old) == 1, s.count(old)
open(p, "w").write(s.replace(old, new))
print("dp4a_us fallback installed")
