// SPDX-License-Identifier: Apache-2.0
//
// One trivial kernel, compiled to a fatbin and loaded by modulegetfn_probe via the
// driver API. Deliberately minimal: the probe is about symbol lookup, not about
// anything this kernel computes.
//
// Build:
//   $SCALE/targets/gfx1201/bin/nvcc -fatbin -o probe_kernel.fatbin probe_kernel.cu

extern "C" __global__ void probe_real_kernel(float * out) {
    if (out) *out = 1.0f;
}
