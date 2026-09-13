// membw.c -- STREAM-style triad for .194's host-bandwidth baseline (PREREG_FLASHNEXT_RESIDENCY.md).
// Written for this test rather than downloaded, so there is no third-party code to audit.
// Reports the best of `reps` triad passes, counting 3 arrays of traffic per element as STREAM does:
// the write-allocate read of `a` is not counted, so the figure understates true bus traffic by ~25%.
#include <omp.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    size_t n = argc > 1 ? strtoull(argv[1], NULL, 10) : (size_t)1 << 27;
    int reps = argc > 2 ? atoi(argv[2]) : 10;
    double *a = aligned_alloc(64, n * sizeof(double));
    double *b = aligned_alloc(64, n * sizeof(double));
    double *c = aligned_alloc(64, n * sizeof(double));
    if (!a || !b || !c) {
        fprintf(stderr, "allocation failed\n");
        return 1;
    }
    // First touch from the threads that will stream the pages, so first-touch placement is what runs.
    #pragma omp parallel for schedule(static)
    for (size_t i = 0; i < n; i++) {
        a[i] = 0.0;
        b[i] = 1.0;
        c[i] = 2.0;
    }
    double best = 1e30;
    for (int r = 0; r < reps; r++) {
        double t = omp_get_wtime();
        #pragma omp parallel for schedule(static)
        for (size_t i = 0; i < n; i++) a[i] = b[i] + 3.0 * c[i];
        t = omp_get_wtime() - t;
        if (t < best) best = t;
    }
    double check = 0.0;  // read the result back so the loop cannot be optimized away
    for (size_t i = 0; i < n; i += 4096) check += a[i];
    printf("threads=%d n=%zu best_triad_GBps=%.2f check=%.1f\n", omp_get_max_threads(), n,
           3.0 * n * sizeof(double) / best / 1e9, check);
    return 0;
}
