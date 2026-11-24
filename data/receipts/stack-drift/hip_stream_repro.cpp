#include <hip/hip_runtime.h>
#include <cstdio>
int main() {
  int n = 0; hipError_t e = hipGetDeviceCount(&n); printf("devices %d (%s)\n", n, hipGetErrorString(e)); fflush(stdout);
  e = hipSetDevice(0); printf("setdevice %s\n", hipGetErrorString(e)); fflush(stdout);
  void *p = nullptr; e = hipMalloc(&p, 1 << 20); printf("malloc %s\n", hipGetErrorString(e)); fflush(stdout);
  hipStream_t s; e = hipStreamCreateWithFlags(&s, hipStreamNonBlocking); printf("stream non-blocking %s\n", hipGetErrorString(e)); fflush(stdout);
  hipStream_t s2; e = hipStreamCreate(&s2); printf("stream default %s\n", hipGetErrorString(e)); fflush(stdout);
  e = hipStreamSynchronize(s); printf("sync %s\n", hipGetErrorString(e)); return 0;
}
