# REAP-320 Q2 is a pure byte-copy prune of the UD-Q2_K_XL on .194

**2026-09-23**, `.194`. Scripts: `verify_reap_parent.py`, `verify_router.py` (run on .194 with buun's gguf-py).

Checked `AnonimousA/Qwen3.8-Flash-Next-REAP-320-GGUF` `Q2/` (sha256 `f9bde75d...c8fbfb`,
`27e944ca...a47b57`, both matching upstream LFS oids) against the unpruned Unsloth
`Qwen3.8-Flash-Next-UD-Q2_K_XL` already at `~/AI/Models/flashnext_q2/`, using the shipped manifest
`manifests/seleccion_mass_K320.json` (512 -> 320 experts per layer, 48 MoE layers).

| check | result |
|---|---|
| kept experts (4 per expert tensor: first, second, middle, last) vs the parent expert the manifest names | **576 / 576 byte-identical** |
| non-expert tensors (full hash; head+tail 16 MiB for tensors > 64 MiB) | **1,032 / 1,032 identical** |
| router `ffn_gate_inp` (48) | differ in shape, as they must; **48 / 48 are the exact parent rows for the kept experts** |
| tensors in the pruned file absent from the parent | 0 |

**So the local pair (UD-Q2_K_XL, REAP-320 Q2) differs ONLY by expert deletion**: same bits, same
router weights for surviving experts, and no requantization, recalibration or router rescaling. That
makes it an exact-parent A/B for any prune-cost experiment. It also confirms this local UD-Q2_K_XL is
the same Unsloth revision the author pruned from.

Limits: experts were sampled (4 of 320 per tensor, all 48 layers x each expert tensor), not
exhaustively hashed. Large dense tensors were compared on head and tail slices.
