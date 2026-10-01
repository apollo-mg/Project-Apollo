    // PREREG_MMVF_SHORTROW.md correctness cases: short rows that must take the warp-per-row path, with row counts
    // not divisible by any R (7, 1001, 10241), every batch width the vector kernel serves, a strided k view,
    // channel/sample broadcast, MUL_MAT_ID and gate/bias fusion.
    for (ggml_type t : {GGML_TYPE_F16, GGML_TYPE_BF16, GGML_TYPE_F32}) {
        for (int64_t m : {7, 10241}) {
            for (int64_t n : {1, 2, 3, 4, 5, 8}) {
                for (int64_t k : {64, 320, 512, 1024}) {
                    test_cases.emplace_back(new test_mul_mat(t, GGML_TYPE_F32, m, n, k, {1, 1}, {1, 1}));
                }
            }
        }
        for (int64_t n : {1, 3}) {
            test_cases.emplace_back(new test_mul_mat(t, GGML_TYPE_F32, 1001, n, 320, {1, 1}, {1, 1}, {0, 1, 2, 3}, 384));
            test_cases.emplace_back(new test_mul_mat(t, GGML_TYPE_F32, 1001, n, 320, {2, 3}, {2, 2}));
        }
        for (bool b : {false, true}) {
            for (int64_t n : {1, 4}) {
                test_cases.emplace_back(new test_mul_mat_id(t, GGML_TYPE_F32, 16, 4, b, 1001, n, 320));
            }
        }
        for (bool use_id : {false, true}) {
            for (bool with_bias : {false, true}) {
                for (int64_t mtok : {1, 4}) {
                    test_cases.emplace_back(new test_mul_mat_vec_fusion(t, GGML_GLU_OP_SWIGLU, mtok, 1001, 320,
                        use_id, 16, 4, false, with_bias, true, false, {1, 1}));
                }
            }
        }
    }
