# Model MRI — MoE expert-routing capture & analysis

Resurrected 2026-09-16 (the original was a WebUI heatmap whose llama.cpp capture hook was lost).
Rebuilt as a clean, model-agnostic three-layer toolset: a dumb C++ capture firehose + Python analysis.

## What it does

For any GGUF MoE, capture the router's per-layer, per-token expert distribution (`ffn_moe_probs`),
then measure: expert **utilization** (layer × expert heatmap), adjacent-token **routing locality**,
router **entropy/confidence**, dead/hot experts, and **base-vs-fine-tune routing diffs**.

## Layer 1 — capture (`moe-capture.cpp`)

A `cb_eval` hook on top of buun-llama-cpp's `examples/eval-callback`. Runs one decode over a prompt and
dumps the raw `ffn_moe_probs` (the softmax over all experts, pre-top-k) for every layer/token.

**Build** (against buun-llama-cpp, RDNA4/gfx1201 example):
```
cp moe-capture.cpp            <buun-llama-cpp>/examples/moe-capture/moe-capture.cpp
cp moe-capture-CMakeLists.txt <buun-llama-cpp>/examples/moe-capture/CMakeLists.txt
# add `add_subdirectory(moe-capture)` to examples/CMakeLists.txt, then:
cmake --build build --target llama-moe-capture -j$(nproc)
```

**Run** (CPU capture is fine — routing doesn't need speed):
```
MOE_CAP_OUT=trace.bin ./build/bin/llama-moe-capture -m model.gguf -ngl 0 -c 1024 -f corpus.txt
```

**Binary format** (little-endian), one record per MoE layer per decode:
`int32 layer` · `int32 n_expert` · `int32 n_tokens` · `float32 probs[n_expert*n_tokens]`
(column-major: token `j`'s distribution at `probs[j*n_expert : (j+1)*n_expert]`).

## Layer 2 — analysis (Python)

```
analyze_mri.py <trace_dir>        # expects mri_code.bin + mri_prose.bin -> utilization/locality/entropy + mri_heatmap.png
analyze_mri_diff.py <trace_dir>   # expects base_{code,prose}.bin + mri_{code,prose}.bin -> routing preservation + mri_diff.png
```
`K` (routing width) is hardcoded to 8 (Qwen3.6-35B-A3B). `corpora/` holds the code + prose samples used.

## Known limits / TODO

- **Routing family:** captures plain `ffn_moe_probs`, correct for **softmax-top-k** models (Qwen). For
  **sigmoid-group** models (DeepSeek/GLM) the selected experts come from the group-masked path
  (`ffn_moe_probs_masked`); add that name to `is_probs()` (and skip the plain probs) to support them.
- N-of-1 corpora in the first runs — multi-sample before treating any single number as rigorous.
- CPU capture; K fixed at 8; per-token diffs require the two models to share a tokenizer (token counts match).
