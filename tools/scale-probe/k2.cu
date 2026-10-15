extern "C" __global__ void w4a16_gemm_t(unsigned int* o) { o[0] = 1; }
extern "C" __device__ unsigned int dev_u32 = 128;
extern "C" __constant__ unsigned int const_u32 = 64;
extern "C" __device__ __attribute__((used)) unsigned int used_u32 = 32;
