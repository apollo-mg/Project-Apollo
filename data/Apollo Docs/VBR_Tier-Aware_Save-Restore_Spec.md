# Tier-Aware Save/Restore for VBR — Design Spec (Sidecar v2)

**For:** buun (spiritbuun/buun-llama-cpp), invited 2026-07-10 ("take a stab at store/restore with VBR").
**From:** Mark (apollo-mg), building on the checkpoint-sidecar patch already shipped to
llama-cpp-turboquant (PR #206 lineage; ~720× restore-vs-reprefill at 100K, receipts in
scripts/experiments/). Design drafted with Claude; Mark owns the implementation.

## 1. Problem

VBR dynamic mode disables slot/session save-restore (README: "they would snapshot tier-typed KV
that can't restore across a degrade — tier-aware save-restore is planned"). Decomposed, four
distinct breaks:

1. **Serializer assumes uniform types.** `llama_state_seq_save_file` treats KV as one type per
   layer for the whole session. VBR KV is per-(layer, side) tier-typed and the map MUTATES at
   degrade events. A snapshot without the tier map is undecodable.
2. **Restore into a mismatched tier map.** The restoring session's budget/degrade state need not
   match the saved one — buffer types and sizes differ per tensor.
3. **Hybrid checkpoints aren't in state files at all.** (Our original llama-cpp-turboquant finding:
   context checkpoints skipped by the serializer → post-restore BPE rollback finds nothing →
   "forcing full prompt re-processing" invalidation. Assumed inherited here — verify on this fork.)
4. **Restore triggers tail rollback** (BPE re-tokenization of the tip) that must be *served* by
   checkpoints. Lesson from our v1: tip-only synthesis is NOT sufficient rollback coverage; real
   persisted checkpoints are required.

## 2. Design principles

- **The tier map is data, not config.** Serialize it per (layer, side); the snapshot is
  self-describing.
- **Tiers only ever degrade.** Restore never upgrades a tensor (the information is already gone).
  If the target session has less budget than the snapshot needs: adopt the saved map, then fire the
  EXISTING degrade machinery until it fits. VBR's core op is reused as the restore-fit op — no new
  quantization path.
- **Codec names, not enum indices.** "New codecs roll straight into VBR" ⇒ tier tags are strings
  (`"turbo3_tcq"`), and an unknown name on restore = clean refusal + full-re-prefill fallback
  (never crash, never garbage — same graceful-fallback contract our no-sidecar test proved).
- **Server-level sidecar first** (mirrors our +117-line server-context.cpp patch), core
  `llama_state` integration as v2 once semantics are agreed.

## 3. Sidecar format (v2)

```
header:   magic, format_version, build sha, model hash, n_tokens, unified_kv flag,
          price_order id (baked per-model vs generic — record WHICH was active)
kv:       per (layer, side): { tier_name, n_bytes, raw quantized blocks }
vbr:      controller state { budget bytes, degrade step counter }
ckpt:     context checkpoints array (recurrent/SSM state; on qwen35-class hybrids these are
          context-INDEPENDENT ~149.6 MiB blobs — cheap to persist, our v1 payload verbatim)
tail:     token stream tail sufficient to serve BPE rollback
```

## 4. Restore algorithm

1. Validate header: model hash, codec-table compatibility (every tier_name known), format version.
   Any mismatch → log + graceful full re-prefill. Never partial-restore.
2. Budget check. If current KV budget ≥ snapshot bytes: adopt saved tier map verbatim; write blocks
   into the VMM-backed pools. **Explicitly map pages for the restored range before memcpy** — the
   pools grow on demand for decode, but restore is a bulk landing, not a fault-driven trickle.
3. Else: adopt, then run degrade steps down the snapshot's price order until fit — each step logged
   with the existing `VBR degrade #` telemetry so the restore is auditable.
4. Reload checkpoints from sidecar (port of our existing patch).
5. Tail rollback proceeds served by checkpoints — acceptance = zero invalidation warnings.

## 5. Scope for v1

