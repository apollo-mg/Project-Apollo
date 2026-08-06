// Frontier-hazard panel (roadmap P1.2 / Codex §3.2-3.3).
//
// TEACHER-FORCED: a reference context (F16/F16 KV) and a quant context decode
// the SAME real token sequence (a wikitext prefix). At every SCORED position t we
// compare the two next-token distributions WITHOUT letting them diverge
// autoregressively, so per-step error never compounds into a one-shot flip.
//
// DEEP-CONTEXT MODE: with a 248k-token vocab the per-position logits buffer is
// ~1 MB/pos, so requesting logits at every position OOMs past a few k. Instead we
// score a sampled subset of positions (--n-score, linearly spaced across the
// prefix) and BUCKET the metrics by depth band -> a hazard-vs-depth curve. KV is
// cheap here (64 KB/tok, ~16 full-attn layers) so depth is bounded by logits, not KV.
//
// Per scored position t (f16 logits P, quant logits Q over the full vocab):
//   a         = argmax P                          (f16 top-1)
//   F_t       = [argmax Q != a]                   (top-1 flip)
//   margin    = p[a] - p[2nd]                     (f16 decision margin, prob)
//   KL        = sum_v p_v (log p_v - log q_v)     (full-vocab KL(P||Q))
//   R_t       = KL / (0.5*margin^2 + eps)         (decision-danger: KL per unit margin)
//   L_t       = (gap_P - gap_Q) / (gap_P + eps)   (logit-margin erosion; >=1 => f16 margin erased)
//
// Per-prompt aggregates over scored positions; per-depth-band aggregates across prompts.
// Reference is always f16/f16; -ctk/-ctv selects the quant KV under test.

#include "llama.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <string>
#include <vector>

static void print_usage(char ** argv) {
    fprintf(stderr,
        "\nusage: %s -m model.gguf [-f prompts.txt] [-ctk type] [-ctv type]\n"
        "         [-ngl n] [--n-prefix K] [--max-prompts N] [--n-score S] [--n-ubatch U]\n"
        "  reference KV is always f16/f16; -ctk/-ctv select the quant KV under test.\n"
        "  --n-score S: score S sampled positions per prompt (default 256; <=0 = all).\n"
        "  --n-ubatch U: physical ubatch for prefill (default 512; bounds compute buffer).\n\n",
        argv[0]);
}

static ggml_type type_from_str(const std::string & s) {
    for (int i = 0; i < GGML_TYPE_COUNT; i++) {
        const ggml_type t = (ggml_type) i;
        const char * n = ggml_type_name(t);
        if (n && s == n) return t;
    }
    fprintf(stderr, "error: unsupported KV cache type '%s'\n", s.c_str());
    exit(1);
}

// log-spaced depth band edges (position value); band i = [EDGES[i], EDGES[i+1])
static const int BAND_EDGES[] = {0, 128, 512, 2048, 8192, 1 << 30};
static const int N_BANDS = (int)(sizeof(BAND_EDGES) / sizeof(BAND_EDGES[0])) - 1;
static int band_of(int pos) {
    for (int b = 0; b < N_BANDS; b++) if (pos >= BAND_EDGES[b] && pos < BAND_EDGES[b + 1]) return b;
    return N_BANDS - 1;
}

