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
- **Deviation 1 (before any GPU row; 10-06 ~15:40): raw prompts, because `spite run` applies no chat template.**
  - **What the source shows:** `spite run` encodes the prompt as raw text (`tokenizer.encode(prompt, add_bos)`) and
    has no template or special-token option. ChatML markers would be tokenized as literal text.
  - **T3's three prompts** are therefore completion-style raw text:
    - `Question: What is 17 multiplied by 23?\nAnswer:`
    - `Question: What is the capital of France?\nAnswer:`
    - `Question: Define photosynthesis in one sentence.\nAnswer:`
    - Each gets 128 greedy tokens. **Gate:** two stage lines, and the continuation contains a correct answer (391,
      Paris, a sensible definition) in coherent English.
  - **T5 takes its "otherwise" branch.** `spite-perplexity`'s source has no CUDA or hybrid path, so the PPL
    comparison is unavailable.
    - The agreement test uses these three prompts plus the PR's own example `The old man walked to the harbor and`.
    - The same strings go to llama.cpp `/completion` (`temperature 0`, `n_predict 128`, `cache_prompt false`).
    - The first 64 tokens are compared. The common prefix is measured in llama.cpp tokens (via `/tokenize`), and the
      prompt token counts are compared too.
- **Deviation 2 (before any GPU row): T2 runs on the desktop, not .73.**
  - `cargo test --workspace` on .73 stops at `openssl-sys`'s build script: "Could not find directory of OpenSSL
    installation". Ubuntu 26.04 on .73 has no OpenSSL headers, and no system packages are installed on .73 for this.
  - T2 is the PR's CPU-only suite, so it runs in the desktop checkout of the same commit `ab8177a`: CachyOS, OpenSSL
    3.6.4, Rust 1.97 from the repo's toolchain pin.
  - The release binaries T3-T8 use built on .73 without hitting this, because `cargo build --release` does not
    compile that dependency.
- **Deviation 3 (after T3-T8, before any T5b row; 10-06 ~15:55): T5b, the agreement test with Spite's sampler
  neutralised.**
  - **Why:** T5's comparison is confounded. `Executor::generate` (`crates/spite-executor/src/lib.rs`) hard-codes
    `repetition_penalty: 1.1` for every `spite run`, temperature 0 included. `apply_repetition_penalty` divides a
    positive logit by the penalty **once per occurrence** in the whole context, prompt included, so a token seen k
    times is divided by 1.1^k. llama.cpp's greedy run used no penalty.
  - **T5b:** a local diagnostic build that changes only that line to `1.0`, built in the same tree on .73 and kept
    as a separate binary. The PR binary is kept and restored.
    - The same four prompts on the same default split, 128 tokens.
    - Compared with the llama.cpp outputs T5 already captured (same file, `-sm layer`, f16 KV, no penalty).
  - **T5b holds** if prompt 1 starts with " 391", and each Spite continuation matches llama.cpp's up to llama.cpp's
    end-of-generation token or for at least 16 llama.cpp tokens.
  - If T5b holds, the T5 differences are the sampler, not the P100 kernels.
  - The daily-driver server and the wake proxy are taken down again for these runs and restored after.
