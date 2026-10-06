# Pre-registration: does Spite PR #23 run Qwen3.8-27B on two PCIe P100s correctly, and how fast against llama.cpp on the same file and cards?

**Registered 2026-10-06, before any GPU row.**
- **Origin:** the PR author (giveen / JabbaTheDuck) asked Mark to pull Spite and test `giveen/spite#23`: "I dont want to
  merge it until I have real answers." Mark: "Yep let's have a looksie. My quad machine is tied up so we'll use the
  dual machine."
- **The PR's own pre-merge list,** which it has never run on Pascal:
  - `spite run` with one "stage" line per GPU;
  - `spite-bench`;
  - `tools/verify/verify.py` on sm_60;
  - real cross-device switching (only ever run with every stage on GPU 0).

**Prior art checked:** `ledger_precheck.py "Spite engine P100 Qwen3.8-27B pipeline split"` -> nothing on Spite. The
hits were keyword noise.

**What this adds:** the first run of Spite on Pascal, and the first with its stages on separate GPUs.

## Instrument

- **Host:** .73.
  - 2x Tesla P100-PCIE-16GB, `nvidia-smi topo -m` PHB, no NVLink.
  - i7-8600K, 16 GB RAM.
  - Driver 580.178.04, SM clock locked at 1,328 MHz (application clocks; recorded per run), 150 W cap.
- **Spite:** `giveen/spite` PR #23 head `ab8177a` (on main `453e98f`). Kernels from
  `cmake -DSPITE_MODELS=qwen/qwen3_5 -DSPITE_GPU_ARCHS=TESLA_P100`, CUDA 12.4.131 with gcc-13.4 as host, Release.
  `cuobjdump` shows sm_60 cubins in both `.so` files. Host built with Rust 1.97.1, `cargo build --release`.
- **Model:** unsloth Qwen3.8-27B Q6_K, the .73 daily-driver file, 22,884,408,288 B.
  - sha256 recorded in `raw/` before any row.
  - `qwen35`, 64 trunk blocks + 1 NextN block (`nextn_predict_layers = 1`).
  - Q6_K is in the qwen3_5 CUDA kernel's type list.
  - The PR's own test file (Hemmingway-1 Q5_K_S) is not on hand.
- **llama.cpp reference:** buun `510cb-nohost` llama-server (the daily driver's binary) on the same file and cards.
  - `-sm layer -fa on -ctk f16 -ctv f16 -c 8192 -np 1 -fit off -ngl 99`, no drafter: the pipeline-matched
    configuration.
  - Plus the daily-driver flags (`-sm tensor`, VBR KV, MTP draft 3) once, as context and not as the matched
    comparison.
- **Node state:** for the window, the daily-driver llama-server is stopped, and the desktop's wake proxy is stopped
  too (otherwise it relaunches llama-server into the test on the next request). Both are restored after.

## Tests

1. **T1, build:** both kernel `.so` files contain sm_60 cubins; `cargo build --release` succeeds.
2. **T2, `cargo test --workspace`** (CPU; the PR reports 126 passed).
3. **T3, load and split:**
   - Command: `spite run -m <Q6_K> --card TESLA_P100 --device cuda --ctx 8192`, greedy, 128 tokens.
   - Three fixed prompts: an arithmetic question, the capital of France, and a one-sentence definition of
     photosynthesis. Chat template as `spite run` applies it, recorded.
   - **Gate:** two stage lines (GPU 0, GPU 1) and a coherent, correct answer to each.
4. **T4, cross-device:**
   - The T3 prompts again with `--gpus 1,0` (stage order reversed).
   - A second default run.
   - **Holds** if all three runs give identical text.
5. **T5, agreement with llama.cpp:**
   - **First choice:** wikitext-2 test perplexity (512 context, 16 chunks), if Spite's perplexity tool runs on CUDA
     with the hybrid decoder, against `llama-perplexity` on the same file, chunks and `-sm layer`. **Holds** if the
     PPLs are within 1 %.
   - **Otherwise:** greedy continuation of three raw prompts (no chat template), 64 tokens each, compared token by
     token with llama.cpp `/completion` (`cache_prompt: false`). The common prefix length is reported. **Holds** if
     each prefix is at least 16 tokens, since near-ties legitimately split two engines after that.
   - Which branch ran is recorded.
6. **T6:** `tools/verify/verify.py` on the qwen3_5 CUDA kernel `.so` passes.
7. **T7, speed:**
   - Spite: `spite-bench --card TESLA_P100 --device cuda` with its defaults (recorded).
   - llama.cpp: the matched server, the canonical reasoning-v1 prompt, 256 tokens, greedy, 1 warmup + 3 timed,
     median `predicted_per_second` and `prompt_per_second` from the server's timings.
   - If spite-bench measures something different (prompt length, token count), Spite is also timed by its own
     run output on the same prompt where it reports it, and the mismatch is stated.
8. **T8:** whether `spite run` uses the NextN/MTP head for speculative decoding, read from its output or flags. If it
   can, one run with it on.

## Predictions

| # | claim | confidence |
|---|---|---|
| P1 | T1 and T2 hold | 0.8 |
| P2 | T3 passes on two GPUs (the split has never run on a device other than 0) | 0.55 |
| P3 | T4 holds (given P2) | 0.7 |
| P4 | T5 holds | 0.6 |
| P5 | T6 passes on sm_60 | 0.6 |
| P6 | Spite's decode is at least 50 % of llama.cpp `-sm layer` decode on this pair | 0.4 |

## Not tested

- The PR's 6-GPU target (only 2 here).
- Q5_K_S.
- Tensor parallelism (`p100_multi` is policy only, not wired).
- Long context.
- Concurrency.

## Reporting

- Results go to the PR author through Mark.
- ggml-org's AI policy does not apply to `giveen/spite`. Its `AGENTS.md` lets agents open PRs and run `verify.py` and
  `spite-bench`.
- Anything posted on GitHub as Mark's agent is drafted, shown to Mark and posted only on his OK, with the footer.

## Deviations

Any change after the first GPU row gets a numbered Deviation here before the affected rows run.