int main(int argc, char ** argv) {
    std::string model_path, prompts_path;
    std::string ctk = "turbo3_tcq", ctv = "turbo3_tcq";
    int ngl = 99, n_prefix = 128, max_prompts = 0, n_score = 256, n_ubatch = 512;

    for (int i = 1; i < argc; i++) {
        std::string a = argv[i];
        auto next = [&](const char * nm) -> std::string {
            if (i + 1 >= argc) { fprintf(stderr, "error: %s needs a value\n", nm); exit(1); }
            return argv[++i];
        };
        if      (a == "-m")            model_path   = next("-m");
        else if (a == "-f")            prompts_path = next("-f");
        else if (a == "-ctk")          ctk          = next("-ctk");
        else if (a == "-ctv")          ctv          = next("-ctv");
        else if (a == "-ngl")          ngl          = std::stoi(next("-ngl"));
        else if (a == "--n-prefix")    n_prefix     = std::stoi(next("--n-prefix"));
        else if (a == "--max-prompts") max_prompts  = std::stoi(next("--max-prompts"));
        else if (a == "--n-score")     n_score      = std::stoi(next("--n-score"));
        else if (a == "--n-ubatch")    n_ubatch     = std::stoi(next("--n-ubatch"));
        else { print_usage(argv); return 1; }
    }
    if (model_path.empty()) { print_usage(argv); return 1; }
    if (n_prefix < 2) n_prefix = 2;
    if (n_ubatch < 1) n_ubatch = 1;

    std::vector<std::string> prompts;
    if (!prompts_path.empty()) {
        std::ifstream f(prompts_path);
        if (!f) { fprintf(stderr, "error: cannot open prompts file\n"); return 1; }
        std::string line;
        while (std::getline(f, line)) {
            if (!line.empty()) prompts.push_back(line);
            if (max_prompts > 0 && (int) prompts.size() >= max_prompts) break;
        }
    } else {
        prompts.push_back("The history of the Roman Empire is a long and complex story that begins");
    }
    if (prompts.empty()) { fprintf(stderr, "error: no prompts\n"); return 1; }

    ggml_backend_load_all();

    llama_model_params mp = llama_model_default_params();
    mp.n_gpu_layers = ngl;
    llama_model * model = llama_model_load_from_file(model_path.c_str(), mp);
    if (!model) { fprintf(stderr, "error: unable to load model\n"); return 1; }

    const llama_vocab * vocab = llama_model_get_vocab(model);
    const int32_t n_vocab = llama_vocab_n_tokens(vocab);

    auto make_ctx = [&](ggml_type tk, ggml_type tv) -> llama_context * {
        llama_context_params cp = llama_context_default_params();
        cp.n_ctx   = n_prefix + 8;
        cp.n_batch = n_prefix;
        cp.n_ubatch = n_ubatch < n_prefix ? n_ubatch : n_prefix;
        cp.type_k  = tk;
        cp.type_v  = tv;
        cp.flash_attn_type = LLAMA_FLASH_ATTN_TYPE_ENABLED;
        cp.no_perf = true;
        return llama_init_from_model(model, cp);
    };
    llama_context * ctx_ref = make_ctx(GGML_TYPE_F16, GGML_TYPE_F16);
    llama_context * ctx_q   = make_ctx(type_from_str(ctk), type_from_str(ctv));
    if (!ctx_ref || !ctx_q) { fprintf(stderr, "error: failed to create contexts\n"); return 1; }
    llama_memory_t mem_ref = llama_get_memory(ctx_ref);
    llama_memory_t mem_q   = llama_get_memory(ctx_q);

    printf("# frontier-hazard  ref=f16/f16  quant=%s/%s  n_prefix=%d  n_score=%d  prompts=%zu  (teacher-forced)\n",
           ctk.c_str(), ctv.c_str(), n_prefix, n_score, prompts.size());
    printf("# HAZ <idx> <npos> <nscored> <flip_rate> <mean_R> <cvar95_R> <mean_L> <frac_Lge1> <mean_KL>\n");

    // running cross-prompt accumulators (overall)
    double s_flip = 0, s_R = 0, s_cvarR = 0, s_L = 0, s_fLge1 = 0, s_KL = 0;
    int n_done = 0;

    // per-depth-band accumulators (across all scored positions of all prompts)
    double b_flip[N_BANDS] = {0}, b_R[N_BANDS] = {0}, b_KL[N_BANDS] = {0}, b_Lge1[N_BANDS] = {0};
    long   b_cnt[N_BANDS]  = {0};

    std::vector<float> refbuf;             // ref logits for scored positions [nscored*n_vocab]
    std::vector<int>   spos;               // scored positions

    for (size_t pi = 0; pi < prompts.size(); pi++) {
        const std::string & s = prompts[pi];
        int n = -llama_tokenize(vocab, s.c_str(), s.size(), NULL, 0, true, true);
        std::vector<llama_token> toks(n);
        if (llama_tokenize(vocab, s.c_str(), s.size(), toks.data(), toks.size(), true, true) < 0) continue;
        if ((int) toks.size() > n_prefix) toks.resize(n_prefix);
        if (toks.size() < 2) continue;
        const int npos = (int) toks.size();

        // choose scored positions (1..npos-1), linearly spaced
        spos.clear();
        if (n_score <= 0 || npos - 1 <= n_score) {
            for (int t = 1; t < npos; t++) spos.push_back(t);
        } else {
            int prev = -1;
            for (int k = 0; k < n_score; k++) {
                int t = 1 + (int)((long long) k * (npos - 2) / (n_score - 1));
                if (t != prev) { spos.push_back(t); prev = t; }
            }
        }
        const int nscored = (int) spos.size();
        std::vector<char> is_scored(npos, 0);
        for (int t : spos) is_scored[t] = 1;

        // teacher-forced: feed the SAME real tokens to both, request logits at scored positions
        auto run = [&](llama_context * ctx, llama_memory_t mem) -> bool {
            llama_memory_clear(mem, true);
            llama_batch b = llama_batch_init(npos, 0, 1);
            for (int t = 0; t < npos; t++) {
                b.token[t] = toks[t];
                b.pos[t] = t;
                b.n_seq_id[t] = 1;
                b.seq_id[t][0] = 0;
                b.logits[t] = is_scored[t];
            }
            b.n_tokens = npos;
            bool ok = llama_decode(ctx, b) == 0;
            llama_batch_free(b);
            return ok;
        };

        if (!run(ctx_ref, mem_ref)) { fprintf(stderr, "error: ref decode failed (prompt %zu)\n", pi); continue; }
        refbuf.resize((size_t) nscored * n_vocab);
        for (int sidx = 0; sidx < nscored; sidx++) {
            const float * lt = llama_get_logits_ith(ctx_ref, spos[sidx]);
            std::memcpy(&refbuf[(size_t) sidx * n_vocab], lt, sizeof(float) * n_vocab);
        }
        if (!run(ctx_q, mem_q)) { fprintf(stderr, "error: quant decode failed (prompt %zu)\n", pi); continue; }

        // per-position panel over scored positions
        std::vector<float> Rvals;
        Rvals.reserve(nscored);
        double sumflip = 0, sumR = 0, sumL = 0, sumLge1 = 0, sumKL = 0;
        for (int sidx = 0; sidx < nscored; sidx++) {
            const int t = spos[sidx];
            const float * Pl = &refbuf[(size_t) sidx * n_vocab];
            const float * Ql = llama_get_logits_ith(ctx_q, t);

            // f16 top-1 (a) and runner-up (b) by logit
            int a = 0, bb = -1;
            float la = Pl[0], lb = -INFINITY;
            for (int v = 1; v < n_vocab; v++) {
                if (Pl[v] > la) { lb = la; bb = a; la = Pl[v]; a = v; }
                else if (Pl[v] > lb) { lb = Pl[v]; bb = v; }
            }
            // quant argmax
            int aq = 0; float laq = Ql[0];
            for (int v = 1; v < n_vocab; v++) if (Ql[v] > laq) { laq = Ql[v]; aq = v; }
            const double flip = (aq != a) ? 1.0 : 0.0;

            // softmax P and Q (double accum), KL(P||Q), and p-margin
            double mP = la, mQ = laq;
            double zP = 0, zQ = 0;
            for (int v = 0; v < n_vocab; v++) { zP += std::exp((double) Pl[v] - mP); zQ += std::exp((double) Ql[v] - mQ); }
            const double logzP = std::log(zP) + mP, logzQ = std::log(zQ) + mQ;
            double kl = 0;
            for (int v = 0; v < n_vocab; v++) {
                const double lp = (double) Pl[v] - logzP;        // log p_v
                if (lp < -30.0) continue;                        // negligible mass
                const double pv = std::exp(lp);
                const double lq = (double) Ql[v] - logzQ;        // log q_v
                kl += pv * (lp - lq);
            }
            if (kl < 0) kl = 0;
            const double pa = std::exp((double) la - logzP);
            const double pb = (bb >= 0) ? std::exp((double) lb - logzP) : 0.0;
            const double margin = pa - pb;
            const double R = kl / (0.5 * margin * margin + 1e-6);

            // logit-margin erosion on the f16 top-2 tokens
            const double gapP = la - (bb >= 0 ? lb : la);
            const double gapQ = (double) Ql[a] - (bb >= 0 ? (double) Ql[bb] : (double) Ql[a]);
            const double L = (gapP - gapQ) / (gapP + 1e-6);

            sumflip += flip; sumR += R; sumL += L; sumKL += kl;
            if (L >= 1.0) sumLge1 += 1.0;
            Rvals.push_back((float) R);

            const int band = band_of(t);
            b_flip[band] += flip; b_R[band] += R; b_KL[band] += kl;
            if (L >= 1.0) b_Lge1[band] += 1.0;
            b_cnt[band] += 1;
        }

        std::sort(Rvals.begin(), Rvals.end());
        int kc = std::max(1, (int) (Rvals.size() * 0.05 + 0.5));
        double cvar = 0;
        for (int j = 0; j < kc; j++) cvar += Rvals[Rvals.size() - 1 - j];   // mean of worst 5%
        cvar /= kc;

        const double flip_rate = sumflip / nscored, mean_R = sumR / nscored,
                     mean_L = sumL / nscored, frac_Lge1 = sumLge1 / nscored, mean_KL = sumKL / nscored;
        printf("HAZ %zu %d %d %.4f %.4f %.4f %.4f %.4f %.5f\n",
               pi, npos, nscored, flip_rate, mean_R, cvar, mean_L, frac_Lge1, mean_KL);
        fflush(stdout);

        s_flip += flip_rate; s_R += mean_R; s_cvarR += cvar; s_L += mean_L;
        s_fLge1 += frac_Lge1; s_KL += mean_KL; n_done++;
    }

    if (n_done > 0) {
        printf("\n# DEPTH bands (pos-bucketed across all scored positions)\n");
        printf("# DEPTH <lo> <hi> <count> <flip_rate> <mean_R> <frac_Lge1> <mean_KL>\n");
        for (int b = 0; b < N_BANDS; b++) {
            if (b_cnt[b] == 0) continue;
            const double c = (double) b_cnt[b];
            printf("DEPTH %d %d %ld %.4f %.4f %.4f %.5f\n",
                   BAND_EDGES[b], BAND_EDGES[b + 1] == (1 << 30) ? n_prefix : BAND_EDGES[b + 1],
                   b_cnt[b], b_flip[b] / c, b_R[b] / c, b_Lge1[b] / c, b_KL[b] / c);
        }
        printf("\n# SUMMARY quant=%s/%s prompts=%d n_prefix=%d (means over prompts)\n", ctk.c_str(), ctv.c_str(), n_done, n_prefix);
        printf("SUMMARY flip_rate=%.4f mean_R=%.4f cvar95_R=%.4f mean_L=%.4f frac_Lge1=%.4f mean_KL=%.5f\n",
               s_flip / n_done, s_R / n_done, s_cvarR / n_done, s_L / n_done, s_fLge1 / n_done, s_KL / n_done);
    }

    llama_free(ctx_q);
    llama_free(ctx_ref);
    llama_model_free(model);
    return 0;
}
