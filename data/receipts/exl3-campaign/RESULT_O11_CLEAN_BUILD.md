# Result — O11 retires: buun's upstream guard replaces our local patch. The test suite is a separate story.

**Run 2026-09-13, 10:20–11:12.** Pre-registered in `NOTE_O11_CLEAN_BUILD.md` (`4b90cc7`), written while
the build was still linking. Predictions were committed before either result existed.

## P-O11a — CONFIRMED. O11 is retired.

A clean worktree of buun `da458765d` at `/mnt/HDD/buun-da458` on `.73`, `git status` empty — **no
`PATCH_e8m0_cuda128_guard.diff`** — configured `-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=60` and built
to **`BUILD EXIT 0`** on **CUDA 12.4**.

Since 2026-09-11 every sm_60 build in this campaign has carried a local two-line guard, because humming's
`__nv_fp8_e8m0` types break `ggml-cuda` on any toolkit below 12.8 and the fleet is held at 12.4. buun's
**`86eae269c` — "cuda: guard Humming E8M0 conversion on older toolkits"** removes that need.

**Consequence for the campaign:** O11 ("you need a patched fork to build this at all") is closed. Building
buun's master on a stock CUDA 12.4 box now requires nothing from us. The memory note
`buun-cuda-128-floor.md` is superseded for `da458765d` and later.

## P-O11b — NOT RUN, and the prediction was malformed

**The prediction said "every `test-exl3-*` returns 0 or 77", and assumed four tests.** That was wrong
before the run: it counted the four *binaries* we built, not the tests `ctest` registers from them.

`ctest -R exl3` in the new tree registered **35 tests**: 10 passed, **24 "Not Run"**, 1 failed.

- **The 24 "Not Run" are our fault, not buun's.** The build targeted only four test binaries. `da458765d`
  registers tests from others we never built — `test-exl3-tensor-split`, the `shard-bytes` / `shard-async`
  / `shard-matrix` families, `expert-boundary`, `expert-up` / `expert-down`, `cache-large-pool`. `ctest`
  reports each as `Unable to find executable`. **These are unbuilt, not broken**, and P-O11b cannot be
  scored until the tree is rebuilt with them.
- **The gate is what caught this.** `ctest` exits 0 when it finds no tests at all, so Amendment 1 scored
  the gate on "4 of 4 ran", never on the exit code. It refused the run and logged `NOT RUN` rather than
  recording a pass — the count was 35, so the assertion failed for the *right* reason even though the
  expected number was itself wrong. **An exit-code check would have recorded a clean pass here.**

### One genuine failure, worth chasing

```
89 - test-exl3-cpu-cache (Subprocess aborted)   main
```

This one **ran and aborted** — it is not a missing binary. The same test, **#89, passed on gfx1201 in
4.86 s** (`rdna4/ctest.log`, test 8's P-R2, 11/11 green).

**That is not yet an sm_60 finding**, and the receipt will not claim it is. The RDNA4 run used an earlier
commit whose suite registered **11** tests against this one's **35**, so the two differ in *both* arch and
commit. Two candidates, not separated:

1. an sm_60-specific abort, or
2. a regression in `da458765d` that would abort on any backend.

**Separating them needs one build**, of the same commit on a second backend (the control plane has no
`test-exl3-*` binaries at present). **Deliberately deferred:** `.73` is running test 10, whose entire size
axis is `peak_mib` sampled every 2 s, and any stray allocation during an arm corrupts a data point.

## What happens next

1. After test 10 frees `.73`: rebuild that tree with **all** `test-exl3-*` targets and re-run `ctest -R
   exl3` for a real P-O11b, with the expected count read from the tree rather than guessed.
2. Capture the abort message from `test-exl3-cpu-cache` (this run used `tail -40`, which kept the summary
   and discarded the assertion).
3. Build the same commit on gfx1201 and run test #89 there. **Only then** does the result tell buun
   whether he has an sm_60 bug or a general one.

## Deviations

- **The expected test count was guessed from the binaries, not read from the tree.** It should have been
  derived with `ctest -R exl3 -N` before the gate was written. The gate still failed closed, but it
  reported "expected 4" when the honest expectation was unknown.
- **`--output-on-failure` output was truncated to `tail -40`**, which is why the one real failure has a
  name but no message.
- The 10 passing tests are recorded in `kld/ctest_exl3_sm60.txt` but are **not** claimed as a partial
  pass: a suite that cannot find two thirds of its executables has not been run.
