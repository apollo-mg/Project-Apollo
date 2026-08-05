# Audit of every public GGUF TurboQuant weight file on HuggingFace — without downloading any of them

**2026-08-03.** Method: HTTP range request for the head of each file, then derive **actual on-disk
bytes-per-block** from consecutive tensor offsets. Tool: `~/scratchpad/hf_tq_probe.py`.

## Why a no-download audit is possible

GGUF places all metadata — KVs plus the complete tensor-info block (name, dims, **type**, offset per
tensor) — at the head of the file. A `Range: bytes=0-16777215` request therefore yields every
tensor's declared type and offset. Consecutive offsets give the real bytes-per-block, which reveals
the true format **regardless of what the declared id claims**. Cost: 4–48 MB per file instead of
5–25 GB, seconds instead of hours.

This matters because of the enum drift documented in `TQ_ENUM_DRIFT_INTEROP.md`: TheTom's fork had
`TQ4_1S = 45` during 2026-04-01..04-03 and `TQ4_1S = 46` since. A file from the drift window is read
as `TQ3_1S` (16 B/block) when its payload is `TQ4_1S` (20 B/block), so current builds compute wrong
offsets and abort with `failed to read tensor data` — indistinguishable, to a user, from a corrupt
download.

## Results — the entire public GGUF TQ corpus

| repo | model | declared id | measured B/32 | TQ tensors | verdict |
|---|---|---|---|---|---|
| `MarcelloG/Qwen3.6-35B-A3B-GGUF-TQ4_1S` | 35B-A3B MoE | **45** | **20.000** | 108 | ❌ **DRIFT — will not load** |
| `ShinkaLabs/Qwopus3.5-9B-v3-TQ-Compress-TQ4_1s` | 9B | **45** | **20.000** | 84 | ❌ **DRIFT — will not load** |
| `bandtor/Qwen3.6-35B-A3B-TQ4_1S-GGUF` | 35B-A3B MoE | 46 | 20.000 | **442** | ✅ OK |
| `MidnightPhreaker/Qwen3.6-27B-MTP-TQ4_1S-GGUF` | 27B dense + MTP | 46 | 20.000 | 180 | ✅ OK |
| `yosoyalguien/gemma-4-E4B-it-GGUF-TQ4_1S` | 8B | 46 | 20.000 | 377 | ✅ OK |
| `yosoyalguien/gemma-4-E2B-it-GGUF-TQ4_1S` | 5B | 46 | 20.000 | 314 | ✅ OK |
| `yosoyalguien/Qwen3.5-9B-GGUF-TQ4_1S` | 9B | 46 | 20.000 | 249 | ✅ OK |
| `yosoyalguien/Meta-Llama-3.1-8B-Instruct-GGUF-TQ4_1S` | 8B | 46 | 20.000 | 224 | ✅ OK |
| `grevinden/Qwen3-Embedding-4B-TQ4_1S-GGUF` | 4B embedding | 46 | 20.000 | 251 | ✅ OK |
| `bandtor/Qwen3.6-27B-TQ4_1S-GGUF` | — | — | — | — | ⚠️ **empty — no .gguf files** |
| `bearcove/*` (4 repos) | ASR / aligner | — | — | — | n/a — **no .gguf files**; `tq6_1s` is not a llama.cpp type |
| `tQ44rm53/aertgfg`, `caleancalean1/tq4gaYuT` | — | — | — | — | noise (name-match artefacts) |

**Every TQ tensor in every readable file measures exactly 20.000 B / 32 values (5.00 bpw).** The
payload format is identical across the corpus; only the declared id differs.

## The drift correlates perfectly with upload date

| uploaded | files | id |
|---|---|---|
| Apr 5, Apr 20 | ShinkaLabs, MarcelloG | **45 (broken)** |
| May 31 → Jul | bandtor, MidnightPhreaker, yosoyalguien ×4, grevinden | 46 (correct) |

Both broken files are from April; everything from May onward is correct. Consistent with quantizing
against a fork checkout from the `TQ4_1S = 45` window.

## Practical consequences

1. **Two of the nine public TQ files are unloadable on any current build**, and both fail in a way
   that reads as a corrupt download. Each is repairable by a metadata-only edit — 4 bytes per TQ
   tensor, no weight byte touched (`TQ_ENUM_DRIFT_RECOVERY.md`; verified on MarcelloG's file, which
   then generated factually correct text).
2. **`bandtor/Qwen3.6-35B-A3B-TQ4_1S-GGUF` is the better MoE.** Correct id *and* **442 TQ tensors
   versus MarcelloG's 108** — a genuinely TQ-throughout quantization rather than mostly Q8_0/Q4_K
   with a TQ subset. It is the right file for any MoE TQ benchmark, and needs no patching.
   (MarcelloG's `Q8_K_XL` build is 21.89 GiB largely *because* its non-expert tensors are Q8_0.)
3. **The corpus is small and Qwen-heavy.** Nine usable files, no Mixtral/Llama-70B class, one
   embedding model. TQ4_1S is the only weight type present — **no public `TQ3_1S` file exists**,
   which is why the `c29f0d1cd` fused-TQ3_1S bug could not be tested against a real model here.
4. **The search-visibility theory checks out, but the hidden population is MLX, not GGUF.** Name
   search for `TQ4_1S` returns 13; searching `turboquant` returns 50+, but the extra hits are almost
   entirely **MLX** quants (Apple-side TurboQuant implementations — `majentik`, `ianleelamb`,
   `alexcovo`, `Jonatan-1987-xtv`, `lew96123`…), plus one binaries repo. So the TurboQuant
   *ecosystem* is much larger than the llama.cpp GGUF *corpus*, and the GGUF corpus really is ~9
   files.

## Reusable check

```bash
python3 hf_tq_probe.py <repo-id> [more...]
```

Reads only the file head over HTTP. Flags any tensor whose measured bytes-per-block disagrees with
its declared type, and names the enum-drift case explicitly. Validated against ground truth: its
remote reading of MidnightPhreaker (id 46, 180 tensors) and MarcelloG (id 45, 108 tensors, drift)
matches byte-for-byte what local inspection of the downloaded files produced.
