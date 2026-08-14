I have gfx1201 (RX 9070 XT, RDNA4), so here is the target the CI has never built.

**Build-only, same knob you used:** `fca3093c9` (current `feature/turboquant-kv-cache`),
`-DGPU_TARGETS=gfx1201 -DGGML_HIP_EXPORT_METRICS=On`, ROCm 7.2.53211. No benchmark, no
runtime, just the resource-usage remarks. 7034 kernels analysed, 346 of them
`flash_attn_ext_vec`, **98 spilling**.

RDNA4 reproduces it, and in three ways the gfx908 picture doesn't show.

## 1. It is not confined to head size 256

You wrote *"Every flagged flash-attention instantiation is at head size 256."* On gfx1201,
spilling FA kernels by head size:

| head size | spilling |
|---|---|
| 256 | 55 |
| **128** | **40** |
| 64 | 3 |

hsk=128 is the shape the suite already tests, and the shape most models actually run. If
that also holds on gfx908 once #293 lands, the "untested shape" framing understates it —
the tested shape is affected too.

## 2. Not only TURBO4_0 as the K type

You wrote *"every one has TURBO4_0 as the K type."* K-type distribution across the 98
spillers here:

```
TURBO4_0  41
TURBO3_0  21
TURBO2_0  21
Q8_0       7
Q4_0       4
F16        2
```

TURBO4_0 does lead. But all three turbo K types spill, and the single worst kernel in the
build has **TURBO2_0** as K:

| hsk | K | V | mask | VGPR | spill | scratch B/lane | occ |
|---|---|---|---|---|---|---|---|
| 256 | TURBO2_0 | F16 | 0 | 256 | **735** | 2608 | 5 |
| 256 | TURBO2_0 | F16 | 1 | 256 | 708 | 2496 | 5 |
| 256 | TURBO4_0 | Q8_0 | 0 | 256 | 704 | 2556 | 5 |
| 256 | TURBO2_0 | TURBO2_0 | 0 | 256 | 698 | 2624 | 5 |
| 256 | TURBO3_0 | TURBO2_0 | 1 | 256 | 696 | 2688 | 5 |

All ten worst are pinned at the 256-VGPR architectural cap with occupancy 5 waves/SIMD,
pushing 2.5-2.75 KB per lane to scratch. Worst spill is **735 against your 330**, roughly
2.2x.

**11 of the 98 involve no turbo type at all**, so there is a residue here that isn't
attributable to this fork's types.

## 3. On the Q2_K `mul_mat_q` entry — your instinct looks right

You flagged `mul_mat_q<type 10, 64, true>` at 189 spilled and said it *"smells upstream."*
On gfx1201 it is both worse and clearly the dominant pattern:

```
mul_mat_q<type 10, 80, 0>   VGPR=256  spill=865  scratch=2688   <- worst in the whole build
mul_mat_q<type 10, 64, 0>   VGPR=256  spill=384  scratch=1196
mul_mat_q<type 10, 64, 1>   VGPR=256  spill=365  scratch=1104   <- your 189 case
mul_mat_q<type 10, 32, 1>   VGPR=256  spill=70   scratch=284
```

Type 10 is Q2_K, a stock ggml type, and it occupies six of the top ten `mul_mat_q`
spillers. Plenty of other stock types spill mildly too (Q8_0, Q4_0, IQ2/IQ3/IQ4, MXFP4),
all in the 3-33 range. That is consistent with an upstream issue rather than a fork one,
though I have not built clean upstream at gfx1201 to confirm — happy to do that next if
it's useful, it's the same one-command build.

## Limits

- **Compile-time only.** Spilling isn't a correctness bug, and I'm making no claim about
  #252/#253 V-cache corruption.
- **No performance number.** Occupancy 5 and 2.5 KB/lane of scratch predict a cost; I
  haven't measured one.
- **This is not your CI condition transplanted.** #293 isn't on the default branch yet, so
  this is current-branch-at-gfx1201, not gfx908's exact build conditions.
- One target, one ROCm version. Nothing here says anything about RDNA2, which as far as I
  can tell still has no data in this thread either.

One reproduction note that cost me an hour: **the turbo type IDs move between commits.** I
first read `ggml.h` from an older checkout where `TURBO4_0=44`, and mislabelled every type.
At `fca3093c9` it's `TURBO2_0=43, TURBO3_0=44, TQ3_1S=45, TQ4_1S=46, TURBO4_0=47`. Your
mapping in the issue is correct — mine was briefly wrong. Worth stating explicitly if the
check ever becomes a gate, since a threshold allowlist keyed on type ID would silently rot.

Raw log available if you want it. Happy to rerun once #293 merges so it's like-for-like,
or to build a target of your choosing — I only have gfx1201 and sm_75 here.
