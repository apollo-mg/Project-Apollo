# MTP costs 1.2–2.1 GB of VRAM and up to 41% of the KV budget, and the cost scales with context

**Date:** 2026-09-08 · **Node:** RX 9070 XT (16 GB) · `buun-llama-cpp/build_rocm` `3823c9eb6`
**Model:** `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf`, 9.73 GiB (inline MTP head at `blk.64`)
**Method:** same GGUF, same flags, **only `--spec-type draft-mtp` varies**.
`-ngl 99 -np 1 -fa on --kv-unified -ctk vbr -ctv vbr --vbr-floor t2 --vbr-vram auto`
**Raw:** `spark_raw/mtp_vram.log`, `spark_raw/mtp_vram.sh`

## Result

| context | VRAM off (MiB) | VRAM on (MiB) | **MTP cost** | KV budget off | KV budget on | **KV lost** |
|---:|---:|---:|---:|---:|---:|---:|
| 65,536 | 12,177 | 13,369 | **1,192** | 5,410 | 4,279 | −1,131 (−21%) |
| 131,072 | 12,263 | 13,778 | **1,515** | 5,384 | 3,887 | −1,497 (−28%) |
| 262,144 | 12,346 | 14,464 | **2,118** | 5,256 | 3,127 | **−2,129 (−41%)** |

Every cell fits KV at the `turbo2_tcq` floor tier.

**MTP's cost is not fixed.** The draft context is sized against the target's, so it grows from
1.19 GB at 64k to 2.12 GB at 256k — worst precisely where full context is most wanted.

Note the shape of the trade: **VRAM without MTP is nearly flat across the whole range**
(12,177 → 12,346 MiB, a 169 MiB spread over a 4× context increase) because VBR absorbs the
growth by degrading. Adding MTP moves the total by 1.2–2.1 GB and takes that directly out of
the KV budget the degrade controller has to work with.

## This explains `RESULT_DEPLOY_CONFIG_THRASH.md`

That run requested 262,144 context **with** MTP and got a 3,183 MiB KV budget, then exceeded it,
hit the `--vbr-floor`, and reset the cache 60 times.

**Without MTP the same context yields 5,256 MiB — 65% more headroom.** The 2.1 GB MTP consumes
is the margin VBR needed. The failure was not "262k is too much context for this card"; it was
"262k *plus MTP* is."

## Bearing on the 16 GB / full-context claim

Model 9.73 GiB, 262,144 context, **no MTP: 12,346 MiB total.** That is a comfortable 16 GB
claim with ~3.4 GB spare. The arithmetic holds.

**With MTP it is 14,464 MiB** — still "fits", still loads, still reports every startup line
green, and thrashes under sustained agentic load. Any 16 GB full-context claim needs to state
whether speculation is enabled, because it is the difference between 3.4 GB of headroom and
1.3 GB.

## Combined with the concurrency result

`RESULT_MTP_UNDER_LOAD.md` measured MTP at **1.40× at np=1 and 0.44× at np=8**, and traced the
collapse to the fitter's KV budget falling 4,449 → 228 MiB. This receipt is the same mechanism
from the static side: **MTP's memory cost scales with both context and slot count, and it is
always taken out of the KV cache.**

Practical rule: **budget MTP as ~1.2–2.1 GB of KV, not as free.** It shares the trunk's
*weights*; it does not share its *context*.

## Method note — the first cell failed and it was the harness

`32768 / off` reports FAILED. A prior `llama-server` was still resident when the sweep started;
the fitter's trial load hit
`vector::_M_range_check: __n (which is 1) >= this->size() (which is 1)` rather than a clean
out-of-memory error. Re-probed afterwards on a clean GPU, all four of
{f16, VBR} × {MTP on, off} load fine at `-c 8192`, `16384` and `32768`.

**Worth reporting to buun separately:** under VRAM pressure the load path raises a
`vector::_M_range_check` instead of reporting insufficient memory. That is a legible-failure
issue, not a correctness one, but it cost a debugging cycle here and would mislead anyone
sizing a config near the limit.

Also a harness bug of my own, recorded because it silently produced an empty table:
`rocm-smi --showmeminfo vram | grep used | grep -oE "[0-9]+"` returns **two** numbers (the
`GPU[0]` index and the byte count), so `$(( V / 1048576 ))` failed with an arithmetic error and
`set -u` aborted the run. Fixed with `| tail -1`.

## Desktop baseline — every figure here understates a headless card by ~2.27 GB

Measured with zero `llama-server` processes resident: **2,376,351,744 bytes ≈ 2,266 MiB** of
VRAM held by the desktop session. `--vbr-vram auto` sizes the KV budget from *remaining* memory,
so that 2.27 GB is subtracted from every budget in the table above.

| 262,144 ctx | measured here | headless estimate |
|---|---:|---:|
| no MTP | 5,256 MiB | ~7,522 MiB |
| **with MTP** | 3,183 MiB | **~5,449 MiB** |

**A headless 16 GB card running 262k + MTP would have ~5,449 MiB of KV budget — more than the
5,256 MiB that is currently running the suite cleanly without MTP.** So the thrash documented in
`RESULT_DEPLOY_CONFIG_THRASH.md` is plausibly specific to a card shared with a desktop session,
not a property of the configuration.

Untested: this is arithmetic on a measured baseline, not a headless run. It predicts that
262k + MTP works on a dedicated card and should be checked before the claim is relied on.

## Limits

One card, one model, one quant, one `--vbr-floor`. Measured at `-np 1`; the concurrency
interaction is in `RESULT_MTP_UNDER_LOAD.md`. VRAM read from `rocm-smi` at steady state after
load, which includes the ~2.3 GB desktop baseline — the **deltas** are the reliable figures,
not the absolute totals.
