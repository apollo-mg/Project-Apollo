p = "/home/mark/exl3quant/lib/python3.13/site-packages/exllamav3/exllamav3_ext/hgemm_f16acc.cu"
s = open(p).read()
G = '#if defined(__CUDA_ARCH__) && (__CUDA_ARCH__ >= 800)\n    {ASM}\n#else\n    __trap();\n#endif\n}}'
subs = [
    ('__device__ __forceinline__ void cp_async_commit() { asm volatile("cp.async.commit_group;\\n" ::); }',
     '__device__ __forceinline__ void cp_async_commit()\n{\n'
     + G.replace('{ASM}', 'asm volatile("cp.async.commit_group;\\n" ::);').replace('}}', '}')),
    ('template <int N> __device__ __forceinline__ void cp_async_wait() { asm volatile("cp.async.wait_group %0;\\n" :: "n"(N)); }',
     'template <int N> __device__ __forceinline__ void cp_async_wait()\n{\n'
     + G.replace('{ASM}', 'asm volatile("cp.async.wait_group %0;\\n" :: "n"(N));').replace('}}', '}')),
]
for old, new in subs:
    assert s.count(old) == 1, (s.count(old), old[:70])
    s = s.replace(old, new)
open(p, "w").write(s)
print("patched 2 one-liner functions")
