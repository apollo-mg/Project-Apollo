// SPDX-License-Identifier: Apache-2.0
//
// meminfo_probe -- does cudaMemGetInfo tell the truth under SCALE on AMD?
//
// Repro for the defect Avarok/atlas #1119 reports against SCALE 1.7.1 on gfx1201:
// cudaMemGetInfo appears to charge far more than the requested bytes per allocation,
// driving reported-free to zero while the GPU still has many GB genuinely free, with
// no recovery after the allocations are released.
//
// This probe is deliberately standalone: it needs SCALE and a GPU, nothing else --
// no inference stack, no model weights. It compares three views of VRAM at every step:
//
//   1. cudaMemGetInfo free        -- what the runtime claims
//   2. amdgpu sysfs vram_used     -- kernel driver ground truth
//   3. cumulative bytes requested -- what we actually asked for
//
// Written in C style on purpose: SCALE 1.7.3 force-includes its own builtins header,
// which collides with the C23 math declarations in glibc >= 2.41 (rsqrt, cospi, ...).
// The workaround is -U_GNU_SOURCE, which in turn breaks libstdc++ headers that need
// _GNU_SOURCE for wide-char support (<cwchar>, pulled in by <vector> and <string>).
// Using only C headers sidesteps both. See data/receipts/scale-gfx1201/RESULT_SCALE_MEMINFO.md.
//
// Build (SCALE):
//   $SCALE/targets/gfx1201/bin/nvcc -U_GNU_SOURCE -o meminfo_probe meminfo_probe.cu
//
// Run:
//   LD_LIBRARY_PATH=$SCALE/lib ./meminfo_probe [chunk_mib] [max_allocs] [csv_path]
// Defaults: 11 MiB chunks, 2000 allocations max, ./meminfo_probe.csv
//
// Exit codes: 0 = ran to completion (either outcome), 1 = setup/runtime failure.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <cuda_runtime.h>

#define GIB 1073741824.0

// ---------------------------------------------------------------- sysfs truth

// Find the amdgpu card node backing the GPU. We take the first card exposing
// mem_info_vram_used; a multi-GPU box would need the PCI id matched instead.
static int find_sysfs_vram_used(char * out, size_t outsz) {
    for (int i = 0; i < 8; ++i) {
        char p[256];
        snprintf(p, sizeof p, "/sys/class/drm/card%d/device/mem_info_vram_used", i);
        FILE * f = fopen(p, "r");
        if (f) { fclose(f); snprintf(out, outsz, "%s", p); return 1; }
    }
    out[0] = '\0';
    return 0;
}

static long long read_ll(const char * path) {
    if (!path || !path[0]) return -1;
    FILE * f = fopen(path, "r");
    if (!f) return -1;
    long long v = -1;
    if (fscanf(f, "%lld", &v) != 1) v = -1;
    fclose(f);
    return v;
}

// ---------------------------------------------------------------------- main

