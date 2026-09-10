# Dirk-Qwen3.8-27B: same bytes as ISTA, a 3.3x LONGER template — and the hybrid KV geometry

**2026-09-03.** Method: HTTP range requests, first 12 MB of each GGUF, headers parsed with a
standalone reader (`scratchpad/`, same technique as `QWEN38_27B_LAUNCH_CENSUS.md`). No weights
downloaded. Local comparison against `/mnt/TG_2TB/AI/Models/Qwen3.8-27B-UD-Q2_K_XL.gguf`.
Total cost: two 12 MB fetches.

## 1. "Same weights, asked better" — VERIFIED, as far as 12 MB can verify it

`peculiar-ragdoll/Dirk-Qwen3.8-27B-GSQ-RCO-IQ3_XXS.gguf` vs
`ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf`:

| check | result |
|---|---|
| tensor count | 866 = 866 |
| all 866 `(name, shape, type, offset)` tuples | **identical** |
| metadata keys | 53 = 53, no key added or removed |
| 52 of 53 shared values | **identical** (incl. `quantize.imatrix.*`, `general.quantized_by = ISTA DASLab`) |
| `tokenizer.chat_template` | **differs** — the only difference |
| first 983,489 B of tensor data (from each file's own data start) | **byte-identical** |

Dirk is ISTA's `-mtp` file with one metadata string swapped. The `-mtp` suffix is dropped from
the filename but `blk.64.*` is present, so every Dirk GSQ file is an MTP build. File sizes
corroborate across the whole ladder (ISTA `-mtp` → Dirk): 8.77→8.8, 9.61→9.6, 10.4→10.4,
12.1→12.1 GB.

## 2. The template got BIGGER, not smaller

| | chars |
|---|---|
| ISTA / stock | 8,952 |
| Dirk | 29,674 |

**3.31x longer.** The header grew by 20,736 bytes, essentially all of it template. So this is
not "delete the default-effort injection" — it is a full template rewrite that happens to also
drop the injection. Anyone reproducing the *effect* by hand-deleting the `xhigh` block (AFM-23:
237 chars, `medium` injects nothing) is not running the same template Dirk ships.

## 3. Structure census — Qwen3.8-27B is a HYBRID, 16 of 65 layers hold KV

Confirmed independently on **two** files (ISTA header has the `ssm.*` keys; our local Unsloth
UD file has 96 `ssm_alpha`/`ssm_beta` tensors), so it is not a GSQ repackaging artifact.

| field | value |
|---|---|
| `general.architecture` | `qwen35` |
| `block_count` | 65 (64 + 1 MTP) |
| `full_attention_interval` | 4 |
| layers with `attn_q`/`attn_k` | **17** — blk 3, 7, 11 … 63, plus MTP blk 64 |
| layers with `ssm_*` | **48** |
| `head_count` / `head_count_kv` | 24 / 4 |
| `key_length` / `value_length` | 256 / 256 |
| `ssm.state_size` / `ssm.inner_size` / `ssm.group_count` | 128 / 6144 / 16 |
| total params (counted from tensors) | **27,320,697,856** |

**KV cache = 16 x 4 x 256 x 2(K,V) x 2 B = 65,536 B/token = 64 KiB/token at f16**
(68 KiB if the MTP layer takes a cache slot — +6.25%). A dense 64-layer read of the same
metadata gives 256 KiB/token and is wrong by 4x.

This is not new to the project — `RESULT_TCQ_2BIT_RDNA4.md` already names the class
("`q27` order — hybrid, 16/64 KV layers, our exact model class"). It was never written down
as a census. It is now.

**Hazard worth flagging:** `qwen35` covers both a dense and a hybrid model, distinguished only
by the presence of `ssm_*` fields. Given yesterday's tensor-split deny-list work, a hybrid arch
that is *not* on the deny list is a thing to watch.

## 4. Both quantizers independently refuse to quantize the same two tensor families

| tensor | Unsloth UD-Q2_K_XL | ISTA GSQ-RCO IQ3_XXS |
|---|---|---|
| `ssm_alpha` / `ssm_beta` (96 x [5120, 48]) | **Q8_0** (all 96) | **BF16** (all 96) |
| MTP layer `blk.64.*` (8 weight matrices) | **Q6_K** / Q8_0 | **Q6_K** (all 8) |
| body | down to IQ1_M | down to IQ1_S / IQ1_M |

Two unrelated pipelines, same two exclusions. `ssm_alpha`/`ssm_beta` are 23.6M params total —
0.09% of the model — so protecting them costs ~47 MB at BF16.

**MTP survives at 3 bpw.** That is the answer to whether speculative decoding is still worth
turning on down there: the draft head is Q6_K in both families.

## 5. …and Bonsai's ternary run (on Qwen3.6) took them down anyway

`Ternary-Bonsai-27B-Q2_g64` (CHANGELOG 2026-07-17): arch `qwen35`, **all 498 weight tensors
Q2_0, F32 norms only**. **Its base is Qwen3.6-27B, not 3.8** (Mark, 2026-09-03; corroborated by
`RESULT_TCQ_2BIT_RDNA4.md`: "the `q27` order — Qwen3.6-27B, hybrid, 16/64 KV layers"). Qwen3.6-27B
carries the *same hybrid layout* as §3 but no MTP layer, and the tensor inventory closes exactly
on that reading:

```
48 SSM layers   x 8 quantizable (attn_gate, attn_qkv, ffn_{down,gate,up},
                                 ssm_alpha, ssm_beta, ssm_out)   = 384
16 attn layers  x 7 quantizable (attn_{k,q,v,output}, ffn_{down,gate,up}) = 112
token_embd + output                                              =   2
                                                                   ---
                                                                   498
```

Exactly 498 — i.e. Qwen3.6-27B is the same 48-SSM / 16-attention hybrid as Qwen3.8-27B, minus
the MTP layer. Independently corroborated by our own VRAM measurement: that receipt records
**~12.6 GB total-system at 32k ctx** with 7.06 GiB of weights. At 64 KiB/token (hybrid) the
KV is 2.0 GiB and the numbers close; at 256 KiB/token (dense) the KV alone is 8.0 GiB and
weights+KV would be 16.2 GB — impossible on the card it ran on.

So the §4 convergence is **not** "these tensors cannot be quantized." It is "post-training
rounding won't touch them." A ternary model with them trained in ran at 46.5 t/s and won the
Battle for 16GB agentic leg 15/20 vs Gemma-4-12B QAT's 14/20.

## 6. What actually fits on a 16 GiB RX 9070 XT

**Blocker first, and it is measured, not arithmetic:** `RESULT_TCQ_2BIT_RDNA4.md` —
**8 of 8 turbo KV configurations collapse generation on this model class on gfx1201**, one
turbo tensor anywhere in the cache is sufficient, bit depth irrelevant. The CLAUDE.md
`-ctk q8_0 -ctv turbo3` recipe **does not apply to this model**. Clean tiers on gfx1201 for
this class: `f16` 10/10, `q8_0` 9/10, `q4_0` 9/10.

Overhead anchored on the Bonsai measurement above (desktop + compute + SSM state ~2.67 GiB),
leaving ~13.33 GiB for weights + KV. **Everything below is arithmetic, not a load test.**

| Dirk file | GB | bpw | GiB | spare | ctx @ f16 (64 KiB/tok) | ctx @ q8_0 (34 KiB/tok) |
|---|---|---|---|---|---|---|
| GSQ-RCO IQ2_XS | 8.8 | 2.58 | 8.19 | 5.14 | ~84k | ~158k |
| GSQ-RCO IQ2_S | 9.6 | 2.81 | 8.94 | 4.39 | ~72k | ~135k |
| UD-Q2_K_XL | 9.8 | 2.87 | 9.13 | 4.20 | ~69k | ~129k |
| **GSQ-RCO IQ3_XXS** | **10.4** | **3.05** | **9.69** | **3.64** | **~60k** | **~112k** |
| GSQ-RCO IQ3_S | 12.1 | 3.54 | 11.27 | 2.06 | ~34k | ~63k |
| UD-Q3_K_XL | 13.1 | 3.84 | 12.20 | 1.13 | ~18k | ~35k |
| UD-IQ4_XS | 14.3 | 4.19 | 13.32 | 0.01 | — | — |

IQ4_XS is out on 16 GiB without offload. The one thing that makes any of this real is a single
load with `rocm-smi` before and after.

**Correction to a claim I nearly made:** the repo does *not* split cleanly at 3 bpw —
`Dirk-Qwen3.8-27B-UD-Q2_K_XL` (9.8 GB, 2.87 bpw) sits inside the GSQ band. GSQ-RCO is offered
as an *alternative* across 2.58–3.54 bpw with one UD option in the same range, then UD only
above 3.84.

## Open / next

- Which family is actually better at matched bytes — GSQ-RCO IQ3_XXS (10.4 GB) vs UD-Q2_K_XL
  (9.8 GB) — is unmeasured. A KLD rung is the discriminator; both files are ~10 GB.
- ~~Hypothesis: the discriminator is the hybrid SSM structure, not the GQA ratio.~~
  **FALSIFIED the same day, twice — see `../kv-tensor-split/RESULT_TURBO_FA_GQA_SWEEP.md`
  (2026-09-03).** First: Qwen3.5-9B, the receipt's own *clean* control, is
  `full_attention_interval = 4` as well, so both the clean and the collapsing model are
  hybrids. Second: a patched `test-backend-ops` cleared every turbo codec at hsk=256 across
  GQA 1/2/4/6/8 on gfx1201, so neither the hybrid structure nor the GQA ratio nor the head
  size produces wrong numbers out of the attention kernel. The fault is not in flash
  attention at all.
