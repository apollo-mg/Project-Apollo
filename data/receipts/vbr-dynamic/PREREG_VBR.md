# Pre-registration — what dynamic VBR actually does

**2026-08-23.** New buun build `7d30a7244` on `.194` (sm_60 routing fix present, 1,474 commits
ahead of anything previously measured here).

## Correction that motivates this

The server we started as "VBR" is **not running VBR**. `/props` reports:

```
vbr: {"enabled": false, "dynamic": false, "realized_bpv": 0.0}
kv_bpv: 3.25
```

`-ctk turbo3_tcq` gives the **static codec**, not the adaptive schedule. `BACKLOG C2` records
the mirror-image trap — past runs read `kv_bpv: 16.0` and were f16 in disguise. Any receipt
calling this configuration "VBR" would be wrong.

## What the new build exposes that we have never used

- `-ct vbr` proper, with an **implicit t4 floor (4.125 bpv)**
- `--vbr-floor` / `--vbr-min-bits` — aggregate bits/value floor; the degrade order stops at the
  last step that stays at or above it, and **advertised context capacity is computed from it**
- `--vbr-vram` — VRAM budget; with `-c` unset the server **advertises `n_ctx` derived from the
  budget** rather than the reverse
- `VBR_LAYER_SCHEDULE`, `VBR_MIN_BITS`, `VBR_BUDGET_MIB` env overrides
- `/slots` exposes `kv_bpv` live, and `/props` exposes `realized_bpv` and `selected_policy`

## Questions, in dependency order

| # | question | why it must come first |
|---|---|---|
| **V1** | Does `-ct vbr` report `enabled: true`, and does `realized_bpv` **move** as the cache fills? | If it never engages, everything downstream is measuring a static codec with a different name. `C2` found exactly this failure before |
| **V2** | With `-c` unset and `--vbr-vram auto`, what `n_ctx` does it advertise on 2×P100? | This is the deployment mode the flags are designed around and we have never run it |
| **V3** | Fidelity at matched **achieved** bitrate: static `turbo3_tcq` (3.25) vs VBR floored to 3.25 | `S4` — VBR has no fixed operating point, so point comparisons against static codecs are category errors. One already produced a wrong conclusion |
| **V4** | Does `tier_cal` change under VBR vs f16 at depth? | Every "clean" verdict we hold means *not degenerate*, never *faithful*, and no fidelity metric we own can see calibration damage (`AFM-21`) |

## Predictions

| # | prediction | conf |
|---|---|---|
| W1 | `-ct vbr` engages (`enabled: true`) on this build | 0.85 |
| W2 | `realized_bpv` stays at the entry tier for short prompts and only degrades under fill | 0.75 |
| W3 | Advertised `n_ctx` under `--vbr-vram auto` exceeds 262,144 on a 32 GB pair | 0.60 |
| W4 | At matched achieved bitrate, VBR beats static `turbo3_tcq` on fidelity | 0.55 |
| W5 | `tier_cal` confabulation under VBR is within 1 item of f16 at 8k context | 0.70 |

**W4 is the one that matters** — it is the entire premise of a variable-rate codec. If VBR at a
3.25 floor is indistinguishable from static 3.25, the adaptive machinery is not buying anything
at this operating point, which would be worth telling buun plainly.
