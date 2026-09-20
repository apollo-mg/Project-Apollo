#pragma once
// sm_60 (GP100 / Tesla P100) compatibility shims for exllamav3.
//
// Force-included into every CUDA translation unit via nvcc -include.
// These two identifiers are simply NOT DECLARED below their introducing arch, so defining
// them here is legal for an sm_60-only build and is a no-op for any arch that has them.
//
//  __dp4a      : introduced sm_61 (GP102/GP104 -- GTX 1080, P40).  GP100 does NOT have it.
//  __nanosleep : introduced sm_70 (Volta).

#if defined(__CUDACC__)

// ---- __dp4a: 4-way byte dot product with accumulate -------------------------------------
// Software implementation, correct for ALL operands (not just the 0x01010101 byte-sum case
// exllamav3 happens to use). nvcc folds this to a handful of ops when b is a constant.
#if defined(__CUDA_ARCH__) && (__CUDA_ARCH__ < 610)

__device__ __forceinline__ unsigned int __dp4a(unsigned int a, unsigned int b, unsigned int c)
{
    unsigned int r = c;
    #pragma unroll
    for (int i = 0; i < 4; ++i)
        r += ((a >> (8 * i)) & 0xFFu) * ((b >> (8 * i)) & 0xFFu);
    return r;
}

__device__ __forceinline__ int __dp4a(int a, int b, int c)
{
    int r = c;
    #pragma unroll
    for (int i = 0; i < 4; ++i)
        r += (int)(signed char)((a >> (8 * i)) & 0xFF) * (int)(signed char)((b >> (8 * i)) & 0xFF);
    return r;
}

#endif  // __dp4a

// ---- __nanosleep: backoff hint in spin-wait loops ---------------------------------------
// Pure scheduling hint with no semantic content. Every call site is a spin loop whose exit
// condition is an atomic/volatile load, which supplies the ordering; dropping the backoff
// leaves those loops correct but hotter. Body deliberately EMPTY -- a fence here would be a
// silent behavioural change to upstream's collectives rather than a no-op.
#if defined(__CUDA_ARCH__) && (__CUDA_ARCH__ < 700)

__device__ __forceinline__ void __nanosleep(unsigned int) { }

#endif  // __nanosleep

#endif  // __CUDACC__
