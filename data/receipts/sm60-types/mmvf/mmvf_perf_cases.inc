    // PREREG_MMVF_SHORTROW.md perf cases.
    // Phase A tuning grid: F16, m=10240, n in {1, 4}.
    for (int64_t n : {1, 4}) {
        for (int64_t k : {64, 128, 256, 320, 384, 512, 768, 1024, 1536, 2048}) {
            test_cases.emplace_back(new test_mul_mat(GGML_TYPE_F16, GGML_TYPE_F32, 10240, n, k, {1, 1}, {1, 1}));
        }
    }
    // Phase B held-out shapes (never used for selection).
    test_cases.emplace_back(new test_mul_mat(GGML_TYPE_BF16, GGML_TYPE_F32, 10240, 1, 320, {1, 1}, {1, 1})); // hc_up
    test_cases.emplace_back(new test_mul_mat(GGML_TYPE_F32,  GGML_TYPE_F32, 10240, 1, 320, {1, 1}, {1, 1})); // hc_up
    test_cases.emplace_back(new test_mul_mat(GGML_TYPE_F16,  GGML_TYPE_F32, 32000, 2, 192, {1, 1}, {1, 1}));
    test_cases.emplace_back(new test_mul_mat(GGML_TYPE_F32,  GGML_TYPE_F32, 16384, 1,  96, {1, 1}, {1, 1}));
    test_cases.emplace_back(new test_mul_mat(GGML_TYPE_F16,  GGML_TYPE_F32,  4096, 1, 448, {1, 1}, {1, 1}));
    test_cases.emplace_back(new test_mul_mat(GGML_TYPE_BF16, GGML_TYPE_F32,  8192, 8, 640, {1, 1}, {1, 1}));
    test_cases.emplace_back(new test_mul_mat(GGML_TYPE_BF16, GGML_TYPE_F32,  2048, 1, 256, {1, 1}, {1, 1}));
    // Controls: long rows (untouched by construction) and hc_down (few rows, long k: a different problem).
    test_cases.emplace_back(new test_mul_mat(GGML_TYPE_F16,  GGML_TYPE_F32,  4096, 1, 4096, {1, 1}, {1, 1}));
    test_cases.emplace_back(new test_mul_mat(GGML_TYPE_BF16, GGML_TYPE_F32,   320, 1, 10240, {1, 1}, {1, 1}));
    test_cases.emplace_back(new test_mul_mat(GGML_TYPE_F16,  GGML_TYPE_F32,   320, 1, 10240, {1, 1}, {1, 1}));
