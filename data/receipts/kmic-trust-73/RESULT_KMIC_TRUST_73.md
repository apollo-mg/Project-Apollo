# Result -- Kaden's P100 fork is deterministic everywhere except its sampled drafter: kernels and greedy drafts reproduce byte for byte within and across servers, and its speculative greedy output is exact (identical to no-MTP). With `LLAMA_SPEC_SAMPLE_TEMP` on, all 9 seeded outputs differ. The daily build is bistable within a server even with `cache_prompt: false`

**2026-10-08.** Pre-registration `PREREG_KMIC_TRUST_73.md` (`312a6b6e`, 20:33:02). One deviation (`5d0ee5be`,
20:51:21), committed before its arm.
- **Runner:** `run_det73.sh` + `detbench.py` on .73.
- **Raw:** `raw/<ARM>.jsonl` (text, timings, draft counts, collapse stats per request), `.cmd`, `.clocks`, server
  logs (gzipped, home paths redacted).
- **Node:** the wake proxy was stopped 20:33-20:50 and 20:51-20:53, and restored after each window.

**Request:** the 2k corpus slice, temperature 1.0 / top-k 20 / top-p 0.95 / seed 1 / 512 tokens, three times per
server; then greedy, 256 tokens. `cache_prompt: false`.

## Validity

V1 (every request full length, no error), V2 (no collapse: longest run <= 3, > 20 distinct characters), V3 (150 W /
1,328 MHz before all 9 servers) and V4 (every server alive at the end, 0 abort lines) all **pass**.

## Results

First differing character between seeded outputs; "=" means byte-identical.

| arm | what it is | s1 vs s2 | s1 vs s3 | s2 vs s3 | vs its restart (s1/s2/s3/greedy) | greedy vs no-MTP |
|---|---|---|---|---|---|---|
| **DS** | daily: buun, VBR, `-np 2`, MTP 3 | 15 | **=** | 15 | -- | differs at 82 (different cache type; not a trust issue) |
| **KS** a / b | Kaden served: sampled drafter, graphs | 555 / 92 | 4 / 92 | 4 / 659 | 4 / 4 / 659 / **=** | **=** |
| **KSng** (Dev. 1) | KS without CUDA graphs | 6 | 555 | 6 | -- | **=** |
| **KG** a / b | greedy drafter, graphs | **=** / **=** | **=** / **=** | **=** / **=** | **= / = / = / =** | **=** |
| **KN** a / b | no MTP, graphs | **=** / **=** | **=** / **=** | **=** / **=** | **= / = / = / =** | (reference) |
| **KN0** | no MTP, no graphs | **=** | **=** | **=** | KN0 = KNa on all four | **=** |

- **Draft counts track the text.**
  - KG accepted 385 of 501 drafts in every seeded rep, both servers (greedy request: 252 / 190).
  - KS's counts move with every request (483-561 drafted). Even its greedy request drafts differently between
    servers (289 / 180 vs 284 / 182) and still emits identical text.
- **All 9 sampled-drafter outputs are distinct** (KSa, KSb, KSng x 3). Their pairwise first divergences fall at
  characters 4, 6, 92, 555, 596, 659, 1,022 and 1,074.
- **This morning's runs line up:**
  - D1's 2k seed-1 text equals DS s1 (and so DS s3). DS s2 is the other state.
  - K1's 2k seed-1 text differs from KSa s1 at character 6.
- **Speed** (2k, temperature 1.0): KG 63-64 t/s, KS 56-65, KN 30.3, DS 24.5.

## Registered verdicts

| # | claim | conf. | result |
|---|---|---|---|
| T1 | DS reps identical within a server | 0.7 | **fails**: s1 = s3, s2 differs at 15. Bistable, with every request on slot 1 and `cache_prompt: false` |
| T2 | KN/KN0 identical within and across servers | 0.75 | **holds** |
| T3 | KG identical within and across servers | 0.6 | **holds** |
| T4 | KS differs somewhere | 0.7 | **holds**: every pair differs |
| T5 | greedy KS = KN | 0.4 | **holds**, and KG = KN too, on both servers |
| T6 | greedy KN = KN0 | 0.8 | **holds**. The seeded texts match too |
| D1a | KSng still varies (graphs not the cause) | 0.6 | **holds** |

## What it means

- **K's numerics are deterministic.** Its target model, with or without CUDA graphs, and its greedy-draft speculative
  path reproduce byte for byte across requests and restarts.
- **K's speculative path is exact.** Greedy output with MTP on, using either drafter, equals greedy output with MTP
  off. That is better than our earlier forks: `RESULT_SPECULATION_IS_NOT_BIT_EXACT` found speculation-on never
  reproduced speculation-off greedy.
- **The one nondeterministic component is the sampled drafter** (`LLAMA_SPEC_SAMPLE_TEMP=1.0`, set in his QUICKSTART
  command).
  - It varies within a server and across restarts, with or without graphs, although the source reseeds both
    speculative RNGs from the request seed (`server-context.cpp` ~1846).
  - **Ruled out:**
    - GPU top-k ordering: the log shows draft sampling already falls back to the CPU under tensor split;
    - CUDA graphs: Deviation 1;
    - the target's kernels: KN, KN0.
  - **Not localised.** The divergence points recur across reps (4/6, 92, 555, 659), which suggests specific borderline
    positions where tiny run-to-run differences flip a draw. Where those come from is open.
  - **Practical consequence:** drop `LLAMA_SPEC_SAMPLE_TEMP` and the engine reproduces. His OPTLOG puts the cost at
    about 15 % fewer tokens per cycle at 2k. KG ran at 63-64 t/s here against KS's 56-65.
- **Our daily driver is not request-to-request reproducible either.** DS alternates between two outputs within a
  server, with `cache_prompt: false`, and agrees with a fresh server only on the first state.
  - This contradicts the memory note that `cache_prompt: false` fixes the bistability. It does not under the daily's
    VBR + `-np 2` + MTP config.
  - The likely carrier is VBR state persisting between requests. Untested.
- **Still missing before adoption:** quality against a reference (a KLD panel). Determinism and exactness, the
  "trustworthy engine" half, check out with the one switch noted.
