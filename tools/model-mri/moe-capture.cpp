// moe-capture: dump per-layer MoE router probabilities (ffn_moe_probs) for every token
// of a prompt, for offline routing analysis (the "Model MRI" toolset).
//
// Based on examples/eval-callback. Registers a cb_eval hook, filters to the ffn_moe_probs
// tensors (the full softmax over experts, pre-top-k), and streams the raw F32 data to a
// binary file. All top-k / utilization / locality / entropy analysis is done offline in
// Python from this dump, so this stays a dumb, model-agnostic firehose.
//
// Binary format (little-endian), repeated per (layer, decode) record:
//   int32 layer            (parsed from tensor name "...ffn_moe_probs-<il>"; -1 if absent)
//   int32 n_expert         (ne[0])
//   int32 n_tokens         (ne[1])
//   float32 data[n_expert * n_tokens]   (column-major: token j at data[j*n_expert ..])
//
// Output path via env MOE_CAP_OUT (default ./moe_trace.bin). Run with warmup disabled so the
// router uses n_expert_used, not all experts.
#include "arg.h"
#include "common.h"
#include "log.h"
#include "llama.h"

#include <clocale>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

struct moe_cap {
    FILE *               out = nullptr;
    std::vector<uint8_t> buf;      // scratch for GPU->host pulls
    long long            records = 0;
    long long            tokens_seen = 0;
    int                  names_shown = 0;
};

static bool is_probs(const char * name) {
    // the plain router softmax, not the biased/masked variants (DeepSeek sigmoid-group path)
    return strstr(name, "ffn_moe_probs") != nullptr &&
           strstr(name, "biased")   == nullptr &&
           strstr(name, "masked")   == nullptr &&
           strstr(name, "reshaped") == nullptr;   // skip the [1,n_expert,n_tokens] view of the same data
}

static int layer_from_name(const char * name) {
    const char * dash = strrchr(name, '-');   // cb names as "<name>-<il>"
    return (dash && dash[1]) ? atoi(dash + 1) : -1;
}

static bool moe_cb(struct ggml_tensor * t, bool ask, void * user_data) {
    auto * cap = (moe_cap *) user_data;
    if (ask) {
        return is_probs(t->name);
    }
    if (!is_probs(t->name) || t->type != GGML_TYPE_F32) {
        return true;
    }

    if (cap->names_shown < 3) {   // reveal the real tensor name/shape once, for validation
        LOG_INF("moe-capture: matched %s  ne=[%lld,%lld,%lld]\n", t->name,
                (long long) t->ne[0], (long long) t->ne[1], (long long) t->ne[2]);
        cap->names_shown++;
    }

    const int64_t n_expert = t->ne[0];
    const int64_t n_tokens = t->ne[1];
    const size_t  nbytes   = ggml_nbytes(t);

    const float * data;
    if (ggml_backend_buffer_is_host(t->buffer)) {
        data = (const float *) t->data;
    } else {
        cap->buf.resize(nbytes);
        ggml_backend_tensor_get(t, cap->buf.data(), 0, nbytes);
        data = (const float *) cap->buf.data();
    }

    const int32_t hdr[3] = { layer_from_name(t->name), (int32_t) n_expert, (int32_t) n_tokens };
    fwrite(hdr,  sizeof(int32_t), 3, cap->out);
    fwrite(data, sizeof(float), (size_t) (n_expert * n_tokens), cap->out);
    cap->records++;
    cap->tokens_seen += n_tokens;   // counts once per layer; divide by n_layers for token count
    return true;
}

static bool run(llama_context * ctx, const common_params & params) {
    const llama_model * model  = llama_get_model(ctx);
    const llama_vocab * vocab  = llama_model_get_vocab(model);
    const bool          add_bos = llama_vocab_get_add_bos(vocab);

    std::vector<llama_token> tokens = common_tokenize(ctx, params.prompt, add_bos, true);
    if (tokens.empty()) {
        LOG_ERR("%s: no input tokens (provide -p or -f)\n", __func__);
        return false;
    }
    LOG_INF("moe-capture: %zu prompt tokens\n", tokens.size());
    if (llama_decode(ctx, llama_batch_get_one(tokens.data(), tokens.size()))) {
        LOG_ERR("%s: decode failed\n", __func__);
        return false;
    }
    return true;
}

int main(int argc, char ** argv) {
    std::setlocale(LC_NUMERIC, "C");

    common_params params;
    common_init();
    if (!common_params_parse(argc, argv, params, LLAMA_EXAMPLE_COMMON)) {
        return 1;
    }

    moe_cap cap;
    const char * out_path = getenv("MOE_CAP_OUT");
    if (!out_path) out_path = "moe_trace.bin";
    cap.out = fopen(out_path, "wb");
    if (!cap.out) {
        LOG_ERR("moe-capture: cannot open output %s\n", out_path);
        return 1;
    }

    llama_backend_init();
    llama_numa_init(params.numa);

    params.cb_eval           = moe_cb;
    params.cb_eval_user_data = &cap;
    params.warmup            = false;   // else the router activates all experts, not top-k

    auto   llama_init = common_init_from_params(params);
    auto * model = llama_init->model();
    auto * ctx   = llama_init->context();
    if (model == nullptr || ctx == nullptr) {
        LOG_ERR("moe-capture: failed to init model/context\n");
        return 1;
    }

    const bool ok = run(ctx, params);
    fclose(cap.out);
    LOG_INF("moe-capture: wrote %lld records to %s\n", cap.records, out_path);
    return ok ? 0 : 1;
}
