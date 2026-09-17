// SPDX-License-Identifier: Apache-2.0
//
// modulegetfn_probe -- does cuModuleGetFunction report missing symbols under SCALE?
//
// Repro for the second defect Avarok/atlas #1119 reports against SCALE 1.7.1 on gfx1201:
// looking up a kernel symbol that does not exist returns CUDA_SUCCESS with an unusable
// handle, deferring the failure to launch time. NVIDIA's driver returns
// CUDA_ERROR_NOT_FOUND (500) at lookup.
//
// Standalone: needs SCALE, a GPU, and probe_kernel.fatbin. No inference stack.
//
// Written in C style on purpose -- see meminfo_probe.cu for why (-U_GNU_SOURCE is
// required to compile against glibc >= 2.41, which then breaks libstdc++ headers).
//
// Build:
//   $SCALE/targets/gfx1201/bin/nvcc -fatbin -o probe_kernel.fatbin probe_kernel.cu
//   $SCALE/targets/gfx1201/bin/nvcc -U_GNU_SOURCE -o modulegetfn_probe \
//       modulegetfn_probe.cu -lcuda
//
// Run:
//   LD_LIBRARY_PATH=$SCALE/targets/gfx1201/lib ./modulegetfn_probe [fatbin_path]
//
// Exit codes: 0 = ran to completion (either outcome), 1 = setup failure.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <cuda.h>

static const char * errname(CUresult r) {
    const char * s = NULL;
    cuGetErrorName(r, &s);
    return s ? s : "(unknown)";
}

static void show(const char * what, CUresult r) {
    printf("  %-46s -> %d (%s)\n", what, (int)r, errname(r));
}

int main(int argc, char ** argv) {
    const char * fatbin = (argc > 1) ? argv[1] : "probe_kernel.fatbin";

    // The symbol that is present in the module, and one that certainly is not.
    const char * present = "probe_real_kernel";
    const char * absent  = "definitely_not_a_kernel_9f3a1c";

    CUresult r;

    r = cuInit(0);
    if (r != CUDA_SUCCESS) { show("cuInit", r); return 1; }

    CUdevice dev;
    r = cuDeviceGet(&dev, 0);
    if (r != CUDA_SUCCESS) { show("cuDeviceGet", r); return 1; }

    char devname[256] = {0};
    cuDeviceGetName(devname, sizeof devname, dev);

    CUcontext ctx;
    r = cuCtxCreate(&ctx, 0, dev);
    if (r != CUDA_SUCCESS) { show("cuCtxCreate", r); return 1; }

    printf("device : %s\n", devname);
    printf("module : %s\n\n", fatbin);

    CUmodule mod;
    r = cuModuleLoad(&mod, fatbin);
    show("cuModuleLoad", r);
    if (r != CUDA_SUCCESS) {
        fprintf(stderr, "FATAL: could not load module -- build probe_kernel.fatbin first\n");
        cuCtxDestroy(ctx);
        return 1;
    }

    // ---------------------------------------------------------- control: present symbol
    printf("\n--- control: symbol that EXISTS (\"%s\") ---\n", present);
    CUfunction f_present = NULL;
    CUresult r_present = cuModuleGetFunction(&f_present, mod, present);
    show("cuModuleGetFunction [present]", r_present);
    printf("  %-46s -> %p\n", "handle", (void *)f_present);

    int launched_ok = 0;
    if (r_present == CUDA_SUCCESS && f_present) {
        CUdeviceptr out = 0;
        cuMemAlloc(&out, sizeof(float));
        void * args[] = { &out };
        CUresult rl = cuLaunchKernel(f_present, 1,1,1, 1,1,1, 0, 0, args, NULL);
        show("cuLaunchKernel [present]", rl);
        CUresult rs = cuCtxSynchronize();
        show("cuCtxSynchronize [present]", rs);
        launched_ok = (rl == CUDA_SUCCESS && rs == CUDA_SUCCESS);
        if (out) cuMemFree(out);
    }

    // ------------------------------------------------------- defect case: absent symbol
    printf("\n--- defect case: symbol that DOES NOT EXIST (\"%s\") ---\n", absent);
    CUfunction f_absent = NULL;
    CUresult r_absent = cuModuleGetFunction(&f_absent, mod, absent);
    show("cuModuleGetFunction [absent]", r_absent);
    printf("  %-46s -> %p\n", "handle", (void *)f_absent);

    CUresult r_absent_launch = CUDA_SUCCESS;
    int attempted_launch = 0;
    if (r_absent == CUDA_SUCCESS) {
        printf("\n  Lookup SUCCEEDED for a symbol that is not in the module.\n");
        printf("  Attempting one launch on that handle to see where the error surfaces.\n");
        attempted_launch = 1;
        void * args[] = { NULL };
        r_absent_launch = cuLaunchKernel(f_absent, 1,1,1, 1,1,1, 0, 0, args, NULL);
        show("cuLaunchKernel [absent]", r_absent_launch);
        CUresult rs = cuCtxSynchronize();
        show("cuCtxSynchronize [absent]", rs);
    }

    // ------------------------------------------------- exploratory: cuModuleGetGlobal
    printf("\n--- exploratory (not preregistered): cuModuleGetGlobal on an absent global ---\n");
    CUdeviceptr gptr = 0;
    size_t gsize = 0;
    CUresult r_glob = cuModuleGetGlobal(&gptr, &gsize, mod, "definitely_not_a_global_9f3a1c");
    show("cuModuleGetGlobal [absent]", r_glob);
    printf("  %-46s -> %p, size %zu\n", "ptr/size", (void *)(size_t)gptr, gsize);

    // ------------------------------------------------------------------------ verdict
    printf("\n================ VERDICT ================\n");
    printf("NVIDIA reference behaviour: lookup of an absent symbol returns\n");
    printf("  CUDA_ERROR_NOT_FOUND (500) at cuModuleGetFunction time.\n\n");
    printf("control (present symbol) : lookup %s, launch %s\n",
           r_present == CUDA_SUCCESS ? "OK" : "FAILED",
           launched_ok ? "OK" : "FAILED");
    printf("absent symbol lookup     : %d (%s)\n", (int)r_absent, errname(r_absent));
    if (r_absent == CUDA_SUCCESS) {
        printf("                           ^ DEFECT REPRODUCED: success for a missing symbol\n");
        printf("absent handle            : %p (%s)\n", (void *)f_absent,
               f_absent ? "non-NULL" : "NULL");
        if (attempted_launch)
            printf("deferred failure at launch: %d (%s)\n",
                   (int)r_absent_launch, errname(r_absent_launch));
    } else if (r_absent == CUDA_ERROR_NOT_FOUND) {
        printf("                           ^ CORRECT: matches NVIDIA. Defect appears FIXED.\n");
    } else {
        printf("                           ^ neither success nor NOT_FOUND; see above\n");
    }
    printf("=========================================\n");

    cuModuleUnload(mod);
    cuCtxDestroy(ctx);
    return 0;
}
