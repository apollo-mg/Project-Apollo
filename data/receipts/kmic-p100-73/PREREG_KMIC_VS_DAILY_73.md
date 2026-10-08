# Pre-registration -- Kaden's P100 fork (Kmic-68/llama.cpp) vs the .73 daily driver, head-to-head on .73

**2026-10-08, before any run.** Kaden's fork (`Kmic-68/llama.cpp`, branch `p100-optimizations`, pinned at
`e48e240a8c9549f88c60b4cd47c8cd44bbf22f36`, MIT) is tuned for the rig .73 already is: two P100-PCIE-16GB on `-sm
tensor`, the same `Qwen3.8-27B-Q6_K.gguf`, MTP, 262k context with vision, and the model card's sampling. Its README
claims tg256 33.2 t/s (upstream at its fork point 17.51), MTP decode 54 t/s at 2k and 38 t/s at 122k, prefill 454 t/s
at 2k. Our own `split-prefill-73` (09-24) measured the daily config at decode 24.7 -> 8.0 and prefill 151 -> 99 from
2k to 128k. Those are his claims against our receipt, on different power caps (his 175 W, ours 150 W), clocks (our
receipt predates the 1328 MHz change of 09-28) and KV caches (q4_0 vs VBR). This test measures both on one rig.
Mark: "Sure let's give it a build" (build), the run itself on his OK.

**Prior art checked:** `ledger_precheck.py "kaden kmic p100 fork head-to-head decode daily driver"` and
`"P100 mmvq decode matvec tensor split Qwen3.8 MTP fork"` -> receipts found:
- `split-prefill-73/RESULT_SPLIT_PREFILL_73.md` (09-24): the D arm's depth curve at 1063 MHz on buun `08826ad6e`.
- `kv-tensor-split/RESULT_XFORK.md`, `RESULT_UPSTREAM.md` (08-17): q8_0/q8_0 and q4_0/q4_0 KV collapsed to 512 `/` on
  sm_60 in the turboquant forks; upstream was clean. K serves q4_0/q4_0, so a collapse check is mandatory (V2).
- `pulsar/MTP_PASCAL_NMAX_MMVQ.md` (08-03): the MMVQ batch table sets the MTP n-max ceiling on Pascal.
- `sm60-types/` (09-29..10-01): per-type decode kernel costs on sm_60.

**What this adds:** the first measurement of an independently tuned P100 fork on our rig. Also the first daily
depth curve at 1328 MHz, and a decode attribution (weight path vs attention at depth) from the same session.

## Arms

| arm | binary | flags |
|---|---|---|
| **D** (daily) | buun `510cbbbfa` + `f08683ffa` (local `ccb273321`), `/mnt/HDD/buun-510cb-nohost/build_sm60` (sm_60 only, gcc-13 host, carve-out present) | the wake proxy's `WP_START_CMD` (`-c 262144 -ctk vbr -ctv vbr --vbr-floor t4 --vbr-vram auto -np 2 --kv-unified -sm tensor -fa on --spec-type draft-mtp --draft-max 3`, mmproj F16, model-card sampling), **minus** `--resume*` (a test leg must not read or write the live store) |
| **K** (Kaden) | `e48e240a8`, `/mnt/HDD/kmic-p100/src/build-opt`, built per his `BUILD.md` (`-DCMAKE_CUDA_ARCHITECTURES=60 -DGGML_CUDA_NCCL=OFF -DGGML_CUDA_FA_QUANTS=all`, Release) plus the .73 pins (`/usr/bin/nvcc`, gcc-13 host) | his `QUICKSTART.md` command verbatim (`GGML_CUDA_P2P=1 GGML_CUDA_GRAPHS_PRE_VOLTA=3 LLAMA_SPEC_SAMPLE_TEMP=1.0 LLAMA_SPEC_DRAFT_TOPK=20`, `-sm tensor -fa 1 -ctk q4_0 -ctv q4_0 -c 262144 -b 32768 -ub 2048 -np 1 --spec-type draft-mtp --spec-draft-n-max 4 --spec-draft-p-min 0.2 -ngld 99 -ubd 64 -ctkd q4_0 -ctvd q4_0 --temp 1.0 --top-k 20 --top-p 0.95 --min-p 0.0`), **plus our `mmproj-F16.gguf`** (he uses a Q8_0 projector; ours is the one the daily serves) |

Each arm runs as it would serve, so the served rows answer "what would .73 get from switching". They are not a
kernel-for-kernel attribution. M1 below is the matched-flag part.

**Registered fallback (K only):** if K fails to load, or OOMs during the 128k request at `-ub 2048` with the F16
projector, rerun that leg at `-ub 1024` (his own documented fix). Record it as a numbered Deviation before the rerun.

## Instrument

- `.73`, both GPUs. Live `nvidia-smi` clocks, power limit and temperature are recorded before every leg; the 09-28
  policy is 150 W / application clocks 715,1328.
- The wake proxy is **stopped** for the duration (it would relaunch the daily server or suspend the node). Busy locks
  on `.73` hold it awake. The daily driver is down from proxy stop to proxy restart.
