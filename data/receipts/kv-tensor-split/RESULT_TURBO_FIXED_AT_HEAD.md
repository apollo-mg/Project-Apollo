# Verified: buun `424c3361e` fixes the turbo-KV collapse on a second RDNA4 card

**2026-09-03.** RX 9070 XT (gfx1201, ROCm), buun-llama-cpp at **`3823c9eb6`**, freshly built.
Gate before running: `BUILD_RC=0`, `git merge-base --is-ancestor 424c3361e HEAD` -> YES,
binary age 4s. Raw: `raw_verify_head_k5.jsonl` / `.log`.

## Before and after

Same card, same model (`Qwen3.8-27B-AD-IQ2_XS`, `qwen35` hybrid, GQA 6:1, D=256), same
`-c 4096 -fa on --jinja --kv-unified -np 1`, temp 0, seed 42, same probes.

| | `7a918624b` (2026-09-01) | `3823c9eb6` (2026-09-02) |
|---|---|---|
| turbo cells clean | **2 of 10** (K=1) | **50 of 50** (K=5) |
| `turbo4` schema copy | COLLAPSE, 1200 tok, empty | **stop, 256 tok, 3/3 terms** |
| `turbo4` @ 2,133 tok | COLLAPSE, 1200 tok, empty | **stop, 611 tok** |
| `turbo3` schema copy | COLLAPSE, 1200 tok, empty | **stop, 132 tok, 3/3 terms** |
| `turbo3` @ 2,133 tok | COLLAPSE, 1200 tok, empty | **stop, 632 tok** |
| `turbo8` @ 2,133 tok | COLLAPSE, 1200 tok, empty | **stop, 665 tok** |
| `q8_0`-K/`turbo4`-V @ 2,133 tok | COLLAPSE, 1200 tok, empty | **stop, 662 tok** |

Full K=5 score, all ten cells:

```
  f16       schema_copy  clean 5/5   ctok=[114, 114, 114, 114, 114]
  f16       long1500     clean 5/5   ctok=[618, 618, 618, 618, 618]
  turbo4    schema_copy  clean 5/5   ctok=[256, 256, 256, 256, 256]
  turbo4    long1500     clean 5/5   ctok=[611, 611, 611, 611, 611]
  turbo3    schema_copy  clean 5/5   ctok=[132, 132, 132, 132, 132]
  turbo3    long1500     clean 5/5   ctok=[632, 632, 632, 632, 632]
  turbo8    schema_copy  clean 5/5   ctok=[256, 256, 256, 256, 256]
  turbo8    long1500     clean 5/5   ctok=[665, 665, 665, 665, 665]
  q8turbo4  schema_copy  clean 5/5   ctok=[256, 256, 256, 256, 256]
  q8turbo4  long1500     clean 5/5   ctok=[662, 662, 662, 662, 662]
```

"Clean" for `schema_copy` requires `finish=stop` **and** all three fixed terms present
character-for-character, not merely non-empty output.

## The run is deterministic — which retires my own caution

Every cell returned **identical completion-token counts across all five repetitions**. Not
approximately: identical. poshih describes the symptom in `turboquant#311` as *"stochastic;
rate scales with prompt length and output length"*, and on that basis I flagged all the
earlier K=1 measurements as possibly unable to distinguish a fix from a lucky draw.

**On this hardware, in this configuration, that concern does not apply.** temp 0 + fixed seed
is bit-stable here across repeats. The earlier K=1 results therefore stand as measured. The
caution was correct a priori and wrong in fact; recording both.

(This does not contradict poshih — different fork, different hardware, different sampling.
It scopes the stochasticity claim to their setup, not ours.)

## What this supports being said publicly

Independent confirmation, on a second RDNA4 card, that `424c3361e` closes the collapse for
`qwen35` hybrid at D=256, across `turbo3`, `turbo4`, `turbo8` and `q8_0`-K/`turbo4`-V, at
both 71-token and 2,133-token prompts, K=5, deterministic.

That is a stronger statement than "everything runs," and it is the loop closing on the
2026-08-19 KV map (`../vbr-backend/kv-map.html`, `TIMELINE_KV_MAP_TO_FIX.md`).

## Repo state

`engines/buun-llama-cpp` was moved from `7a918624b` to `3823c9eb6` and left there — it is the
fixed version and the better default. Original SHA recorded in
`scratchpad/buun_orig_sha.txt`; restore with `git checkout 7a918624b`. **Note that rebuilding
in place destroyed the pre-fix binary**, so the before-column above is K=1 and cannot now be
deepened without rebuilding the old commit.
