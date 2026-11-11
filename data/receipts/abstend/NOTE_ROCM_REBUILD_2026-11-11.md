# NOTE: the shared f74e2fa build_rocm llama-server was rebuilt in place on 2026-11-11, and reproduces its stored output

While testing `data/scorecard/build_engine.sh`, I ran it against the existing checkout
`engines/llama_cpp_upstream_f74e2fa` (same commit, f74e2fa6). Its reconfigure (`LLAMA_BUILD_TESTS` ON -> OFF; compiler,
`GGML_NATIVE` and arch unchanged in the cache) recompiled 207 objects and relinked `build_rocm/bin/llama-server`
(new sha256 `e67a3d9c...`; the old binary's hash was never recorded). That binary serves the 9070 recipes and the frozen
AbstentionBench judge.

**Check:** the stored greedy arm S26G (Spark-X2.6-4B Q8_0, recipe `spark-x2.6-4b`, the same flags and file, sha256
verified) replayed on the rebuilt binary as S26GR: `abstend.py compare S26G S26GR` -> 240 of 240 items, content 0
differ, finish 0, grade 0, P_abs 0 (tolerance 1e-6). Raw: `quant-abstention/raw/main_S26GR.jsonl`.

**Fix:** `build_engine.sh` now refuses an existing destination unless `REBUILD=1`, and says a replay is owed after.
