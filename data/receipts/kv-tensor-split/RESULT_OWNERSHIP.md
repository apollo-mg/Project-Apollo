# The two KV bugs have different owners — one is fork-side, one is upstream

**2026-08-17**, `.73`, dual Tesla P100 (sm_60). Capstone for the day's KV work.
Raw `~/xfork_final/`, log `~/kv_final.log`, script `kv_final.sh`.

Binaries: **upstream `ggml-org/llama.cpp` `34af94c`**, **TheTom `f6124e9`**,
**buun `a8e5b5a38`** — all on the same node, same GPUs, same models, same detector.

## The answer

| | upstream `34af94c` | TheTom `f6124e9` | buun `a8e5b5a38` | **owner** |
|---|---|---|---|---|
| **Bug A — silent collapse** (`q8_0`/`q4_0` symmetric, D=256) | **clean** | **collapse** | **collapse** | **the forks** |
| **Bug B — hard abort** (`SPLIT_AXIS_UNKNOWN`, `-sm tensor`) | **ABORTS** | aborts | aborts | **upstream** |

Two bugs, two different owners. That is the clean answer the whole day was chasing, and it
was only obtainable once a genuine upstream binary existed (**C3**) — which is why the
absence of one had been blocking so much.

## Bug A is fork-side

**The decisive arm is U_E**: Qwen3.8-27B-Q6_K, `q8_0` K+V, **layer** split, sm_60 — same
model, same node, same split mode, same codec, `-fa on` on both. **Only the binary differs.**

| binary | result |
|---|---|
| TheTom `f6124e9` | **collapse 3/3** (`RESULT_XFORK.md` T9) |
| TheTom `f6124e9` | **collapse 3/3** (`RESULT_FA_AND_GRID.md` F2, independent replication) |
| **upstream `34af94c`** | **clean 3/3** (U_E) |

Confirmed independently on the 4B under **tensor** split, matched after the split-mode error
below was caught:

| binary | Qwen3.5-4B-BF16, `q8_0` K+V, **tensor** split |
|---|---|
| TheTom `f6124e9` | **collapse 3/3** (`kv_4b.sh` Q2) |
| **upstream `34af94c`** | **clean 3/3** (S2) |

Two models, two split modes, both directions matched. Bug A does not exist in upstream.

## Bug B is upstream

```
/home/mark/llama_upstream/ggml/src/ggml-backend-meta.cpp:537:
GGML_ASSERT(ret.axis != GGML_BACKEND_SPLIT_AXIS_UNKNOWN) failed
```

| arm | K | V | upstream |
|---|---|---|---|
| S3 | `q8_0` | `q4_0` | **HARD ABORT `:537`** |
| S4 | `iq4_nl` | `iq4_nl` | **HARD ABORT `:537`** |
| S5 | `q5_1` | `q5_1` | **HARD ABORT `:537`** |

All three verified genuine — 63-line logs, zero bind failures, real asserts. S1 (f16 control,
tensor split) is **clean 3/3**, so upstream's tensor split works; only these KV type
combinations kill it.

Line numbers across the three trees — upstream **537**, Tom **535**, buun **533** — in a file
that is near-byte-identical everywhere (upstream 107,082 B vs Tom 107,067 B). **The forks
inherited this one unchanged.** An earlier hypothesis that `ggml-backend-meta.cpp` was a
shared *fork addition* is dead: it is upstream code.

**Practical impact:** on stock `llama.cpp`, `-sm tensor` plus certain quantized KV pairs is an
immediate hard abort on multi-GPU. Not a fork problem, not sm_60-specific as far as this
evidence goes.

## Where Bug A came from

`fattn.cu` is the only file that meaningfully diverges:

| | `fattn.cu` | `ggml-backend-meta.cpp` |
|---|---|---|
| upstream | **589 lines** | 107,082 B |
| TheTom | 846 (+257) | 107,067 B |
| buun | 2528 (+1939) | ~same |

Both forks *extend* `fattn.cu` — that is where turbo KV codec dispatch is added, and where
the D=256 dispatch table and the `turing_mma_available() || amd_wmma_available()` gate live.

**Hypothesis, not established:** adding turbo dispatch broke the *stock* quantized D=256 path
on hardware lacking MMA/WMMA — in both forks, because both solve the same problem in the same
file. Consistent with everything measured (both forks collapse; upstream's small `fattn.cu`
does not; RDNA4 *with* WMMA does not) but **no commit is isolated**. `AFM-17` applies.

`BACKLOG U1` — bisect for the commit — is the remaining high-value thread, and would turn
this from *"your fork corrupts output on Pascal"* into *"this change did it"*.

## An error this run caught, and why the run existed

The upstream comparison was initially run at **layer** split because I assumed upstream had
no `-sm tensor`. It does (`{none,layer,row,tensor}`). Worse, the gap-closer showed the **fork
is also clean** on the 4B under layer split — the 4B collapses only under *tensor*. So U_B vs
Q2 had compared two different split modes and observed a contrast that was never there.

The headline survived because **U_E** was a genuine matched comparison. But two receipts
needed correcting on the spot:

- `RESULT_UPSTREAM.md` — U_B/U_C withdrawn as evidence; S2 substituted.
- `RESULT_XFORK2.md` — *"the collapse is split-independent"* qualified: true of the **27B**,
  **false** of the 4B. **Split-independence is model-dependent, not a property of the bug.**

**Every cross-binary comparison must match split mode explicitly.** One did not, and it took a
control arm to notice.

## Prediction scorecard for the day

| # | prediction | conf | outcome |
|---|---|---|---|
| X1 | Bug A clean on Tom's fork | 0.80 | **FALSIFIED** |
| X2 | `q4_0` clean on Tom's fork | 0.75 | **FALSIFIED** |
| X3 | Bug B reproduces on mixed f16/quantized | 0.70 | **FALSIFIED** |
| X4 | `q8_0`+turbo4 clean | 0.90 | correct |
| X5 | turbo3 sym shows visible damage | 0.60 | **WRONG** — aborted |
| X6 | guard-on clean + upgrade logged | 0.85 | correct |
| X7 | f16 control clean | 0.97 | correct |
| — | T5 (`q8_0` V alone) collapses | 0.75 | **FALSIFIED** — needs both |
| — | U4 (`q8_0`+`q4_0`) collapses | 0.60 | **FALSIFIED** — aborts |
| — | L1 clean at D=128 | — | **correct** |
| — | R1 clean on RDNA4 | 0.65 | **correct** |
| — | upstream collapses | 0.65 | **FALSIFIED** |

**4 of 12.** The correct calls cluster in two groups: high-confidence "nothing happens"
predictions (0.97, 0.90, 0.85), and the two backed by a **runtime capability gate or
deployment reality** (L1, R1). Every call warranted by *reading source structure* was wrong.
That distinction is now `AFM-17`, and it earned its place.

## What is still open

- **`U1` — bisect for the Bug A commit.** `~/llama_upstream` is `--depth 1`; a bisect needs a
  full clone. Bound with each fork's merge-base, test with the 4B `q8_0` tensor-split arm.
- **Is Bug B sm_60-specific?** Untested on RDNA4 — the 9070 XT is a single GPU, so there is no
  tensor split and no split-axis resolution. Needs a second AMD card.
- **Fidelity.** Every "clean" here means *not degenerate*. No quality claim anywhere.
- **Reporting is Mark's call.** Bug A goes to Tom and buun. Bug B is upstream — noting that
  Mark has previously declined to file with `ggml-org` over their AI-assistance policy, so
  routing that one is his decision, not mine.
