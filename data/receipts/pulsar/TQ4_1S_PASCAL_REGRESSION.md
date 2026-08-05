# TQ4_1S generates garbage on sm_60 in `6aa97d810` (post-#256) but is coherent in `d0e2a8b64`

**Node `.73`, 2× Tesla P100-PCIE-16GB (sm_60), 150 W cap / 1063 MHz app clock, persistence ON.
2026-08-03.** Model: `Qwen3.6-27B-MTP-TQ4_1S.gguf` (MidnightPhreaker), `qwen35` dense, 65 blocks,
MTP head at `blk.64`, declared type **46 = TQ4_1S**, payload verified **20.000 B / 32 vals** from
tensor offsets. Flags on every arm: `-c 8192 -fa on -np 1 -ngl 99 -sm tensor`, temp 0,
`cache_prompt:false`, K=3 after a discarded warm draw.

| build | tree | version |
|---|---|---|
| OLD | `~/tom_rebase` `d0e2a8b64` | 10281 |
| NEW | `~/tom_sync` `6aa97d810` (post-#256) | 116 |

## The regression

Same model, same flags, same prompt, greedy decoding:

```
OLD:  the airplane, the automobile, and the computer. A. True B. False Answer: B ...
NEW:  to from W / The W is ...  is  is ... ... ... ... ... ... ... ... ... ... ...
```

With `GGML_TQ_NATIVE=1` (conversion off) NEW degrades further — the server returns HTTP 500
because its own parser rejects the output:

```
W common_chat_peg_parse: unparsed Content-only output: ?ptpt ? over然是 over over ieee????????????
W srv operator(): got exception: {"error":{"code":500,"message":"The model produced output that
   does not match the expected Content-only format","type":"server_error"}}
```

**MTP draft acceptance corroborates it independently.** The MTP head and the target model are the
same weights; when the target's logits are broken they stop agreeing:

| n-max | OLD t/s | NEW t/s | accept OLD | accept NEW |
|---|---|---|---|---|
| none | 16.44 / 16.46 / 16.46 | 15.95 / 15.94 / 15.96 | — | — |
| 1 | 26.27 / 26.26 / 26.26 | 21.19 / 20.97 / 21.02 | **0.938** | 0.595 |
| 2 | 29.43 / 29.47 / 29.53 | 17.99 / 18.03 / 18.04 | **0.832** | 0.331 |
| 3 | 30.25 / 31.09 / 31.08 | 15.29 / 15.32 / 15.35 | **0.795** | 0.229 |

On OLD, MTP scales normally (16.46 → 31.08 t/s = **1.888×**). On NEW it is *negative* — throughput
falls as draft depth rises, because almost nothing is accepted. Acceptance of 0.229 at n-max 3, and
0.005 in native mode, is noise.

## Control: the regression is TQ-specific, not a broken build

Same NEW binary, same flags, non-TQ models:

| model | OLD | NEW | text |
|---|---|---|---|
| `Qwen3.6-27B-Q6_K-MTP` (dense, non-TQ) | coherent, 13.30 t/s | **coherent**, 12.95 t/s | byte-identical |
| `Qwen3.6-35B-A3B-UD-IQ4_NL-MTP` (MoE, non-TQ) | coherent, 46.94 t/s | **coherent**, 44.20 t/s | divergent, both coherent |
| `Qwen3.6-27B-MTP-TQ4_1S` (dense, **TQ**) | coherent, 16.46 t/s | **GARBAGE** | — |

NEW is uniformly ~3–6% slower than OLD (general cost of the merge) but only **TQ4_1S** breaks.

⚠️ Methodology note: the non-TQ MoE produced *divergent but coherent* text across builds at temp 0.
So "greedy output must be byte-identical across builds" is too strong a test — small numerical
differences flip one token and cascade. Coherence is the discriminator; byte-equality is only
informative when it holds.

## What is NOT the cause

`ggml_tq_convert_q8()` is **byte-identical in both builds** and defaults ON (`GGML_TQ_NATIVE=1`
opts out), so the load-time TQ4_1S→q8_0 conversion is not the differentiator. Confirmed empirically
by VRAM, not by reading comments:

| mode | VRAM / GPU | note |
|---|---|---|
| default | 12465 MiB | conversion ran: 20 B/block → 34 B/block |
| `GGML_TQ_NATIVE=1` | **9905 MiB** | native weights |

5.0 GiB saved across the pair — matching the source comment's "saves 1.7× VRAM" exactly
(34/20 = 1.70). NEW breaks in **both** modes, so the fault is not confined to either path.

⚠️ **Provenance of these two numbers:** they were measured in *separate scripts* (`dense_tq.sh` and
`tq_native.sh`) at identical flags (`-c 8192 -fa on -np 1 -ngl 99 -sm tensor --spec-type none`),
not as a back-to-back pair inside one run. The arithmetic (34/20 = 1.70) is what makes the reading
decisive; the VRAM pair corroborates it. A single script alternating both modes would be the clean
version if this is ever contested.

## Separate finding: on sm_60 the native TQ4_1S decode path is *slower* than converting to q8_0

Measured on OLD (the build that works), same model, same flags:

| | default (converted to q8_0, 8.5 bpw) | `GGML_TQ_NATIVE=1` (5.0 bpw) |
|---|---|---|
| decode | **16.44 / 16.46 / 16.46** | 15.49 / 15.51 / 15.51 |
| MTP n-max 3 | **30.25 / 31.09 / 31.08** | 27.73 / 29.29 / 29.30 |
| VRAM / GPU | 12465 MiB | 9905 MiB |

Native TQ4_1S is **5.8% slower while moving 41% less weight traffic**. The fork's own comment claims
"Native TQ4_1S decode is faster (+29-33%)". That does not hold on sm_60.

Mechanism: **`__dp4a` is sm_61+, and P100 is sm_60.** The TQ decode kernel's per-block WHT rotation
and centroid dot product fall back to scalar integer math on this hardware, making decode ALU-bound
rather than bandwidth-bound — so the bpw saving cannot be collected. This is the same sm_60 dp4a gap
that had to be patched out of pulsar to compile it for these cards.

**Practical consequence: on Pascal, keep the default conversion for speed and use
`GGML_TQ_NATIVE=1` only to buy the 1.7× VRAM saving when a model would not otherwise fit** — the
trade is ~6% throughput for ~2.5 GiB per GPU.

⚠️ **This also means any "TurboQuant decode" number taken with default flags is a q8_0 number**,
not a TQ number, on any hardware. Benchmarks of the TQ decode path must set `GGML_TQ_NATIVE=1` or
they measure the wrong kernel.

## Scoring against pre-registration

- **P-TQ4 (0.7): "dense TQ4_1S is SLOWER than the same model at Q6_K" — FALSIFIED**, and by a wide
  margin in both modes: 16.46 (default) and 15.51 (native) vs Q6_K's 13.30, i.e. +23.8% and +16.6%.
  My mechanism was wrong twice over. I reasoned from *whole-file size* (19.93 vs 21.31 GiB, only
  6.5% smaller) when the file mixes Q8_0 and Q4_K tensors, and I assumed the comparison ran TQ
  kernels when the default path had silently converted the weights to q8_0. The real reason TQ4_1S
  wins here is that **q8_0's dequant kernel is cheap on Pascal while Q6_K's k-quant superblock
  dequant is not** — an ALU story, not the bandwidth story I told.
- **P-TQ5 (0.6): "MTP on dense TQ yields a smaller multiplier than the MoE's 1.487×" — FALSIFIED.**
  Measured **1.888×** default and **1.889×** native, at 93.8% acceptance at n-max 1. The predicted
  mechanism (the `2293b1da6` contiguity gate forcing MTP verify batches onto a slow path) is not
  what happens; on the build where TQ works, that gate does not exist, and on the build where it
  does, the model is broken outright rather than merely slower.
- **P-TQ1 / P-TQ2 / P-TQ3 — UNSCORABLE**, see `TQ_ENUM_DRIFT_INTEROP.md`: the MoE they concerned
  never loads.

Every scored prediction in this session was falsified. The two that mattered were both cases of
reasoning from a plausible mechanism without first checking which code path actually executes.

## ROOT CAUSE — CONFIRMED BY BUILD: `sync/upstream-master` is missing a fix, not carrying a new bug

**The two builds are DIVERGENT BRANCHES, not linear.** `git merge-base d0e2a8b64 6aa97d810` =
`eb41d503b` (2026-07-31, upstream). `d0e2a8b64` (Aug 2) carries TheTom's TQ work rebased onto that
base; `6aa97d810` (Aug 3) merged TheTom's **Jul-18** branch (`c26cbdffc`) into it. So the correct
question is not "what did NEW add" but **"what does NEW lack"**.

Two TQ commits are present in the working tree and absent from the broken one:

```
e130aef60  fix : close complete-audit findings - 7 port regressions + TQ4_1S dp4a kernel
5fd308947  cuda : add TurboQuant MMVQ/WHT/inner-quant CUDA kernels
```

`e130aef60` (**author: jabbatheduck, 2026-07-31**) lists, among 8 fixes:

> - cuda: **fix TQ4_1S dp4a centroid LUT broken by `__byte_perm` selector misuse**
> - cuda: restore `!is_tq_weight` exclusion in `ggml_cuda_mul_mat` (TQ mmvq abort)
> - tests: restore TQ3_1S/TQ4_1S all_types coverage and turbo FA sweep

Confirmed at source level — same file, same line, two trees:

| tree | `ggml/src/ggml-cuda/mmvq-tq.cu:80` |
|---|---|
| `d0e2a8b64` (coherent) | `// __byte_perm is NOT used for the interleave/LUT: its selector encoding is …` |
| `6aa97d810` (garbage) | `const uint32_t sel0 = __byte_perm(lo, hi, 0x5140u);` |

### Proof by build

Applied **only** `e130aef60`'s `mmvq-tq.cu` hunk (75 lines, `git apply --3way`, clean) to a fresh
`6aa97d810` worktree. Nothing else changed. Rebuilt for sm_60:

| mode | before patch | after patch |
|---|---|---|
| `GGML_TQ_NATIVE=1` | HTTP 500, `?ptpt ? over然是 over over ieee????` | **15.04 t/s, coherent** |
| default (q8_0 conversion) | `to from W / The W is ... is is ... ...` | **15.80 t/s, coherent** |

> the airplane, the automobile, and the computer. A. True B. False Answer: B  Which of the
> following is NOT a type of computer? …

**One file's hunk restores both paths.** That the *default* (q8_0-converting) path is also fixed
shows the load-time conversion depends on the same centroid LUT.

Patch saved at `~/tq_lut_fix.patch` on `.73`.

### Branch scope

Verified with `git branch -r --contains` / `merge-base --is-ancestor`:

| commit | `feature/turboquant-kv-cache` (default, `thetom/HEAD`) | `sync/upstream-master` |
|---|---|---|
| `e130aef60` (fix) | **present** | **ABSENT** |
| `d0e2a8b64` (coherent build) | present | — |

**The default branch is unaffected.** Exposure is limited to `sync/upstream-master` — the base of
PR #256 and the branch carrying DeepSeek-V4-Flash support, i.e. exactly the branch someone would
check out *to get DSv4*.

Note this is **disjoint from the rebase audit (PR #260)**, which audits
`feature/turboquant-kv-cache` — the branch that already contains the fix — and looks for work the
rebase dropped *from* it.

(**`giveen` = `jabbatheduck`**, same person: PR #260's author node ID decodes to GitHub user
**1180939**, matching `giveen <1180939+giveen@users.noreply.github.com>` and `J M (giveen)` in the
repo; `jabbatheduck <jabbatheduck@localhost>` is a local-only identity from a second machine. So the
author of the audit is also the author of the dropped fix `e130aef60`.) That audit's **unsure/** bucket lists the same area as unverified
(*"CUDA kernel features (~10): TQ4_1S native kernels, fused mat-vec, dp4a multi-token, load-time
conversion"*), but it could not have surfaced this one.

### Why this matters beyond one model

The fix was authored on the rebase branch and never reached `sync/upstream-master`, so the shipped
branch carries a pre-fix TQ4_1S centroid LUT. Anyone pulling `sync/upstream-master` and running a
TQ4_1S model gets silent garbage — no crash, no CUDA error, **identical throughput**, which is the
hardest failure mode to notice. `cuda_err=0` on every arm.

## Attribution of the earlier suspects: PR #256 is NOT the cause

`git revert` of the two #256 commits conflicts (`2e3ea2af8` edits the block `c29f0d1cd` added), so
the isolation was done surgically instead.

For **TQ4_1S specifically**, #256's only behavioural change is `2293b1da6`'s contiguity gate:
`c29f0d1cd` adds `!tq3_1s_fused_disabled`, which is true for TQ4_1S (only TQ3_1S is disabled), so it
is a no-op for this model. Forcing `tq_fast_path_ok = true` on the NEW tree therefore reproduces
pre-#256 dispatch for TQ4_1S exactly, changing nothing else.

Built on `6aa97d810` with that single-line change, `GGML_TQ_NATIVE=1`:

```
SURGICAL native : SERVER ERROR {'code': 500, 'message': 'The model produced output that
                  does not match the expected Content-only format'}
```

**Still broken. `2293b1da6` is cleared, and with it PR #256.**

Remaining suspect: **`b89e04f27` — *Merge upstream/master: DeepSeek-V4-Flash (deepseek4) support***,
the only other commit in `d0e2a8b64..6aa97d810` touching the TQ decode path
(`mmvq-tq.cu` −89 lines, `dequantize.cuh` −204 lines, which gained a relocated pairwise
`dequantize_tq4_1s`). Not yet confirmed by build — that needs a bisect across the merge.

Note the tested-scope gap this exposes, from `c29f0d1cd`'s own comment:

> TQ4_1S (dp4a and the AMD scalar variant) is untouched — **no model on hand uses it** and there's
> no evidence it shares this bug, so the fast path stays enabled for that type to avoid regressing
> existing users.

TQ4_1S had no test model upstream. Two now exist on `.73`, and both break on `6aa97d810`.

## Reproduction

```bash
# coherent
~/tom_rebase/build/bin/llama-server -m Qwen3.6-27B-MTP-TQ4_1S.gguf \
    -c 8192 -fa on -np 1 -ngl 99 -sm tensor --spec-type none --port 8161
# garbage, same flags
~/tom_sync/build/bin/llama-server   -m Qwen3.6-27B-MTP-TQ4_1S.gguf \
    -c 8192 -fa on -np 1 -ngl 99 -sm tensor --spec-type none --port 8162
# 500s + noise
GGML_TQ_NATIVE=1 ~/tom_sync/build/bin/llama-server ... --port 8163
```

Scripts: `~/dense_tq.sh`, `~/control_nontq.sh`, `~/tq_native.sh`, `~/isolate_256.sh` on `.73`.

---

# ADDENDUM 2026-08-04 — build provenance, and why `6aa97d810` no longer resolves

TheTom replied on issue #249 reporting that he **cannot reproduce this on the default branch**, that
`b89e04f27` is not an ancestor of `feature/turboquant-kv-cache`, and that **`6aa97d810` "is not an
object in the fork at all."** All three are correct as stated. None of them contradict this receipt.
The reason is a branch deletion, and the provenance that explains it was missing from the original
write-up. Recording it here.

## Clone provenance (the question that was asked)

Both build trees are **`git worktree`s of a single clone**, `/home/mark/oscar-turboquant` on `.73`:

```
origin    https://github.com/giveen/llama-cpp-turboquant     <- clone origin (fork of the fork)
thetom    https://github.com/TheTom/llama-cpp-turboquant.git <- added as a second remote
turbotan  https://github.com/turbo-tan/llama.cpp-tq3.git

/home/mark/tom_rebase   d0e2a8b64 (detached)   OLD / coherent
/home/mark/tom_sync     6aa97d810 (detached)   NEW / garbage
```

The clone origin is **giveen's fork**, but that is not where either tested commit came from — both
were fetched from the **`thetom` remote**, and both are TheTom's own objects:

| commit | author | reached via |
|---|---|---|
| `d0e2a8b64` | TheTom | `thetom/feature/turboquant-kv-cache` |
| `6aa97d810` | `Tom Turney <tturney1@gmail.com>` | `thetom/sync/upstream-master` |

So this is **not** a fork-of-fork artifact. Neither build carries giveen-only commits.

## `6aa97d810` is PR #256's own merge commit

From the GitHub API, `repos/TheTom/llama-cpp-turboquant/pulls/256` — verifiable from the PR page,
and unaffected by any later branch deletion:

```
merge_commit_sha  6aa97d810870837556251f6c35795606399d1f23
base              sync/upstream-master
head              tom/merge-upstream-dsv4   (2e3ea2af8)
merged            true   2026-08-03T22:59:15Z
```

Local `git log -1 6aa97d810` agrees exactly:

```
parents  b89e04f270a37bc2ec31fffcb922ab5386cc55b5 2e3ea2af828fe294767bdacb70174ca34fc33f8a
         Merge pull request #256 from TheTom/tom/merge-upstream-dsv4
```

`b89e04f27` is the **first parent** — the `sync/upstream-master` side that PR #256 merged into. That
is consistent with TheTom's statement that it is not on `feature/turboquant-kv-cache`.

## Why it no longer resolves: the base branch was deleted

`git fetch thetom --prune` on 2026-08-04:

```
- [deleted]         (none)     -> thetom/sync/upstream-master
  ffc210bfb..0463c8ef8  feature/turboquant-kv-cache -> thetom/feature/turboquant-kv-cache
```

**`sync/upstream-master` is gone from the repo.** With the only branch that contained it deleted,
`6aa97d810` is unreachable, and `git cat-file` in a current clone correctly reports nothing. It was
reachable when this receipt was written (2026-08-03, hours after the 22:59Z merge). Both
observations are accurate; they were made on either side of the deletion.

**This does not weaken the finding — it retires it.** The original Branch Scope section concluded
exposure was limited to `sync/upstream-master`. That branch no longer exists, so the exposure window
is closed by deletion rather than by a fix.

## Agreement, not conflict, on the default branch

TheTom's control (GB10 / sm_121, `0967f4997`, NemotronH-8B Config-I TQ4_1S, coherent, 26.39 t/s) and
this receipt's OLD arm are **the same claim**. Verified locally:

```
git merge-base --is-ancestor d0e2a8b64 0967f4997   ->  YES
```

The coherent build in this receipt **is on the default-branch lineage**. `e130aef60` (the LUT fix)
is likewise an ancestor of `0967f4997`, and current default head `0463c8ef8` still carries the fixed
code — `mmvq-tq.cu` retains the "Plain shifts are deterministic" comment with no `__byte_perm`, and
`ggml-cuda.cu:1845` retains the `!is_tq_weight` exclusion. Both of the `e130aef60` hunks named in
this receipt are present on what people are running.

## Footnote: `tq_fast_path_ok`

TheTom reports zero occurrences of `tq_fast_path_ok` in `mmvq-tq.cu` on the default branch. Correct
conclusion, wrong file — the symbol lives in **`ggml-cuda.cu`**:

```
tom_sync/ggml/src/ggml-cuda/ggml-cuda.cu:2055
    const bool tq_fast_path_ok = ggml_is_contiguous(src1) && ggml_is_contiguous(dst);
```

It is upstream code on the deleted branch, not something introduced by the surgical patch (the patch
only forced it `true`). Checked branch-wide, his conclusion holds regardless of file:
`git grep -l tq_fast_path_ok thetom/feature/turboquant-kv-cache` returns **nothing anywhere** on the
default branch. The gate is `sync/upstream-master`-only.

## What is still open

The default-branch health check is **lineage-confirmed but not point-confirmed**. `d0e2a8b64` is an
ancestor of `0967f4997`, but **8 commits separate them, and 1 of those touches TQ CUDA/quant code**.
That gap is unmeasured on sm_60.

Separately, the second defect from `PHASE0_BUILD_VALIDATION.md` —
`MUL_MAT(tq4_1s, m=256,n=256,k=1536,k_v=1600)` **NaN on both CPU and CUDA, unaffected by the LUT
fix** — has not been checked against `0967f4997`. CPU reproduction implies shared code rather than
the deleted branch. A single-prompt coherence check cannot surface it; it needs `test-backend-ops`.
Both questions close with one default-branch build. Status: **running, see below.**

---

# RESULTS — default branch `0967f4997` on sm_60, 2026-08-04

Built in a third worktree (`/home/mark/tom_default`, detached at `0967f4997`) so the known-good
control build at `d0e2a8b64` stays untouched. `0967f4997` chosen deliberately over current head
`0463c8ef8` — it is **exactly** the commit TheTom tested on GB10, making this a same-commit /
different-architecture control rather than a new variable. Provenance asserted before building:
`e130aef60` and `d0e2a8b64` both ancestors, `tq_fast_path_ok` absent from the tree, `__byte_perm`
absent from `mmvq-tq.cu` (the one hit is the explanatory comment). Build version `100 (0967f4997)`.

## ✅ Coherence — TheTom's Q2 answered, both paths

`Qwen3.6-27B-MTP-TQ4_1S.gguf`, `llama-cli`, greedy (`--temp 0 --seed 1`), `-c 4096 -fa on -ngl 99
-sm tensor`:

| mode | result | generation |
|---|---|---|
| default (q8_0 conversion) | **coherent**, exit 0 | — |
| `GGML_TQ_NATIVE=1` | **coherent**, exit 0 | **15.5 t/s** |

The native figure reproduces `d0e2a8b64`'s 15.49 / 15.51 / 15.51 t/s. **The default branch is
healthy on sm_60 for TQ4_1S, in both the converted and native paths** — confirming TheTom's GB10
result on a second architecture, and confirming that the garbage was confined to the deleted
`sync/upstream-master`.

## ⚠️ The NaN is REAL, is on the DEFAULT branch, and is a CPU-side defect

The base sweep passed clean — `test-backend-ops test -o MUL_MAT`, exit 0, **3/3 backends**, 536
tq4_1s rows, 0 NaN. **That result is not exculpatory**: `k_v=1600` has **0 occurrences** in
`0967f4997`'s test file, exactly the caveat that made `d0e2a8b64`'s clean run inconclusive in
`PHASE0_BUILD_VALIDATION.md`. The branch passes every test it has; the failing shape is not among
them.

The two generating lines exist **only** on the deleted `sync/upstream-master`
(`tests/test-backend-ops.cpp:9148-9149`), preserved locally because the `tom_sync` worktree still
pins `6aa97d810`. `test_mul_mat`'s member layout (`m, n, k, bs[2], nr[2], per[4], k_v`) is identical
on both branches, so the 8-argument call compiles unchanged — a 2-line backport pulling no API
surface across. Applied, rebuilt, then reverted (tree left clean).

**It reproduces:**

```
Backend 1/3: CUDA0   1483/1484 tests passed
  [MUL_MAT] NaN at index 245 (CUDA0=8.191498  CPU=nan)
  MUL_MAT(type_a=tq4_1s,type_b=f32,m=256,n=256,k=1536,...,k_v=1600,o=1)   Backend CUDA0: FAIL
Backend 2/3: CUDA1   1483/1484 tests passed
  [MUL_MAT] NaN at index 246 (CUDA1=5.454212  CPU=-nan)                    Backend CUDA1: FAIL
Backend 3/3: CPU
1/3 backends passed
```

**The attribution has flipped, and this is the substantive new finding.** On `6aa97d810` both sides
were NaN (`CUDA0=nan CPU=-nan`) — the CUDA side being independently broken by the `__byte_perm` LUT
bug. On `0967f4997`, with the LUT fix present, **CUDA produces finite values and the CPU reference
produces NaN**. The failures are recorded against CUDA0/CUDA1 only because `test-backend-ops`
compares every backend against the CPU reference, and that reference is the broken one. CPU is never
tested as a backend at all — the run reports `Backend 3/3: CPU` / **`Skipping CPU backend`**, since
it *is* the reference. **A defect in the CPU reference is therefore structurally invisible to this
suite except as a false accusation against every other backend**, which is exactly the shape of what
is seen here.

⚠️ **This does not establish that CUDA is correct at this shape.** The two CUDA backends report
*different* values at *different* indices for the same op (`CUDA0=8.191498` at index 245,
`CUDA1=5.454212` at index 246). That is consistent with "CPU broken, CUDA fine", and equally with
"both wrong, CPU merely louder about it". With the only reference producing NaN there is nothing
left to check CUDA against, so CUDA correctness here is **untested, not demonstrated**.

So: **the CPU implementation of TQ4_1S `MUL_MAT` with non-contiguous `src1` (`k_v > k`) yields NaN,
on the branch people are running.** This is consistent with the original `PHASE0` reasoning — CPU
reproduction implied shared code rather than anything on the deleted branch — and that reasoning is
now the confirmed half.

TQ3_1S at the identical shape reports `not supported [CUDA0, CPU]` and is skipped. **TQ4_1S-specific.**

### Honest limits on this one

- **Real-world impact is unproven.** The 27B model generated coherently on both paths on this same
  build. This is a reference-path failure at a synthetic shape; whether a production graph feeds a
  non-contiguous `src1` into a TQ4_1S matmul on CPU is not established here.
- The deleted branch's own comment says these cases exercise "the rotate-act contiguity fallback" —
  i.e. the `tq_fast_path_ok` gate, which is `sync/upstream-master`-only. On CUDA the default branch
  may route this shape differently, so the CUDA-side pass proves less than it appears. The **CPU**
  NaN is unaffected by that objection: the CPU backend has no such gate.

### The coverage point, which is the actionable part

The only test that catches this was deleted along with `sync/upstream-master`. The default branch
gained the fix (`e130aef60`) and lost the test; the deleted branch had the test and lacked the fix.
Neither branch could ever have shown both. **Porting those two lines forward is a 2-line change that
restores the coverage** — worth raising regardless of what the NaN turns out to be.

And it is not only those two lines. Diffing the two test files shows **29 TQ-relevant lines present
on the deleted branch and absent from the default branch**, including **6 additional
`test_mul_mat` cases** for TQ3_1S/TQ4_1S — a DeepSeek-V4 MLA shape (`128, 512, 512`), an
`m, 256, k` batched sweep, and two large-k cases (`1024, nb, 4096` and `24, nb, 16384`). The
coverage loss is broader than the single case that happened to be caught. Full file and the
extracted delta preserved under `preserved/`.

## Prediction scoring

| id | conf | claim | outcome |
|---|---|---|---|
| P-D1 | 0.85 | coherent on `0967f4997` / sm_60 | **CONFIRMED** |
| P-D2 | 0.60 | NaN still reproduces, on both CPU and CUDA | **SPLIT** — reproduces (right), but CUDA is now clean; CPU alone is the source |
| P-D3 | 0.70 | `GGML_TQ_NATIVE=1` also coherent | **CONFIRMED** |
| P-D4 | 0.45 | NaN does **not** reproduce | **FALSIFIED** |

P-D2 and P-D4 are contradictory because they were registered at different times: after seeing that
the test targets the `tq_fast_path_ok` contiguity gate — branch-exclusive code — I revised downward
from "reproduces" (0.60) to "does not" (0.45). **The revision was wrong and the original reasoning
was right.** The gate argument applied only to the CUDA path; it never bore on the CPU reference,
which is where the fault actually lives. Recorded rather than quietly dropped, since the whole point
of pre-registration is to catch this kind of mid-course rationalisation.

Artifacts on `.73`: `~/default_branch_check.sh`, `~/nan_backport.sh`, `~/default_check.log`,
`~/nan_backport.log`, `~/tbo_default.txt`, `~/tbo_nan.txt`, `~/cli_default.txt`, `~/cli_native.txt`.

✅ **Preservation done.** `6aa97d810` and its tree survive on `.73` **only** because
`/home/mark/tom_sync` pins them; removing that worktree and running `git gc` would destroy the only
accessible copy. The at-risk material has been copied into this repo:
`preserved/test-backend-ops.cpp.6aa97d810` (the full 453,542-byte file) and
`preserved/tq_coverage_delta.txt` (the 29 TQ-relevant lines the default branch lacks). Note this
preserves the **test file**, not the branch — anything else wanted from `6aa97d810` still depends on
that worktree.

---

# BISECTED — `309de108e` is a reliable TRIGGER, not the cause (2026-08-04)

The NaN was walked across the four commits on the default branch that touch CPU TQ code. Only four
exist, and `9421bd097` predates the TQ4_1S type entirely, so this is a complete walk rather than a
sample.

| commit | subject | result |
|---|---|---|
| `9421bd097` | WIP: add TurboQuant KV cache types (turbo3, turbo4) | skipped — no TQ4_1S type yet |
| `00fda770b` | ggml : port TurboQuant core quant types and CPU kernels | **CLEAN**, 3/3 backends |
| `309de108e` | ggml-cpu : fix get_n_tasks NULL deref for single-input ops | **NaN**, 1/3 backends |
| `0967f4997` | fix: apply rebase-audit fixes (stack overflow + docs) | **NaN**, 1/3 backends |

Every result was validated by confirming the backported `k_v=1600` row is actually **present in the
test output**, not merely that the run exited 0 — see the methodology note below for why.

## The clean side is deterministic, not lucky

`00fda770b` was re-run **5×**, and because the insertion landed inside a shape loop each run
registered the case **468 times**: **2,340 executions of the exact failing shape, zero NaN**, 3/3
backends every run. This is not a single-run existence proof.

For contrast, an unrelated case flaked during this work — `MUL_MAT(q5_1, m=16, n=1, k=256)` with
`ERR = 0.000534801 > 0.000500000`, once in five runs. So the suite *does* have run-to-run variance
on this box; the TQ4_1S result is clean *despite* that, which is what makes it load-bearing.

## But the diff cannot cause it

`309de108e` is **three lines** in `ggml/src/ggml-cpu/ggml-cpu.c` plus a doc edit:

```c
         case GGML_OP_FLASH_ATTN_BACK:
         case GGML_OP_SSM_CONV:
         case GGML_OP_SSM_SCAN:
+            {
+                n_tasks = n_threads;
+            } break;
         case GGML_OP_RWKV_WKV6:
```

It restores an upstream/fork split in `ggml_get_n_tasks` so single-input ops stop dereferencing a
NULL `src[1]`. **It does not touch MUL_MAT, TQ, or any quant path**, and under `test -o MUL_MAT` the
graph contains no SSM or FLASH_ATTN nodes at all — so the changed branches are never even reached.

There is no causal path from this diff to a MUL_MAT NaN. The reading that fits every observation is
a **latent uninitialized-read (or race) in the CPU TQ4_1S non-contiguous-`src1` path**, present at
both commits, whose manifestation depends on compiled binary layout and therefore on whatever
unrelated code happens to sit nearby. `00fda770b` is clean because its layout leaves the unwritten
region benign, not because the code is correct there.

**Practical consequence: do not report this as "309de108e introduced the NaN."** It is a reliable
reproducer, which is genuinely useful, but bisecting further will not find the defect. The next step
is a memory checker — running the single failing case under **valgrind or `-fsanitize=memory`** on
the CPU backend should name the uninitialized read directly, and is far cheaper than more bisection.

Supporting evidence for "CPU-side": with the `__byte_perm` LUT fix present, CUDA returns finite
values while the CPU reference returns NaN, and CPU is never exercised as a backend
(`Skipping CPU backend`) because it *is* the reference.

## ⚠️ Methodology note — two void runs before this one

The first two determinism attempts reported "0 of 5 runs showed NaN" and were **meaningless**: the
backported case never registered. The anchor used was *the first*
`emplace_back(new test_mul_mat(` in the file, which at this commit is line 8827 — **inside an
`#if 0` block** at 8825 (`// > 4GB A matrix. Too slow to be enabled by default.`). The line compiled
into nothing.

The original probe avoided this **by accident**: its walk-back loop reversed past the comment and
the `#if 0` to a preceding blank line, landing outside the block. So the probe's bisect data was
valid all along; only the follow-up scripts were broken.

Two lessons worth carrying:

1. **A guard that prints a warning but still computes a summary will produce a confident wrong
   answer.** The `!! case did not run` warning fired on all five runs, and the script *still*
   printed "consistent with 309de108e genuinely introducing it". The abort belongs at the guard,
   not the log line.
2. **"Exit 0 / N backends passed" is not evidence a specific case ran.** Always confirm the case's
   own row is in the output. This is the third time in this campaign the same class of error
   appeared (clean `test-backend-ops` on a suite missing the case; `pgrep` matching its own command
   line; and now insertion into dead code).

## Prediction scoring

| id | conf | claim | outcome |
|---|---|---|---|
| P-D5 | 0.75 | every commit with TQ4_1S NaNs — never worked | **FALSIFIED** — `00fda770b` is deterministically clean |
| P-D6 | 0.55 | `00fda770b` not clean on all 5 repeats | **FALSIFIED** — 0/5, across 2,340 executions |

Both falsified. The common error was assuming the defect was *in* the TQ code path itself; the
evidence points instead to TQ code that is correct in isolation but reads memory someone else was
supposed to initialise.

Artifacts on `.73`: `~/nan_probe.sh`, `~/nan_probe2.sh`, `~/nan_repeat3.sh`, `~/nan_repeat3.log`,
`~/tbo_probe2_*.txt`, `~/tbo_rp3_*.txt`.
