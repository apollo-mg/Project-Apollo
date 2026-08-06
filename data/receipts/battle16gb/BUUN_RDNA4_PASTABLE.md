# Discord pastable for buun — RDNA4: a turbo4 nondeterminism/NaN bug, and where the 6× isn't

Draft for Mark to review and send. Numbers from `buun_isolate/results.tsv`,
`buun_isolate/regression.log`, `buun_isolate/nanrate/nanrate.log`, and the 2026-07-23
`RDNA4_AB_FINDINGS.md`.

---

Went hunting for the RDNA4 slowdown on your fork this morning. Ended up finding something I
think matters more. Rig: RX 9070 XT (gfx1201, HIP), `Qwopus3.5-27B-v3-Q2_K`, wikitext-2,
ctx 2048, 2 chunks. Both forks built identically (Release, `-O3 -DNDEBUG`, gfx1201,
`GGML_HIP=ON`) — checked, so none of this is a build-flag artifact.

**1. Your turbo4 decode is nondeterministic on RDNA4, and ~9% of the time it NaNs.**

22 turbo4 runs, same binary, same flags, same model file, back to back:

```
NaN:            2 / 22 runs   ([1]nan,[2]nan -> "Unexpected negative standard
                               deviation of log(prob)", exit code 0)
finite PPL:     8.0984 - 8.1825 across 11 consecutive runs — every one different

for contrast, same session, same card:
  your f16:     7.4948   every run, bit-identical
  tom turbo4:   7.4880   every run, bit-identical
```

So it's not the harness, not the machine, not thermals — it's specific to your turbo decode
path here. The NaN and the drift look like the same underlying thing: usually it perturbs the
result a little, occasionally it lands somewhere that produces NaN.

Note the NaN run **exits 0** and only prints the error to stderr, so anything checking exit
codes will record it as a clean pass.

**Reproducer:**
```
llama-perplexity -m Qwopus3.5-27B-v3-Q2_K.gguf -f wiki.test.raw \
  -ctk turbo4 -ctv turbo4 -fa on -c 2048 --chunks 2 -ngl 99
```
Run it ~10 times and compare `Final estimate: PPL`. f16 is identical every time; turbo4 isn't.

**This makes my earlier fidelity numbers provisional.** I reported your turbo4 at 90.200%
same-top vs Tom's 97.642% (matched tiers, each against its own f16 base). If the decode path
is nondeterministic, those were n=1 samples of a distribution — some of that 7-point gap could
be variance. I wouldn't act on those numbers until this is sorted.

**2. On the speed gap: it's the prefill path, not RDNA4 generally, and it's not new.**

```
tom  f16 / turbo4     10 s
buun f16 / turbo4     61 s        ~6.1x, flat across both
```

Three things worth knowing:

- **Flat across f16 and turbo4.** A cost that's the same with and without a codec in the loop
  probably isn't in the codec.
- **Not a regression.** I re-ran the identical test on the `58364703a` build from the July 23
  unroll A/B (~200 commits back): **62 s**, same as today's 61 s. No bisect window.
- **Your fork is NOT uniformly slow on this card.** On that same commit, decode benched
  **36.45 t/s** on Bonsai-8B — healthy. So decode is fine; it's the prefill/perplexity path
  that's ~6× off. That's a much smaller haystack.

I tried your own switches on it and neither moved: `TURBO_MEANSUB_OFF=1` +1.6%,
`TURBO_FUSED_PREFILL=1` +1.6% (both noise). The tap is doing real work though — disabling it
moved turbo4 PPL 8.11 → 8.44, so it's worth ~0.33 PPL, just not any time.

(My earlier note said 8×; that was 8 chunks including a cold-cache first pass. 6.1× warm is
the honest number.)

**3. One thing to re-open.** Back on July 23 the `Qwen3.5-35B-A3B-IQ2_M` GPU memory-access
fault got written off as a possibly-corrupt file. Given a different model is now producing
NaN and run-to-run drift on the same fork and card, that might have been the same bug rather
than a bad download. Might be worth another look.

Happy to run whatever you want on this card — ~1 min per cell at 2 chunks. Can also run under
`AMD_SERIALIZE_KERNEL=3` or with `-fa off` if you want to test a race/kernel hypothesis, or
bisect the ~200 commits if the prefill thing turns out to be worth chasing.

---

## Notes for Mark (do not paste)

- **Both of my going-in hypotheses were wrong** (VMEAN tap, fused-prefill gate). The pastable
  leads with the bug I found by accident instead, and reports the negatives so he doesn't walk
  the same two dead ends.
- **The NaN/drift was found by running every cell twice** — a habit adopted after a cold-cache
  first load burned us earlier today. It is not something I set out to test.
- **The July 23 material you sent changed this draft materially.** It supplied the older build
  that proved "not a regression", and the 36.45 t/s decode number that narrows this to the
  prefill path. Without it I'd have sent a vaguer report.
- **`rc` did not catch the NaN** (exit 0). I only caught it because the PPL string was missing.
  Worth remembering for our own harnesses.
- Rate is **2/22 ≈ 9%**, from 10 mixed-config runs + 12 stock reps. Stated as ~9% rather than
  a precise figure since the configs weren't all identical.
- I flagged my own 90.200% fidelity number as provisional. That's a real retraction, not
  politeness — n=1 cells can't support a 7-point claim against a nondeterministic path.
- **Untested, if he asks:** whether the drift is depth-dependent (grows with `--chunks`),
  whether K-only (`-ctk turbo4 -ctv f16`) isolates it to the K or V kernel, and whether the
  other turbo tiers drift too (only turbo4 was swept for rate).
