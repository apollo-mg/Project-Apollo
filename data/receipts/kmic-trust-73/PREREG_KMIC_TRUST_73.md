# Pre-registration -- is Kaden's P100 fork deterministic? Seeded reproducibility of its served config, split by component, plus greedy exactness of its speculative path

**2026-10-08, before any row.** `kmic-p100-73` found that the daily build (D) is seed-reproducible at temperature 1.0
(D1 = D2 byte for byte), while Kaden's fork (K) is not. K1 and K2, two fresh servers with the same seeded requests,
diverged at characters 57, 44, 373 and 5. At temperature 0, K was deterministic and matched D (M1). Mark: "I need to
validate determinism and all that before I'd consider adopting the changes"; tonight, "why don't we see if this
engine of Kaden's is trustworthy."

**Prior art checked:** `ledger_precheck.py "determinism seed reproducible speculative MTP sampled draft greedy bit
exact"` -> receipts found:
- `spec-decode-determinism/RESULT_SPECULATION_IS_NOT_BIT_EXACT.md` (08-18): on our earlier forks, speculation-on greedy
  never reproduces speculation-off greedy.
- INDEX L501: the speculative path, not the drafter, changes the output.
- INDEX L37 / `prompt-cache-breaks-determinism`: a warm prompt cache with MTP is bistable; `cache_prompt: false` avoids
  it.
- `agent-benchmark-determinism`: `-np 1` avoids slot-identity effects under VBR.

**What this adds:** the first test of K. Its OPTLOG claims a lossless sampled drafter ("Same seeds give byte-identical
text run to run") and a bit-identical restore path. This test splits its served config into components, so a
divergence can be pinned to one.

**Source read before registering:** K seeds both speculative RNGs per request from the request's sampler seed
(`server-context.cpp` ~1846: `spec_dist_rng` and `common_speculative_set_seed`). The draft RNG defaults to `0x5eed`
(`speculative.cpp` ~1381). On paper, a fixed request seed should therefore reproduce. Why K1 and K2 diverged is open.

## Arms (one server each; .73, both P100s, 150 W / 1,328 MHz recorded per server)

| arm | build | command | env |
|---|---|---|---|
| **DS** | D | the daily served command (`kmic-p100-73` launch `DS`: VBR, `-np 2`, MTP draft 3) | none |
| **KS** | K | his served command (`kmic-p100-73` `KS`: q4_0 KV, `-np 1`, MTP n-max 4, p-min 0.2) | `GGML_CUDA_GRAPHS_PRE_VOLTA=3 LLAMA_SPEC_SAMPLE_TEMP=1.0 LLAMA_SPEC_DRAFT_TOPK=20` (as K1/K2) |
| **KG** | K | `KS` | `GGML_CUDA_GRAPHS_PRE_VOLTA=3` only: greedy drafts |
| **KN** | K | `KS` minus every `--spec-*`/draft flag: no MTP | `GGML_CUDA_GRAPHS_PRE_VOLTA=3` |
| **KN0** | K | as KN | none: no CUDA graphs |

**Order (KS, KG and KN each get a fresh second server, the "b" leg, to test across restarts):**
DS, KSa, KGa, KNa, KN0, KSb, KGb, KNb.

## Requests per server (`/completion`, raw token ids, `cache_prompt: false`, `ignore_eos`)

After a 16-token warmup:
- **Seeded:** 3 identical requests on the 2k slice `[212992:215040]` of `split-prefill-73/raw/corpus_ids.json`.
  Temperature 1.0, top-k 20, top-p 0.95, min-p 0, **seed 1**, 512 tokens. This is M2's 2k seed-1 request.
- **Greedy:** 1 request on the same slice, temperature 0, top-k 1, 256 tokens.

Recorded per request: text, timings, `draft_n`, `draft_n_accepted`.

**Comparisons:**
- **within a server:** r1 vs r2 vs r3;
- **across restarts:** a vs b, per arm (r1 vs r1);
- **greedy exactness:** each speculative arm's greedy text against KN's and KN0's, and K against D. The first
  differing character is reported.

## Predictions

| # | claim | conf. |
|---|---|---|
| T1 | DS: the 3 seeded reps are byte-identical (the daily is reproducible within a server too) | 0.7 |
| T2 | KN and KN0: seeded reps identical within each server, and KNa = KNb (K's kernels are deterministic) | 0.75 |
| T3 | KG: identical within each server, and KGa = KGb | 0.6 |
| T4 | KS: at least one of its within-server or a-vs-b pairs differs (replicates K1 vs K2) | 0.7 |
| T5 | greedy: KS's text equals KN's byte for byte (his speculative path is exact) | 0.4 |
| T6 | greedy: KN's text equals KN0's (CUDA graphs do not change single-token numerics) | 0.8 |

**How the outcome maps to "trustworthy":**
- If T2/T3 hold and T4 holds, the nondeterminism is confined to the sampled drafter, which is an env switch.
- If T2 fails, K's kernels themselves are nondeterministic, which is the worse finding.
- If T5 fails, his speculative output is not exact. Prior art says that is normal for llama.cpp forks. It still
  contradicts his "lossless" claim at the token level.

## Validity

- **V1:** every request returns 512 (seeded) or 256 (greedy) tokens with no error.
- **V2:** no collapse: longest single-character run < 64 and > 20 distinct characters.
- **V3:** clocks at 150 W / 1,328 MHz before each server.
- **V4:** each server is alive at the end, with no abort line.

## Not tested

- Quality against a reference (KLD). That is the remaining step before adoption.
- Concurrency (`-np` > 1 on K).
- Long context.
- Distributional correctness of the sampled drafter (it would need thousands of samples).

## Deviations

Any change after the first row gets a numbered Deviation here before the affected rows run.
- **Deviation 1 (after all 8 registered arms, before this arm; 10-08 ~20:55): KSng, the sampled drafter without CUDA
  graphs.**
  - **Why:** KS varies within and across servers. KG, KN and KN0 never vary, and greedy text is exact in every arm.
  - **A hypothesis already ruled out by the log, without a run:** GPU top-k order in the offloaded draft sampler. KS's
    log says "backend sampling not supported with SPLIT_MODE_TENSOR; using CPU", so draft sampling is already on the
    CPU and `--no-spec-draft-backend-sampling` would be an inert knob (AFM-19).
  - **Next candidate:** `GGML_CUDA_GRAPHS_PRE_VOLTA=3` captures the single-token MTP draft steps. Replay jitter in the
    draft logits would move a sampled draw but not an argmax.
  - **Arm KSng:** KS's command and env minus `GGML_CUDA_GRAPHS_PRE_VOLTA`. One server, the same 3 seeded reps + greedy.
  - **Prediction D1a:** KSng still varies within the server, i.e. graphs are not the cause. (0.6)