int main(int argc, char ** argv) {
    const size_t chunk_mib  = (argc > 1) ? strtoull(argv[1], NULL, 10) : 11;
    const int    max_allocs = (argc > 2) ? atoi(argv[2])               : 2000;
    const char * csv_path   = (argc > 3) ? argv[3] : "meminfo_probe.csv";

    const size_t chunk = chunk_mib * 1024ull * 1024ull;

    char sysfs[256];
    if (!find_sysfs_vram_used(sysfs, sizeof sysfs)) {
        fprintf(stderr, "WARN: no amdgpu mem_info_vram_used found; sysfs column will be -1\n");
    } else {
        printf("sysfs ground truth: %s\n", sysfs);
    }

    cudaDeviceProp prop;
    if (cudaGetDeviceProperties(&prop, 0) != cudaSuccess) {
        fprintf(stderr, "FATAL: cudaGetDeviceProperties failed\n");
        return 1;
    }

    // Force context creation before the first measurement, so that context
    // overhead is charged to the baseline rather than to allocation #1.
    void * warm = NULL;
    if (cudaMalloc(&warm, 1024) != cudaSuccess) {
        fprintf(stderr, "FATAL: could not create context (cudaMalloc of 1 KiB failed)\n");
        return 1;
    }
    cudaFree(warm);

    size_t rt_free0 = 0, rt_total0 = 0;
    if (cudaMemGetInfo(&rt_free0, &rt_total0) != cudaSuccess) {
        fprintf(stderr, "FATAL: cudaMemGetInfo failed\n");
        return 1;
    }
    const long long sys_used0 = read_ll(sysfs);

    printf("device       : %s\n", prop.name);
    printf("chunk        : %zu MiB   max allocs: %d\n", chunk_mib, max_allocs);
    printf("\n--- baseline (context created, nothing else allocated) ---\n");
    printf("  cudaMemGetInfo total : %.3f GiB\n", rt_total0 / GIB);
    printf("  cudaMemGetInfo free  : %.3f GiB\n", rt_free0  / GIB);
    printf("  runtime implies used : %.3f GiB\n", (rt_total0 - rt_free0) / GIB);
    if (sys_used0 >= 0)
        printf("  sysfs actually used  : %.3f GiB   <-- ground truth\n", sys_used0 / GIB);
    printf("\n");

    FILE * csv = fopen(csv_path, "w");
    if (!csv) { fprintf(stderr, "FATAL: cannot write %s\n", csv_path); return 1; }
    fprintf(csv, "alloc_n,requested_bytes,rt_free_bytes,rt_used_delta_bytes,"
                 "sysfs_used_bytes,sysfs_used_delta_bytes,charge_ratio\n");

    void ** ptrs = (void **)calloc((size_t)max_allocs, sizeof(void *));
    if (!ptrs) { fprintf(stderr, "FATAL: host alloc failed\n"); fclose(csv); return 1; }
    int n_alloc = 0;

    int    phantom_at         = -1;  // first iteration where the free counter stopped tracking
    double phantom_sysfs_free = 0.0;
    int    hard_fail_at       = -1;  // first iteration where cudaMalloc actually failed

    // Phantom-exhaustion detector: N consecutive allocations with an unchanged free
    // counter, while cudaMalloc keeps succeeding.
    const int STUCK_N   = 8;
    size_t    prev_free = (size_t)-1;
    int       stuck_run = 0;

    for (int n = 1; n <= max_allocs; ++n) {
        void * p = NULL;
        cudaError_t rc = cudaMalloc(&p, chunk);
        if (rc != cudaSuccess) {
            hard_fail_at = n;
            printf("cudaMalloc FAILED at alloc #%d (%s)\n", n, cudaGetErrorString(rc));
            break;
        }
        ptrs[n_alloc++] = p;

        size_t f = 0, t = 0;
        cudaMemGetInfo(&f, &t);
        const long long sys_used = read_ll(sysfs);

        const long long requested  = (long long)chunk * n;
        const long long rt_used_d  = (long long)rt_free0 - (long long)f;
        const long long sys_used_d = (sys_used >= 0 && sys_used0 >= 0) ? (sys_used - sys_used0) : -1;
        const double    charge     = requested > 0 ? (double)rt_used_d / (double)requested : 0.0;

        fprintf(csv, "%d,%lld,%zu,%lld,%lld,%lld,%.4f\n",
                n, requested, f, rt_used_d, sys_used, sys_used_d, charge);

        // Phantom exhaustion: the runtime's free counter stops tracking reality while
        // allocations keep succeeding. Detect it as "free stopped moving", NOT as
        // "free < chunk" -- on gfx1201 the counter saturates at a small nonzero floor
        // (~56 MiB observed) and never reaches zero, so a < chunk test never fires.
        // That was a real defect in the first version of this probe: it printed
        // "phantom exhaustion: NO" on a run that had been pinned for 337 allocations.
        if (f == prev_free) {
            if (++stuck_run == STUCK_N && phantom_at < 0) phantom_at = n - STUCK_N + 1;
        } else {
            stuck_run = 0;
        }
        prev_free = f;

        if (phantom_at == n - STUCK_N + 1 && stuck_run == STUCK_N) {
            phantom_at = n;
            phantom_sysfs_free = (sys_used >= 0)
                               ? ((double)((long long)rt_total0 - sys_used) / GIB) : 0.0;
            printf("PHANTOM EXHAUSTION at alloc #%d: runtime free %.3f GiB, "
                   "sysfs says %.3f GiB genuinely free\n",
                   n, f / GIB, phantom_sysfs_free);
        }

        if (n % 100 == 0 || n <= 5) {
            printf("  #%-5d requested %7.3f GiB | rt free %7.3f GiB | rt charged %7.3f GiB "
                   "| sysfs used %7.3f GiB | charge %.2fx\n",
                   n, requested / GIB, f / GIB, rt_used_d / GIB,
                   sys_used_d >= 0 ? sys_used_d / GIB : -1.0, charge);
        }
        fflush(csv);
    }

    printf("\n--- releasing %d allocations ---\n", n_alloc);
    for (int i = 0; i < n_alloc; ++i) cudaFree(ptrs[i]);
    free(ptrs);
    cudaDeviceSynchronize();

    size_t rt_free1 = 0, rt_total1 = 0;
    cudaMemGetInfo(&rt_free1, &rt_total1);
    const long long sys_used1 = read_ll(sysfs);

    printf("  cudaMemGetInfo free  : %.3f GiB  (baseline was %.3f GiB)\n",
           rt_free1 / GIB, rt_free0 / GIB);
    if (sys_used1 >= 0)
        printf("  sysfs actually used  : %.3f GiB  (baseline was %.3f GiB)\n",
               sys_used1 / GIB, sys_used0 / GIB);

    const double recovered_frac = rt_free0 ? (double)rt_free1 / (double)rt_free0 : 0.0;

    printf("\n================ VERDICT ================\n");
    printf("allocations completed   : %d of %d attempted\n", n_alloc, max_allocs);
    printf("total actually requested: %.3f GiB\n", (double)((long long)chunk * n_alloc) / GIB);
    if (phantom_at > 0) {
        printf("phantom exhaustion      : YES at alloc #%d (%.3f GiB requested),\n"
               "                          with %.3f GiB genuinely free per sysfs\n",
               phantom_at, (double)((long long)chunk * phantom_at) / GIB, phantom_sysfs_free);
    } else {
        printf("phantom exhaustion      : NO -- runtime free tracked real usage\n");
    }
    if (hard_fail_at > 0)
        printf("hard cudaMalloc failure : alloc #%d\n", hard_fail_at);
    printf("recovery after free     : %.1f%% of baseline free restored %s\n",
           100.0 * recovered_frac,
           recovered_frac > 0.98 ? "(RECOVERED)" : "(NO RECOVERY)");
    printf("csv                     : %s\n", csv_path);
    printf("=========================================\n");

    fclose(csv);
    return 0;
}
