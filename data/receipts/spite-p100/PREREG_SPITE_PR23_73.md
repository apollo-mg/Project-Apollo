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
- **Addendum R (after the report, before any R row; 10-06 ~17:15): rerun at the new PR head `06e44a0`.**
  - **Origin:** the author pushed `b33e50f` (greedy decode no longer applies the repetition penalty) and `06e44a0`
    (NVLink/PCIe probe, prefer pipeline, Q6_K budget) after our runs. Mark approved a rerun.
  - **Same instrument:** host, model, kernels config, prompts.
  - **What reruns:**
    - T1 (build, cubins);
    - T3/T4 (4 prompts x default / `--gpus 1,0` / repeat);
    - T5 with the PR binary itself, now that temperature 0 should be penalty-free, against the llama.cpp outputs
      already captured (same file and server config, so not re-run);
    - T6 (`verify.py`);
    - T7 (`spite-bench`, compared with the captured llama.cpp 8.90 tok/s);
    - T8 (`spite run --mtp`, `spite-bench --mtp`).
  - T2 (`cargo test`) reruns on the desktop at the same commit.
  - **Predictions:**
    - **R1:** T5 now holds with the PR binary. Its outputs equal T5b's diagnostic build: p1-p3 through
      end-of-generation, p4 for 15 tokens. (0.8)
    - **R2:** `spite-bench --mtp` still crashes on the split. Neither new commit names it. (0.65)
    - **R3:** decode within 3 % of `ab8177a`'s 6.69 tok/s. (0.7)
- **Addendum R3 (before any R3 row; 10-06 ~19:35): round 3 at PR head `f1cc494`, requested on the PR by the author.**
  - **What the head claims:**
    - `092094f` fixes our #1 (the MTP split crash), #2 (the penalty is now once per distinct token, with a
      `repeat_last_n` 64 window) and #4 (stops on any control token).
    - Batched hybrid prefill (`a9bb561`..`290c102`) is aimed at #5.
  - **The author's asks:**
    - `verify.py` and `verify_batch_cuda.py` on the sm_60 `.so`;
    - spite-bench prefill before/after;
    - confirmation that greedy output is unchanged;
    - `cargo test`;
    - a refreshed `sm_60/tesla_p100/qwen3_5.bench`.
  - **Before/after instrument:** the `06e44a0` binaries and kernel `.so` files were copied to `~/spite-test/b06/`
    before the checkout, and run with `--kernels-dir` pointing there. Same host, model, clocks and session.
  - **Rows:**
    - T1 (build, cubins). T2 (desktop `cargo test`).
    - T3/T4 (4 prompts x default / `--gpus 1,0` / repeat), with generated text compared against `06e44a0`'s.
    - T6: `verify.py` and `verify_batch_cuda.py <vendor .so> <libcudart.so.12>`.
    - T7:
      - `spite-bench` defaults, after (decode, `.bench` line);
      - `spite-bench --n-prompt 512 --n-tokens 32 --n-runs 3`, before and after (prefill);
      - llama.cpp prompt processing for the same 512-token padded prompt, matched `-sm layer` server, 3 runs, as
        context.
    - T8: `spite-bench --mtp` (after).
  - **Predictions:**
    - **Q1:** both verify tools pass on sm_60. (0.75)
    - **Q2:** prefill at 512 prompt tokens is at least 3x the `06e44a0` binary's. (0.55)
    - **Q3:** decode within 3 % of 6.69 tok/s. (0.75)
    - **Q4:** greedy text equals `06e44a0`'s on all 4 prompts, up to where `06e44a0` printed its first EOG token.
      (0.6)
    - **Q5:** p1-p3 now end at the EOG token, with nothing after it. (0.85)
    - **Q6:** `spite-bench --mtp` completes on the split. (0.7)
