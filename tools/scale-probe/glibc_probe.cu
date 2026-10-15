// Needs libstdc++ headers that require _GNU_SOURCE, plus device code using the maths names glibc 2.41+ exposes as C23.
#include <vector>
#include <string>
#include <cmath>
#include <cstdio>
__global__ void k(double* o, const double* x) { o[0] = rsqrt(x[0]) + cospi(x[0]); }
int main() { std::vector<double> v(2, 4.0); std::string s = "ok"; double *d; cudaMalloc(&d, 16);
  cudaMemcpy(d, v.data(), 16, cudaMemcpyHostToDevice); k<<<1,1>>>(d, d + 1); cudaMemcpy(v.data(), d, 8, cudaMemcpyDeviceToHost);
  printf("%s rsqrt(4)+cospi(4) = %g (expect 1.5)\n", s.c_str(), v[0]); return 0; }
