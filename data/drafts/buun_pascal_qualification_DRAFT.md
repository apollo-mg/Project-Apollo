Pascal qualification for 4d90517b1, which closed with "actual Pascal hardware qualification
remains pending". I have 2x Tesla P100-PCIE-16GB (GP100, sm_60), so here is that run.

**Build**

- origin/master `08826ad6`
- `-DCMAKE_CUDA_ARCHITECTURES=60`, CUDA 12.4
- host compiler pinned to gcc-13 (CUDA 12.4 hard-errors above gcc 13 and this box defaults
  to gcc 15.2)
- configure and build both rc=0, zero errors, about 20 minutes on a 6-core 8600K at -j 6

**Results**

```
test-exl3-byte-dot
  PASS: all 65536 codebook products, unsigned byte sums, mixed byte dots
        and wrapping accumulation
  exit 0

test-backend-ops test -o MUL_MAT -b CUDA0
  Backend 1/3: CUDA0
    1529/1529 tests passed
```

451 MUL_MAT cases reported "not supported", all of them `type_a=tq2_0`, which the CUDA backend
does not implement. Skipped rather than failed, so I read that as expected.

**One thing I checked before trusting the pass**

I wanted to be sure the test was not silently compiling out the path it is meant to cover. At
`__CUDA_ARCH__ == 600` both `byte_sum` and `dp4a_us` take the scalar `#else` branch, since
`__dp4a` is sm_61 and GP100 does not have it. So the branch under test is the one no sm_61+ card
can reach, which I think is why the 3090 run could not close this out.

**Not covered**

- Only MUL_MAT, not the full op suite. My daily driver was resident on the same GPUs (about
  2.3 GB free), so a full run risked an OOM on a box that was serving.
- Single device (`-b CUDA0`). The second P100 is untested.
- No end-to-end inference on this build yet, only the unit-level tests above.

Happy to run the full op suite, the second device, or a server shakedown when I can take the
node out of service. Just say which would be most useful.

**Possibly worth knowing:** I hit the same `__dp4a` issue the same week in an unrelated project
(exllamav3 fails to build for sm_60 on an unguarded `__dp4a` in its EXL3 codebook header), and
the fix there landed on the same `__CUDA_ARCH__ >= 610` threshold and the same scalar fallback
you used. Might be a general trap for anything carrying EXL3-derived CUDA, since the intrinsic
sits one minor revision above what people usually mean by "Pascal", and the datacentre part is
the one that lacks it.

*Posted by my agent (Claude Opus 5) on my behalf. The hardware and the runs are mine; I reviewed this before it went out.*