- **Addendum R4 (before any R4 row; 10-07 ~13:40): round 4 at PR head `f85a2a2`, requested by the author ("probably the
  last one I do").**
  - **What the commit claims:**
    - batched prefill across stages (the `batch_capable` single-stage gate is removed, and `[d, m]` blocks pass over
      the host hop);
    - real MTP. `MtpBenchRunner` sampled the trunk's logits as the "draft", so acceptance was structurally 0. Now an
      exact speculative-decode loop drives the NextN head, and greedy is claimed bit-exact against plain decode.
      `--mtp` / `--draft-tokens` are wired into `spite run`.
  - **Before/after:** the `f1cc494` binaries and `.so` files are saved to `~/spite-test/b_f1/` before the checkout.
  - **Rows:**
    - T1 build. T2 `cargo test` (desktop).
    - T6: `verify.py`, `verify_batch_cuda.py`.
    - T3/T4: 4 prompts x default / `--gpus 1,0` / repeat, compared with `f1cc494`'s text.
    - T7: `spite-bench --n-prompt 512 --n-tokens 32 --n-runs 3`, before and after; `spite-bench` defaults after.
    - T8:
      - `spite-bench --mtp`, plus `--draft-tokens 2` and `3` (acceptance, decode);
      - `spite run --mtp` on the 4 prompts, text compared with plain `spite run`.
  - **Predictions:**
    - **S1:** both verify tools pass. (0.85)
    - **S2:** prefill at 512 tokens is at least 3x `f1cc494`'s 7.23 tok/s on the 2-stage split. (0.6)
    - **S3:** plain decode within 3 % of 6.67 tok/s. (0.8)
    - **S4:** greedy text equals `f1cc494`'s on all 4 prompts. (0.65)
    - **S5:** `spite-bench --mtp` acceptance above 30 %, and `spite run --mtp` text identical to plain on all 4. (0.55)
    - **S6:** MTP decode at least 1.2x plain decode. (0.4)
- **Addendum R5 (before any R5 row; 10-07 ~17:10): round 5 at `caa2d72` (head `6e708fb` = `caa2d72` plus a test
  comment), the author's list.**
  - **What the head claims:** the MTP KV is filled over the prompt. The draft head previously attended over unwritten
    KV rows, so round 4's ~99 % acceptance came from a context-blind head.
  - **Method correction accepted from the author:** "text identical to plain under `--mtp`" does not show the head
    ran, since the loop emits only trunk-argmax tokens. Acceptance > 0 does.
  - **Rows:**
    - verify tools; `cargo test` (desktop);
    - refreshed `spite-bench` rows (512/32/3 and defaults);
    - (a) prompt-length scaling at n = 8/32/128/512;
    - (b) `nsys profile --trace=cuda,osrt --stats=true` on a 512-token prefill at `caa2d72` and at the saved
      `f1cc494` binaries, plus `--n-tokens 16` at `caa2d72`;
    - (c) `sudo ncu` on `gemv_batch_kernel` / `gemv_row_kernel`. Run unconditionally, because ncu needs root here
      (RmProfilingAdminOnly=1) and a second window costs more than the run.
    - (d) an `nvidia-smi` 1 s log during the 512 run, plus `-q -d PERFORMANCE,ECC`;
    - (e) tool versions and `cuobjdump -res-usage`;
    - (f) real-text MTP acceptance (the author's Roman Republic prompt, 128 tokens, K = 1).
  - **Not run:** the generic CPU gate row. `DenseWeights::load` dequantizes every tensor to F32 (~108 GB for the
    27B) against 15 GiB of RAM on .73. Reported as infeasible on this box.
  - **Predictions:**
    - **V1:** verify tools and `cargo test` unchanged. (0.9)
    - **V2:** 512-token prefill within 5 % of round 4's 7.89 tok/s, despite the added draft pass per prompt token.
      (0.6)
    - **V3:** TTFT scales roughly linearly with prompt length: TTFT(512) / TTFT(128) >= 3.5. (0.8)
    - **V4:** the sum of GPU kernel time under nsys is below 50 % of the 512-token prefill wall time (host and sync
      gaps dominate). (0.55)
    - **V5:** real-text MTP acceptance at K = 1 is between 40 % and 90 %. (0.6)
  - **R5-b (after the (f) row, before its follow-ups; 10-07 ~17:45): is the 100 % real-text acceptance real?**
    - (f) gave acceptance 100.0 % at K = 1 on the author's Roman Republic prompt. That is implausible for a NextN
      head on free text, and the bench reports no token count.
    - **Reference:** buun `510cb-nohost` llama-server, the daily driver's binary, on the same GGUF, its own NextN head
      (`--spec-type draft-mtp --draft-max 1`), `-sm layer -fa on -c 8192 -np 1`, f16 KV, `/completion` greedy,
      `cache_prompt` false, the same prompt, 128 tokens. Acceptance = `draft_n_accepted / draft_n` from its timings.
    - **Also:** spite `--mtp --draft-tokens 2` and `3` on the same prompt.
    - **Prediction R5-b1:** llama.cpp's K = 1 acceptance on this prompt is below 95 %, which would make spite's 100 %
      a counting or drafting artifact, not a property of the head. (0.75)
- **Addendum R6 (before any R6 row; 10-08 ~17:45): round 6 at `2a7d5ac` plus the row-tiling commit `69676bc` (PR head),
  run together in one pass.**
  - **Origin:** the author's round-6 list on the PR (6 questions, posted at `2a7d5ac`), then `69676bc` ("Owed before
    this can gate a PR: the P100 before/after"). Mark: option 1, one combined pass, a short results table instead of a
    full write-up per round.
  - **Prior art checked:** this file's own R3-R5 rows; nothing else covers spite.
  - **Binaries, all built on .73 the same way as R5:** `6e708fb` (R5 head, saved to `b_6e7/`), `2a7d5ac` (saved to
    `b_2a7/`), `69676bc` (in tree). `cuobjdump -res-usage` captured for each new `.so`.
  - **27B rows** (same Q6_K file, 2-stage split, 150 W / 1,328 MHz recorded):
    - verify: `verify.py` and `verify_batch_cuda.py` on the `69676bc` sm_60 `.so`; `cargo test --workspace` at
      `69676bc` on the desktop.
    - prefill/decode: `spite-bench --n-prompt 512 --n-tokens 32 --n-runs 3` at all three binaries, in the order
      `6e708fb`, `2a7d5ac`, `69676bc`; defaults at `69676bc`.
    - MTP (author's Q1/Q2): `spite-bench --prompt "<Roman Republic>" --n-tokens 128 --n-runs 1 --mtp
      --draft-tokens 1/2/3` at `69676bc`: acceptance, `draft-vs-trunk TV`, decode. The same prompt without `--mtp`
      for the plain decode it has to beat.
    - greedy text: `spite run` on the 4 raw prompts at `69676bc`, compared with R4's plain text; `spite run --mtp` on
      the Roman Republic prompt compared with plain.
  - **Small model (author's Q2/Q3; Mark: "pick whatever works and fits"):** unsloth `Qwen3.5-2B-MTP-GGUF`,
    `Qwen3.5-2B-Q6_K.gguf`.
    - **Why this file:** `qwen35` with a NextN block (checked before any row); the same Q6_K type as the 27B; ~1.9 B
      params, so ~7.8 GB once `DenseWeights::load` expands it to F32, inside .73's 15 GiB. Our Qwen3.5-4B is 16.8 GB as
      F32 and has no NextN block.
    - **CPU gate row:** `spite-bench --device cpu --n-prompt 16 --n-tokens 8 --n-runs 1`, then the same command on
      `--device cuda --card TESLA_P100`, and CUDA defaults.
    - **Unsplit MTP:** the 2B fits on one card, so spite-bench places it unsplit. Roman Republic prompt, K = 1/2/3:
      acceptance and TV.
    - **Reference:** buun `510cb-nohost` llama-server on the same 2B file, one GPU, `--spec-type draft-mtp
      --draft-max 1`, greedy, `cache_prompt` false, 128 tokens.
    - **Conditional:** spite-bench has no split override. Only if the 2B unsplit acceptance is within 10 points of
      llama.cpp's (a healthy head unsplit) does a forced-split comparison follow, as a numbered deviation.
  - **Not run:** a `SPITE_GEMV_BATCH_CHUNK` sweep. At `69676bc` the chunk only governs the untiled form, which
    `rows / kRowTile >= kRowTileMinBlocks` restricts to shapes under ~1,024 rows; the 27B's large projections all
    take the tiled (4, 4) form. Reported with the register counts instead.
  - **Predictions:**
    - **W1:** both verify tools pass at `69676bc`; `cargo test` passes with >= 150 tests. (0.85)
    - **W2:** 512-token prefill at `2a7d5ac` is >= 1.05x `6e708fb`'s (batched MTP prefill removes the per-token draft
      pass). (0.6)
    - **W3:** 512-token prefill at `69676bc` is >= 1.30x `2a7d5ac`'s (the author measured 1.42-1.58x per projection
      on an RTX 5090). (0.55)
    - **W4:** plain decode at `69676bc` within 3 % of 6.69 tok/s (the m = 1 path is unchanged). (0.8)
    - **W5:** 27B, K = 1: acceptance >= 95 % and TV < 0.05, i.e. the head still reproduces the trunk. (0.55)
    - **W6:** 27B MTP decode at K = 1 >= 1.2x plain decode on the same prompt (batched verify). (0.45)
    - **W7:** the 2B unsplit shows the same artifact: spite K = 1 acceptance >= 10 points above llama.cpp's on the same
      file. That points at the head path, not the split. (0.55)
    - **W8:** the CPU gate row completes on the 2B. (0.8)
    - **W9:** greedy text at `69676bc` equals R4's on all 4 prompts, and `--mtp` text equals plain. (0.75)
  - **Deviation R6-1 (after the 27B `--mtp` text row, before any of these rows; 10-08 ~18:20): is the `--mtp` text
    divergence a split bug or a verify bug?**
    - **Why:** at `69676bc`, `spite run --mtp` (K = 3 default) on the Roman Republic prompt diverges from plain greedy
      at character 14 ("overthrown in 5091509 BC"), while spite-bench reports 100 % acceptance at K = 1/2/3 with TV
      0.10-0.13. An exact greedy loop can only emit the trunk's own tokens, so the verify accepts drafts the trunk would
      not choose. The host acceptance code (`spite-executor` batched path) indexes `batch_logits[k]` against draft `k`
      correctly on reading, which points at the logits `verify_batch` returns.
    - **Rows** (after the main R6 runner exits; `spite run`, greedy, 128 tokens, the Roman Republic prompt; `spite run`
      prints no acceptance, so these are text checks):
      - 27B, `--mtp --draft-tokens 1` (verify width 2), against the plain text already captured;
      - 2B unsplit (automatic placement): plain, `--mtp`, `--mtp --draft-tokens 1`;
      - 2B forced split `--gpus 0,1 --layer-split 12,12`: plain, `--mtp`;
      - 2B plain text against llama.cpp's greedy text from the reference row (same file).
    - **Predictions:**
      - **R6-1a:** 27B `--mtp` at K = 1 also differs from plain. (0.7)
      - **R6-1b:** 2B unsplit `--mtp` differs from plain, so the fault is in the verify, not the split. (0.65)
      - **R6-1c:** 2B split plain text equals 2B unsplit plain text. (0.8)
  - **Deviation R6-2 (after R6-1, before these rows; 10-08 ~18:16): did the row-tiling commit cause the 27B
    divergence?**
    - **Why:** R6-1: every `--mtp` text differs from plain, both models, split or not (2B split `--mtp` = 2B unsplit
      `--mtp` byte for byte). The 2B diverges at character 11 with 83 % acceptance, which fits the rollback reading:
      `rollback_drafts` restores the GDN state saved before the whole batch, and nothing replays the accepted prefix.
      But the 27B diverges at character 14 with 100 % acceptance, so no rollback ran there; its verify rows agree with
      drafts plain decode rejects. `69676bc` changed the batched GEMV used by the verify (row tiling at >= 1,024 rows).
    - **Rows:** the saved `2a7d5ac` binaries (batched verify, no row tiling) on the 27B: `spite run --mtp
      --draft-tokens 1` text against plain, and `spite-bench --mtp --draft-tokens 1` on the Roman Republic prompt
      (acceptance, TV).
    - **Prediction R6-2a:** `2a7d5ac` also diverges at K = 1 on the 27B, i.e. the fault predates the row tiling.
      (0.6)
  - **R6-3 (after the R6 result, before the capture; 10-08): a clean profile for the author's Q5.** The R5 profiler
    streams embed the run's shell environment (hundreds of `NAME=value` strings), so they are not sent. Instead: one
    `nsys profile --trace=cuda,osrt` of `spite-bench --n-prompt 512 --n-tokens 16 --n-runs 1` at `69676bc` on the 27B,
    run under `env -i` (PATH and the CUDA library path only) from a copy of the binaries outside the home directory. The
    file is scanned for environment strings before it leaves the box. A capture, not a test: no prediction.
