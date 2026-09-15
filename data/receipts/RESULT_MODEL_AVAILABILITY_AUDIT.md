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

## UPDATE 2026-09-15, nodes surveyed — three cited builds are permanently unrecoverable

`.194` (390 files, 457.4 GiB) and `.73` (480 files, 297.7 GiB) were woken and surveyed. Four of the six
unknowns resolved to nodes. **Three cited models exist nowhere on the fleet, and cannot be re-downloaded
as the same build.** No platform policy change was involved — this is ordinary repository churn.

| model | GiB | cited in | what happened upstream |
|---|---:|---|---|
| `Qwen3.6-35B-A3B-UD-IQ2_M.gguf` | 11.07 | **6+ receipts** incl. `MTP_DETERMINISM`, `MTP_CACHEPROMPT_FALSIFICATION`, HA20 controls | `unsloth/Qwen3.6-35B-A3B-GGUF` still lists that exact filename — at **11,522,702,304 bytes** against our recorded **11,882,969,376**. **Re-quantized and overwritten in place.** |
| `Qwopus3.5-27B-v3-Q2_K.gguf` | 9.98 | **5 receipts** incl. `hermesagent20/KV_QUANT_GENERATION_EFFECT`, `FORK_CODEC_SHOOTOUT`, the RDNA4 bundle | `Jackrong/Qwopus3.5-27B-v3-GGUF` **no longer ships a Q2_K** — its smallest is Q3_K_M at 13.3 GB |
| `Ornith-1.0-35B-UD-IQ2_M.gguf` | 10.77 | `PREDICTIONS_ha20_ornith.md` | `ornith-ai/Ornith-1.0-35B-A3B` returns *"Invalid username or password"* — **gated or deleted**. Only Ornith-1.5 is public, with no IQ2_M |

**This is the concrete version of the platform-risk worry, and it already happened.** Not a hypothetical
about who owns Hugging Face — three upstream repos changed in three ordinary ways (re-quantize, prune a
quant, take a repo down) and three published receipts lost the ability to be independently reproduced.
The results remain valid; nobody, including Mark, can re-obtain the artifact to check them.

**Both re-quantized cases are `gguf-label-is-not-a-spec` in the wild**: identical filename, identical
label, different bytes. Only the recorded size and fingerprint caught it. **A mirror that stores files
without fingerprints would have silently "restored" the wrong build** and nobody would have known.

Two of the three are also `davidau-model-filenames` cases from the other direction — `Ornith-1.0-35B`'s
`general.name` is **"Ornith-1.0-9B"** and `Qwopus3.5-27B-v3-Q2_K`'s is a bare git SHA
(`7cc05e59a4da512149a723c4f58aeaa028445e18`). The filename identifies neither.

### Provenance file is stale as a locator

Of 24 `MODEL_PROVENANCE.json` entries: **1 at its recorded path**, 16 found elsewhere, 7 gone. The
fingerprints still identify correctly — that design works — but the paths have almost entirely drifted.
**It also records no source repo**, which is why recovering the three above required guessing at repo
names and querying HF by exact byte size. **A `source` field would have made this a lookup instead of an
investigation**, and should be added on the re-scan.

### Node inventory

| location | files | GiB |
|---|---:|---:|
| NAS `/mnt/HDD` | 120 | 1,858.7 |
| `/mnt/TG_2TB` | 66 | 617.9 |
| `.194` | 390 | 457.4 |
| `.73` | 480 | 297.7 |
| Games 2TB | 19 | 201.6 |
| `home` | 86 | 50.9 |

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
