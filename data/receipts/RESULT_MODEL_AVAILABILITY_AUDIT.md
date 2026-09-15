# Audit — what the receipts depend on, and what exists in only one place

**Measured 2026-09-15**, control plane + NAS + Games + home. `.194` and `.73` were asleep, so anything
resident only on a node is counted as "not found" below and may well be safe.

**Trigger:** Nvidia's agreement to acquire Hugging Face (reported in The New Stack, early September)
and Mark's concern about model availability — *"Nvidia ownership + uncensored/decensored models."*

## The headline is not the platform risk

**24 of the 29 heavily-cited models (≥ 13 citations in `data/receipts/`) exist as a single copy.
580 GiB with no redundancy.** Only 5 have a second copy on any volume.

**`Qwen3.8-27B-Q6_K.gguf` is cited 204 times — more than any other artifact in the campaign — and
exists in exactly one place.**

**A drive failure is a larger threat to reproducibility than any repository policy change.** A closed
repo costs future downloads; a lost volume costs the ability to reproduce already-published work,
including the Pascal KV finding and the EXL3 campaign that others cite.

## Inventory

| volume | files | size |
|---|---:|---:|
| NAS `/mnt/HDD` | 120 | **1,858.7 GiB** |
| `/mnt/TG_2TB` (`AI/Models`) | 66 | 617.9 GiB |
| Games 2TB | 19 | 201.6 GiB |
| `home` | 86 | 50.9 GiB |

**The NAS already holds a 1.8 TiB model archive.** Memory had recorded it as read-only and "a read
source only" since 2026-08-20; that was wrong on the path, the permission and the conclusion, corrected
2026-09-14 ([[fleet-hardware-topology]]). It has **2.7 TB free** and is the obvious mirror target.

## Single-copy, cited ≥ 13 times

| citations | model | only copy | GiB |
|---:|---|---|---:|
| 204 | `Qwen3.8-27B-Q6_K.gguf` | NAS | 21.3 |
| 152 | `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf` | TG_2TB | 9.7 |
| 81 | `Qwen3.8-27B-UD-IQ4_XS.gguf` | TG_2TB | 13.3 |
| 62 | `Qwen3.6-27B-Q4_K_M.gguf` | NAS | 15.7 |
| 61 | `Qwen3.8-27B-AD-IQ2_S.gguf` | **home** | 10.4 |
| 51 | `Qwen3.6-27B-Q8_0.gguf` | NAS | 27.1 |
| 47 | `…TurboFCFusion-735-882-Here-Uncen-NEO-CODER-MAX-MTP-IQ2_M.gguf` | TG_2TB | 11.3 |
| 41 | `Qwen3.8-27B.i1-IQ3_M.gguf` | TG_2TB | 11.9 |
| 36 | `Qwen3.8-27B-AD-IQ2_XS.gguf` | TG_2TB | 9.2 |
| 33 | `Qwen3.8-27B-UD-IQ3_XXS.gguf` | TG_2TB | 11.1 |
| 32 | `Puzzle-75B-A9B-UD-IQ4-XL.gguf` | NAS | 41.6 |
| 29 | `Qwen3.8-27B-UD-Q4_K_M.gguf` | TG_2TB | 15.3 |
| 27 | `Qwen3.6-27B-Q6_K-MTP.gguf` | NAS | 42.6 |
| 26 | `gemma-4-12B-it-qat-UD-Q4_K_XL.gguf` | NAS | 6.3 |
| 24 | `ThinkingCap-Qwen3.6-27B-Q8_0-MTP.gguf` | NAS | 27.1 |

Redundant already (2+ volumes): `mmproj-F16`, `Qwen3.6-27B-Q4_0-STATIC`, `Ternary-Bonsai-27B-Q2_g64`,
`Qwopus3.6-27B-Coder-heretic-Q6_K`, `Llama-3.2-3B-Instruct-BF16`.

## Not found on mounted storage — incomplete, nodes were asleep

| citations | model | likely |
|---:|---|---|
| 199 | `Qwen3.6-35B-A3B-UD-IQ2_M.gguf` | a node |
| 79 | `Qwen3.8-Flash-Next-UD-IQ4_XS.gguf` | **known on `.194`**, `~/AI/Models/flashnext/` |
| 53 | `crow9b.gguf` | unknown |
| 32 | `Qwen3.8-Flash-Next-UD-Q2_K_XL.gguf` | **known on `.194`**, `flashnext_q2/` |
| 18 | `unsloth-Qwen3.8-27B-Q6_K.gguf` | possibly a naming variant of a held file |
| 13 | `nex-agi_Nex-N2.5-mini-Q4_K_M.gguf` | unknown |

**This section cannot be closed without waking `.194` and `.73`.**

## Repositories the receipts name

`lmstudio-community/Qwen3.6-27B-GGUF` · `bartowski/Qwen3.8-27B-GGUF` · `unsloth/Qwen3.8-27B-GGUF` ·
`unsloth/Qwen3.8-Flash-Next-GGUF` · `Qwen/Qwen3.8-27B` · `Qwen/Qwen3.6-27B` · `Qwen/Qwen3.6-35B-A3B` ·
`ornith-ai/Ornith-1.5-35B-A3B(-GGUF)` · `Jackrong/Qwopus3.5-27B-v3.5-GGUF` · `nex-agi/Nex-N2.5-{mini,Pro,Max}`
(`xet-bridge-us/*` hits are HF's CDN, not repos.)

## Proposed policy

**Anything cited in a published receipt lives on at least two volumes, one of which is the NAS, with its
sha256 recorded.** The hash is not optional: [[davidau-model-filenames]] documents that repo names,
in-repo filenames and `general.name` routinely disagree, and 2026-09-14's dedup pass found two distinct
builds sharing one filename and a rounded size. **A mirror without hashes cannot tell you which build
you saved.**

Cost: **580 GiB** to make the single-copy set redundant, against 2.7 TB free on the NAS. The `home` and
Games residents should move first — neither is a backed-up volume.

## Not done

Waking the nodes to close the six unknowns; hashing the mirror set; deciding whether the `-Uncen-` /
`-heretic-` variants (already present and already cited) warrant priority on the grounds that they are
the category most exposed to a repository policy change.
