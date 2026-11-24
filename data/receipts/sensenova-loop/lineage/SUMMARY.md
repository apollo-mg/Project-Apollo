# SenseNova-Loop-9B is Qwen3.5-9B, heavily retrained (2026-11-24; Mark asked, not preregistered)

Every same-named tensor of SenseNova-Loop-9B's full-precision weights (sha256-checked, sensenova/SenseNova-Loop-9B) compared
with Qwen3.5-9B's (our verified download, `AI/Models/qwen35-9b`): cosine similarity and relative change ||a-b|| / ||b||
(`lineage.py`, `lineage.json`).

- **All 32 transformer layers:** matrix cosine 0.967-0.980 (mean 0.973). **Control:** the same tensor at a different layer
  (down_proj, layer i vs i+7): cosine 0.0000. Two independently trained models sit at the control's value.
- **Embeddings 0.985, output head 0.977** (float64; the float32 pass lost precision on these 1e9-element tensors).
- **Vision tower: identical** (cosine 1.0000 on every tensor).
- **New in SenseNova:** 97 tensors, the two-stream routers (`mhc_attn`, `mhc_ffn`) on layers 4-27 and `loop_gate.logits`.
- **How far it moved:** median relative change of the layer matrices 0.255 (range 0.030-0.440). Recognisably Qwen's
  weights, but moved by a quarter of their own size: large-scale continued training, not a light fine-tune -- which fits
  the knowledge loss and the doubled Wikipedia perplexity in `../RESULT_SENSENOVA_LOOP.md`.

So SenseNova-Loop-9B was initialised from Qwen3.5-9B (layer for layer, text and vision), given the loop and the routers, and
retrained at scale. The comparison in the RESULT is therefore a looped, retrained model against its own base -- but the
loop and the retraining remain confounded; only the loop-count dial on the same weights can separate them.
