# Pastable — GCN Vulkan sign-off for TheTom, PR #244 / adopted branch

Source: `PR244_GCN_SIGNOFF.md`. Logs on `.76` at `~/adopted_mx/` and `/mnt/usb/adopted_mx/`.

---

**GCN Vulkan sign-off — 21/21 healthy on the adopted head. The wave64 fix survived the rebase.**

Ran the 7-cell matrix against `c19884fb4` (`version: 10249` — giveen's `418cbf49b` +
your `supports_op` reconstruction `28c68fe74`), K=3, RX 580 / Polaris10 / RADV 26.1.6,
Crow-9B IQ4_XS, temp 0, 500 tokens, same methodology as #241.

| cell | gzip (identical all 3 reps) | sha | vs 9981 `11a8377bd` |
|---|---|---|---|
| kturbo4_vturbo3 | 0.4961 | `5afcafda0c5d` | ref 0.4866 |
| kf16_vf16 | 0.5097 | `ad9dd4fa776f` | **byte-identical** |
| kturbo4_vturbo4 | 0.5101 | `4a86d5f4c3f3` | ref 0.5024 |
| kturbo4_vturbo2 | 0.5021 | `0b3b5c4235d5` | **byte-identical** |
| kturbo3_vturbo3 | 0.5149 | `2cf82bbbff4a` | ref 0.5152 |
| kf16_vturbo3 | 0.5251 | `1dc38ed16d50` | ref 0.5251 (gzip exact, sha differs) |
| kturbo3_vf16 | 0.5206 | `6f6426953a0a` | ref 0.5199 |

**All 21 runs in the healthy band (≥0.45); nothing marginal, nothing corrupt.** The wave64
ballot bug produced **0.175–0.347** on turbo3 cells on this same rig, so there is a wide margin
here. The three turbo3-V cells — the ones `#243` fixed — are 0.4961 / 0.5149 / 0.5251 against
pre-rebase 0.4866 / 0.5152 / 0.5251.

Two of seven cells are byte-identical to the pre-rebase build; the other five diverge in bytes
while staying in band, which I read as 268 builds of upstream sampling/graph drift rather than
anything from the rebase. Shout if you want those five chased down — I did not.

**Every cell produced the same SHA in all three reps** (21 runs, zero variation, timings within
±1%). Worth flagging honestly: I *predicted* the f16 control would be bistable here, because
in #241 follow-up work this rig produced two distinct f16 states with cell order held fixed.
It did not reproduce — everything was stable this time. The one thing I changed that could
plausibly matter: this run wrote all server logs to a RAM overlay, where every earlier run on
this box wrote them to an exfat USB mount *during generation*. That change also stopped the
matrix from wedging the GPU. If FUSE write stalls were perturbing execution timing, and the
bistability was timing-dependent, that would explain both. **Hypothesis, not a result** — so I
would not yet describe this rig as deterministic, and I kept K=3.

One caveat on what this does and does not cover: **gzip is a degeneracy gate, not a fidelity
metric.** It catches the wave64 class of corruption with a lot of headroom, but a subtle
numerical regression that kept output fluent would pass. KLD against an f16 reference is the
instrument for that and I have not run it on the rebase — happy to if it is useful.

Setup for the record: RX 580 8 GB (Polaris10/GCN4, **subgroup 64**), RADV Mesa 26.1.6,
CachyOS live USB, Pentium G3258. Build flags `-DGGML_VULKAN=ON`,
`AVX/AVX2/F16C/FMA/BMI2=OFF`, `-march=x86-64-v2` (the G3258 has no AVX), and
`.note.gnu.property` stripped — the CachyOS toolchain stamps `x86 ISA needed: x86-64-v3` on
every locally-linked binary via `crt1.o` regardless of `-march`, so binaries built elsewhere
will not exec on that CPU without it. Noting in case anyone else tries to reproduce on
pre-AVX hardware.

`test-backend-ops -o SET_ROWS_TURBO3` still reports `0/0 tests passed → OK` on this device,
same as pre-rebase — the turbo SET_ROWS cases are gated off on Polaris, so that filter is not
a useful signal here and the e2e matrix is doing the real work. (Recorded in #241 as well; it
reads like a pass and is not one.)
