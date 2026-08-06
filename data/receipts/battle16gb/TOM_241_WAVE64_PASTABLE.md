# Pastable — turboquant#241 wave64 fix confirmation (for Tom's issue thread)

Paste as one comment. Source data: `TURBO3_241_WAVE64_FIX_CONFIRMED.md`,
artifacts in `turbo3_w64_artifacts/`.

---

Confirmed on the RX 580. **`11a8377bd` fixes it, and the specificity is clean.**

Same 7-cell matrix, same box, same model (Crow-9B IQ4_XS), same probe, `cache_prompt:false`,
**cell order held identical** to the previous run so the byte comparisons stay valid:

| cell | unpatched | **11a8377bd** | |
|---|---|---|---|
| kturbo4_vturbo3 | 0.2736 / `173da68272cc` | **0.4866** / `b031d9c337e8` | changed |
| kf16_vf16 | 0.5097 / `ad9dd4fa776f` | 0.5097 / `ad9dd4fa776f` | **byte-identical** |
| kturbo4_vturbo4 | 0.5024 / `9e33a09474a1` | 0.5024 / `9e33a09474a1` | **byte-identical** |
| kturbo4_vturbo2 | 0.5021 / `0b3b5c4235d5` | 0.5021 / `0b3b5c4235d5` | **byte-identical** |
| kturbo3_vturbo3 | 0.3474 / `65e01d083c83` | **0.5152** / `4cb388a93d6d` | changed |
| kf16_vturbo3 | 0.1753 / `b539962f600d` | **0.5251** / `169b27a7251c` | changed |
| kturbo3_vf16 | 0.4299 / `4dfeae533123` | **0.5199** / `e89131fbe39d` | changed |

**Every cell containing turbo3 changed. Every cell without turbo3 is byte-identical.** That's
the part I'd hang the attribution on — turbo2/turbo4 have no `signs` plane and no ballot, so a
correct fix to signs packing has to leave them untouched, and it does, to the byte. Both of
your predictions landed: the turbo3-V cells moved into the healthy band, and unlike last time
they are *not* byte-identical to the unpatched run.

All four recovered cells now open with the same coherent reasoning shape as the f16 control
(`1. **Analyze the Request:** ... Topic: Linux`). Before the fix each turbo3-V cell opened on a
different unrelated essay premise.

**The K-side arm you asked for:** `turbo3`-K / `f16`-V went **0.4299 → 0.5199**. You expected a
small but real lift; it closed the entire remaining gap to the 0.5097 control. Fits the
mechanism — K corruption perturbs pre-softmax scores (degraded but coherent), V corruption
feeds garbage straight into the output sum (incoherent).

Two caveats on my own numbers. The four recovered cells span 0.4866–0.5251 and
`kturbo4_vturbo3` sits ~3 pp under the others — almost certainly nothing at n=1 on one prompt,
but it's in the table so I won't call it four identical landings. And I've only validated
**wave64**. The wave32 no-op looks trivially right by inspection (`ballot_word` is always 0,
`byte_in_word` reduces to the old `local_byte`) but I have no wave32 hardware here and didn't
measure it.

**`FLASH_ATTN_EXT` turbo3: still 6/6 OK** on the fixed build, as expected — the read path was
never the problem.

**On the `SET_ROWS_TURBO3` trap — it persists on the fixed build**, and I made an instructive
mistake chasing it. My first check ran `-o SET_ROWS`, which filters on op *name* and selected
**zero** turbo3 cases: 365 lines of output, no matches, exit 0. It reads exactly like a pass.
`SET_ROWS_TURBO3` is an `op_desc`, so it needs `-o SET_ROWS_TURBO3`. With the right filter:

```
SET_ROWS_TURBO3(type_idx=i32,ne0=128,ne1=16,r=1): not supported [Vulkan0]
...
  Backend Vulkan0: OK
2/2 backends passed
OK
```

Still every case skipped, zero executed, green summary. So the shader that carried this bug
remains uncovered by a test on this backend — which is plausibly how it shipped. Glad you're
filing it separately.

**One generalisation worth more than the patch:** any `subgroupBallot` result indexed as if it
were 32 bits wide is a latent wave64 bug. Invisible on NVIDIA (warp 32), invisible on RDNA in
wave32 mode, fires on GCN. Might be worth grepping the shader tree for other `ballot.x` uses
with a lane-derived shift.

And credit where it's due — the null result only became useful because you read `warp size: 64`
off my own device dump and saw what it meant. I'd filed that line under bench-rig trivia.

Bench rig is still up and the repro is deterministic if you want anything else run on GCN
before this merges.