- `-np 1`, single sequence (dynamic VBR forces unified KV at `-np > 1`; multi-slot restore
  semantics deferred deliberately — our dual-slot investigation found pre-existing sharp edges even
  without VBR).
- Same build, same model, CUDA first (the VMM machinery is the load-bearing dependency).
- Cross-GPU-count restore (saved on 2 devices, restored on 4) SHOULD work — the tier map is
  per-layer, device placement is orthogonal — but is a test case, not a promise.

## 6. Known hazards (each with its mitigation)

| hazard | mitigation |
|---|---|
| save races an in-flight degrade | take the snapshot under the same lock degrades hold; quiesce slot first |
| VMM pages unmapped at restore write | explicit map of the full restored extent before memcpy (step 4.2) |
| CUDA-graph capture invalidated by instant n_kv jump | existing per-node src-ne memcmp forces re-capture; restore lands in an eager pass by construction |
| FA f16 dequant scratch sized for tiny attended width | existing `kv_dequant_scratch()` maps to exact attended width on first post-restore pass |
| codec table drift across builds | string tier tags + header build sha; unknown tag = clean fallback |
| double-lossy quality on degrade-at-restore | measured, not assumed — see §7.4 |

## 7. Validation plan (receipts, all from methodology we've already run)

1. **Bit-exactness (the strong claim):** same-budget save→restore, then compare next-64-token
   logits against an uninterrupted control session. Target: byte-identical (restore is invisible).
2. **Canary at 95% depth intact at 100K** (slot_benchmark.py pattern), zero invalidation warnings.
3. **Timing:** restore vs full re-prefill at 100K (Tom-fork sidecar precedent: 1.0s vs 720.1s
   same-build A/B; VBR adds requant cost only on the degrade-at-restore path).
4. **Degrade-at-restore priced:** KLD panel (median + l64) on restored-then-degraded cache vs a
   natively-degraded control at the same final tier map. Double-lossy vs single-lossy is THE
   honest cost number for this feature; publish it either way.
5. **No-sidecar fallback:** graceful full re-prefill, correct output, no crash (proven test).
6. **Live multi-turn regression** (existing script): reuse unregressed, park-and-resume with
   divergent continuation, no stray sidecar files.

## 8. What we bring (prior receipts)

- Shipped sidecar on llama-cpp-turboquant: 807ms/15-token delta vs 7,704ms full re-prefill (small);
  1.0s vs 720.1s at 100K (same-build A/B — the sidecar is the entire effect); canary intact; log
  receipt "restored 2 context checkpoints from sidecar".
- Hybrid checkpoint context-independence (2×149.6MiB at 1K and 100K alike) ⇒ no persist-cap needed
  on qwen35-class models.
- Failure library: tip-only synthesis insufficient (v1), dual-slot cache drop pre-existing on
  hybrid `-np 2 --kv-unified`, think-stripping templates force per-turn rollback that checkpoints
  serve (~250 tok/turn on thinking models) — the last one means VBR+sidecar directly improves
  agent-loop latency, not just park-and-resume.

## 9. Open questions for buun (design veto requested before code)

1. Degrade internals: does a degrade step requant from the f16 dequant scratch or
   dequant→requant per block? (Determines whether restore-fit can reuse it verbatim.)
2. Price-order provenance: is the baked per-model order stamped anywhere at runtime we can read,
   or should the sidecar carry the order table itself?
3. t8:t4 asymmetric tiers: per-(layer,side) tags cover it — any other split-K/V states to encode?
4. Preference: keep this at server layer (fast, contained) or land it in `llama_state_*`
   properly from the start?
5. Restore-across-budget semantics: is adopt-then-degrade the behavior you want, or should a
   smaller-budget restore refuse instead? (We prefer degrade — auditable and it always resumes.)

## 10. Sequencing

VBR Pascal validation (protocol doc, Phase A/B) completes first — its receipts calibrate the
instruments this spec's §7.4 needs. Then: branch on buun's fork, implement v1 scope, run §7,
hand buun the receipts with the PR.