- **Fresh server per leg**, then one discarded warmup completion; readiness = a completion that returns tokens.
- **M1, matched-flag microbench, as server legs.** The daily build tree has no `llama-bench`, and building one would
  touch the live tree.
  - **Flags, identical on both builds:** `-ngl 99 -sm tensor -fa on -ctk f16 -ctv f16 -c 8192 -np 1 -b 2048 -ub 2048
    -fit off`, no MTP, no projector, `GGML_CUDA_P2P=1`.
  - **Cells, in order:** D, K, K, D, then **D0** (D without `GGML_CUDA_P2P`).
    - D vs D0 measures the P2P env alone. .73's cards report P2P read OK (`nvidia-smi topo -p2p r`), and the daily
      driver does not set it.
    - f16 KV on both, because buun's history of quantized KV under tensor split makes q4_0 on D a validity risk.
  - **Requests per cell:** the 2k slice, `n_predict 256`, temperature 0, `ignore_eos`, `cache_prompt: false`, 3 reps.
    Prefill is the 2k prompt's `prompt_per_second`; plain decode is `predicted_per_second`.
- **M2, served depth curve** (`/completion`, raw token ids, `cache_prompt: false`, `ignore_eos`, `n_predict 512`,
  temperature 1.0 / top-k 20 / top-p 0.95 / min-p 0, fixed seeds). The prompts are disjoint slices of
  `quant-hesitation/corpus_reasoning.txt`, from the token ids already in `split-prefill-73/raw/corpus_ids.json`
  (same GGUF, so the same tokenizer; V1 checks it):
  - **2k** `[212992:215040]`, seeds 1 and 2;
  - **32k** `[131072:163840]`, seeds 1 and 2;
  - **128k** `[0:131072]`, seed 1 (legs D1/K1 only).

  Legs in order **D1, K1, K2, D2**. D1 and K1 run 2k, 32k, 128k; K2 and D2 run 2k and 32k only. Recorded: server
  `timings` (prompt tok/s, predicted tok/s, draft n / accepted), wall time, and the decoded text.
- **Primary metric:** decode = `timings.predicted_per_second`; prefill = `timings.prompt_per_second`. Averaged per
  arm and depth over legs and seeds.

## Validity checks (a failed check voids the affected rows; it is reported, not patched)

- **V1** tokenizer: `/tokenize` of the first 4,000 corpus characters is identical on D and K.
- **V2** no collapse: every K completion has a longest run of a single character < 64 and > 20 distinct characters.
- **V3** vision works on K: one `/v1/chat/completions` with `split-prefill-73/media_probe.png` returns non-empty
  content (thinking off).
- **V4** live clocks: the leg's pre-run `nvidia-smi` shows 150 W and 1328 MHz application clocks on both GPUs.
- **V5** the server survived the leg (alive at the end, no `GGML_ASSERT` / abort in its log).

## Predictions

| # | claim | confidence |
|---|---|---|
| P1 | M1 plain decode (256 tokens after the 2k prompt, f16 KV, no MTP): K >= 1.5x D | 0.7 |
| P2 | M1 prefill (2k prompt, ub 2048): K >= 1.8x D (D does fp32 math under the carve-out, K uses fp16 products with fp32 folds) | 0.6 |
| P7 | M1: D with `GGML_CUDA_P2P=1` decodes >= 3 % faster than D0 | 0.5 |
| P3 | M2 served MTP decode at 2k: K >= 1.5x D | 0.65 |
| P4 | M2 served MTP decode at 128k: K >= 2.5x D (the whole-cache f16 conversion D still does per attention call) | 0.6 |
| P5 | M2 prefill at 32k: K >= 2x D | 0.6 |
| P6 | V2 and V3 pass on K at `-ub 2048` with the F16 projector, without the fallback | 0.6 |

## Not tested

- Quality (KLD vs an fp32 base). D runs fp32 math (carve-out); K's own claim is mean KLD ~0.0012 vs fp32 on his corpus.
  That needs a separate panel.
- `-np 2` concurrency on K, `--resume` (K has no equivalent), and tool-calling or agent behaviour.
- Depths above 128k.
- Any change to the daily driver. Switching is Mark's decision after the result.

## Deviations

Any change after the first row gets a numbered Deviation here before the affected rows run.

- **Deviation 1 (build, before any row): one-line local patch to K.**
  - **Error:** the build stopped at 45% with `src/llama-context.cpp:2178: error: no matching function for call to
    'max<int64_t>(<brace-enclosed initializer list>)'`. The host C++ compiler here is GCC 15.2. Only nvcc's host
    compiler is pinned to gcc-13, as in the D build. The file uses `std::max` on an initializer list without
    including `<algorithm>`, which GCC 15 no longer pulls in transitively.
  - **Fix:** add `#include <algorithm>` (`local_patch_algorithm_include.diff`, kept next to the build on .73 and
    copied here). It changes no code path.
  - **Resume:** the build continued in the same tree with the same flags. The CUDA objects were already compiled and
    are unaffected.
