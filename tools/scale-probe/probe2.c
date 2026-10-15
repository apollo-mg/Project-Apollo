#include <stdio.h>
#include <cuda.h>
int main(void) {
  CUdevice d; CUcontext c; CUmodule m; CUdeviceptr p; size_t sz = 12345; unsigned int v = 0;
  cuInit(0); cuDeviceGet(&d, 0); cuCtxCreate(&c, 0, d);
  CUresult r = cuModuleLoad(&m, "k2.o"); printf("cuModuleLoad: %d\n", r);
  const char* names[] = {"dev_u32", "const_u32", "used_u32"};
  for (int i = 0; i < 3; i++) { sz = 12345; p = 0; r = cuModuleGetGlobal(&p, &sz, m, names[i]);
    v = 0; CUresult r2 = (r == CUDA_SUCCESS && p) ? cuMemcpyDtoH(&v, p, 4) : -1;
    printf("%-22s GetGlobal=%d size=%zu ptr=%s value=%u (copy=%d)\n", names[i], r, sz, p ? "set" : "null", v, r2); }
  return 0; }
