    // PREREG_HC_Q8.md kernel control: the two hyper-connection shapes in four types
    for (ggml_type t : {GGML_TYPE_F16, GGML_TYPE_F32, GGML_TYPE_BF16, GGML_TYPE_Q8_0}) {
        test_cases.emplace_back(new test_mul_mat(t, GGML_TYPE_F32, 10240, 1, 320, {1, 1}, {1, 1}));
        test_cases.emplace_back(new test_mul_mat(t, GGML_TYPE_F32, 320, 1, 10240, {1, 1}, {1, 1}));
    }
