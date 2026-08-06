RDNA4 numbers on both, RX 9070 XT (gfx1201, HIP arch 1300), ROCm 7.2.4.

## 1. `75a24b8f2` confirmed — matches the revert arm exactly

`test-backend-ops test -o FLASH_ATTN_EXT -b ROCm0`, `GGML_CUDA_DISABLE_GRAPHS=1`:

| build | OK | FAIL | `no device code` | ratio-9 OK | dies at |
|---|---|---|---|---|---|
| `75a24b8f2` | **7,604** | 0 | **0** | 784 | `hsk=576,hsv=512` in `..._tile` |
| `418b1759c` (test branch) | **7,604** | 0 | **0** | 784 | same |
| my earlier revert arm | 7,604 | 0 | 0 | 784 | same |

Out of the box, as you predicted. Finding closed from my side. **The test branch is also
correctness-neutral** — identical on every counter, so it changes selection only.

Remaining death is the separate `DKQ > 128` arm of the same guard on the MLA geometry (#251).

## 2. Graphs-on: I can't support the crash concern — the measurement is nondeterministic

Short version: **no evidence the branch introduces or worsens the capture abort.**

I nearly reported the opposite. First run looked damning — head reached 3,951 passing tests
before aborting, branch only 997, a 4× regression with a ready mechanism (more shapes to TILE →
raw temp buffers during capture). Then I repeated it:

| build | graphs-on OK counts before abort, across runs |
|---|---|
| `75a24b8f2` | 927, 957, 3,951, 5,260 |
| `418b1759c` | 907, 997, 2,701, 5,876 |

**Same binary varies ~6× run to run.** The ranges overlap almost entirely and the head's median
is if anything higher. My K=1 result was noise, and I'd have handed you a phantom regression.

Directly testing the set the branch actually re-routes — quantized KV, small batch, graphs on:

```
-o FLASH_ATTN_EXT -p 'nb=[1-8],.*type_K=q8_0'
  head   : 545 OK, 0 capture-aborts
  branch : 545 OK, 0 capture-aborts
```

Clean on both. So on RDNA4 the branch does not appear to trade your perf bug for a crash bug —
though see the limit below.

## 3. The capture abort is stateful, and `test-backend-ops` can't localize it

Identical on both builds:

```
ROCm error: operation not permitted when stream is capturing
  in ggml_cuda_compute_forward at ggml-cuda.cu:2450  →  ggml-cuda.cu:108
#6 ggml_cuda_graph_evaluate_and_capture
#7 ggml_backend_cuda_graph_compute
```

Two ways to name the failing shape, both dead ends, in case they save someone time:

- **Last descriptor before the abort** — no good even under `stdbuf -o0`: `test-backend-ops`
  prints descriptor and verdict *together after* the test, so the failing test never prints.
- **Next test in deterministic suite order**, recovered from the graphs-off log which runs much
  further. This does name a shape — but the one it named for the branch
  (`hsk=64,nr23=[1,3],nb=75,bf16`) **passes on the head's graphs-on run**, and the branch diff
  only touches quantized types while bf16 isn't one. So the abort reflects accumulated capture
  state, not the op it lands on.

Practical consequence for #247/#251: **this bug needs a reproducibility protocol, not a single
run.** Any one-shot comparison of it — on any vendor — will give a different answer each time.

## Limit worth stating plainly

K=3–4 per arm on the graphs-on comparison. That's enough to show the spread swamps any
difference, **not** enough to exclude a small real effect — anything under roughly 6× is
invisible to this instrument at this K. If you want the branch's capture behaviour actually
characterised rather than just "not obviously worse", say the word and I'll run K=15+ per arm
overnight and give you distributions instead of point estimates.

## Separate note: `75a24b8f2` reverts one hunk more than `f924ee29f` introduced

`f924ee29f` changed a single hunk (`@@ -89`, the non-Volta block). `75a24b8f2` changes two
(`@@ -66` **Volta** + `@@ -89`). The Volta block was already modulo before `f924ee29f` — it's
modulo in upstream `0fcb3760b` and in the fork parent `e1fd6cea3`:

| | Volta branch | non-Volta branch |
|---|---|---|
| upstream `0fcb3760b` | `% 8/4/2 == 0` | `> 4/2/1` |
| fork parent `e1fd6cea3` | `% 8/4/2 == 0` | `> 4/2/1` |
| fork head `75a24b8f2` | **`> 4/2/1`** ← new divergence | `> 4/2/1` |

Upstream carries that asymmetry deliberately, with the comment *"On Volta the GQA optimizations
aren't as impactful vs. minimizing wasted compute"* — modulo packs only exact multiples, which
is the point on sm_70. The AMD fix only needed the non-Volta hunk.

Flagging rather than claiming harm: I have no sm_70 to test on, so this is a diff observation,
not a measurement. If the Volta change was deliberate, ignore me.
