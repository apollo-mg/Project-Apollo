# C3 — upstream does not collapse. The bug is fork-side.

**2026-08-17**, `.73`, dual Tesla P100 (sm_60).
Binary **`ggml-org/llama.cpp` `34af94c`** ("ci : push release tag explicitly", 2026-08-17 —
that day's master), built `-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=60`, at
`~/llama_upstream`. Raw `~/xfork_upstream/`, log `~/kv_upstream.log`, script `kv_upstream.sh`.

**This is the first genuine upstream binary on this fleet for the whole campaign.**

## It is really upstream — checked, not assumed

`INDEX.md` has warned all along that `~/llama_stock_ref` is **not** stock despite its
`ggml-org` remote (it sits on `adeff9b82`, a *laguna* commit). So this build was verified
before use: its `--cache-type-k` list is `f32, f16, bf16, q8_0, q4_0, q4_1, iq4_nl, q5_0,
q5_1` — **no turbo types**. A turboquant-derived tree always offers `turbo2/3/4`. The absence
is the proof.

## Result — every arm clean

| arm | model | K | V | upstream `34af94c` |
|---|---|---|---|---|
| U_A | Qwen3.5-4B-BF16 (D=256) | f16 | f16 | **clean 3/3** |
| U_B | Qwen3.5-4B-BF16 | `q8_0` | `q8_0` | **clean 3/3** |
| U_C | Qwen3.5-4B-BF16 | `q4_0` | `q4_0` | **clean 3/3** |
| U_D | Qwen3.8-27B-Q6_K (D=256) | f16 | f16 | **clean 3/3** |
| U_E | **Qwen3.8-27B-Q6_K** | **`q8_0`** | **`q8_0`** | **clean 3/3** |

> **CORRECTION 2026-08-17, same day.** U_B and U_C are **not** evidence for the headline.
> The gap-closer (`kv_final.sh` M2) showed the **fork is also clean** on the 4B under *layer*
> split — the 4B collapses only under **tensor** split (`kv_4b.sh` Q2). So U_B vs Q2 compared
> two different split modes and there was no contrast to observe. The valid 4B comparison is
> upstream-at-tensor (S2) against fork-at-tensor (Q2).
>
> **The headline survives on U_E alone**, which is a genuine matched comparison (below).
> Corrected on discovery rather than left standing.
>
> This also qualifies a claim in `RESULT_XFORK2.md` and `RESULT_D128.md`: "the collapse is
> split-independent" holds for the **27B** (T9 and F2 both collapse under layer) but **not**
> for the 4B, which is clean under layer and collapses under tensor. Split-independence is
> model-dependent, not universal.

**U_E is the decisive arm.** Same model, same node, same layer split, same KV types, same
`-fa on` — **only the binary differs**:

| binary | `q8_0` K+V, Qwen3.8-27B, layer split, sm_60 |
|---|---|
| TheTom `f6124e9` | **collapse 3/3** (`RESULT_XFORK.md` T9) |
| TheTom `f6124e9` | **collapse 3/3** (`RESULT_FA_AND_GRID.md` F2, replicated) |
| **upstream `34af94c`** | **clean 3/3** |

Nothing else varies. The collapse is **not** inherited from current upstream.

## Prediction, scored

**Predicted upstream COLLAPSES at 0.65** (warrant: the mechanism sits in `fattn.cu`, which is
upstream-origin code, and two independently-maintained forks reproduce it byte-identically).
**FALSIFIED.** The falsification is the more useful outcome: a fork-side regression has an
identifiable commit, an upstream-wide bug does not.

## Where the forks actually diverge

| file | upstream | TheTom | buun |
|---|---|---|---|
| `ggml-backend-meta.cpp` | 107,082 B | 107,067 B | ~ same |
| `fattn.cu` | **589 lines** | **846** | **2528** |

Two hypotheses died in the space of ten minutes here, both worth recording:

1. **"`ggml-backend-meta.cpp` is a shared fork addition, which is why upstream is clean."**
   Wrong — the file **is upstream code**, near-byte-identical across all three trees, and
   upstream even carries the `SPLIT_AXIS_UNKNOWN` assert (lines 527/532 against Tom's 535 and
   buun's 533).
2. **"Upstream has no `-sm tensor`, so the abort can't be tested there."** Wrong — upstream
   offers `{none,layer,row,tensor}`. That assumption would have left half the comparison
   permanently unmade; `kv_final.sh` corrects it.

What actually differs is **`fattn.cu`**, and only there: both forks *extend* it — Tom by ~257
lines, buun by ~1900 — which is where turbo KV codec dispatch is added, and where the
D=256 dispatch table and the `turing_mma_available() || amd_wmma_available()` gate live.

**Working hypothesis, not established:** adding turbo codec dispatch broke the *stock*
quantized D=256 path on hardware lacking MMA/WMMA — in both forks, because both solve the
same problem in the same file. It is consistent with every measurement so far (both forks
collapse; upstream with the small `fattn.cu` does not; RDNA4 with WMMA does not), but **no
commit has been isolated**, and `AFM-17` applies: this is a structural reading, not an
execution trace.

## Why this is the good outcome

A fork-side regression is *actionable in a way an upstream bug is not*. It means there exists
a diff between "works" and "doesn't", and a bisect can name it — turning the report from
*"your fork corrupts output on Pascal"* into *"this specific change did it"*. That is the
best possible shape to hand two maintainers who both have to fix it.

It also removes the routing problem: this no longer needs to go to `ggml-org` at all.

## Next, and it is the highest-value thread open

**`BACKLOG U1`: bisect for the commit.** Note `~/llama_upstream` was cloned `--depth 1`, so a
bisect needs a full clone first. Bound the range with each fork's merge-base (`U3`), use the
4B `q8_0` arm as the test — it is small, loads fast, and collapses reliably on the fork.

## What this does NOT establish

- **One upstream commit.** `34af94c` is today's master. Whether upstream *ever* had this — and
  was fixed after the forks branched — is exactly what the bisect answers. "Upstream is clean
  today" is not "upstream was always clean."
- **Not the abort.** Every upstream arm above ran **layer** split. The abort requires
  `-sm tensor` (`RESULT_XFORK2.md`), and upstream does support it, so this is a real gap and
  not a structural one — `kv_final.sh` S1–S5 close it.
- **Not a fidelity claim.** "Clean" is not-degenerate, not verified quality.
