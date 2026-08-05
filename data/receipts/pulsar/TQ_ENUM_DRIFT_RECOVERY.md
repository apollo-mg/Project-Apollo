# Recovering an unloadable TurboQuant GGUF by rewriting 432 bytes

**Node `.73`, 2× Tesla P100-PCIE-16GB (sm_60), 150 W cap. 2026-08-03.**
Companion to `TQ_ENUM_DRIFT_INTEROP.md`, which diagnosed the failure.

## What was wrong

`Qwen3.6-35B-A3B-UD-Q8_K_XL-TQ4_1S.gguf` (MarcelloG, 21.89 GiB) failed to load on every current
build with `failed to read tensor data`. Its 108 TQ tensors declare type **45**, which current
TheTom builds read as `TQ3_1S` (16 B/block), while the payload measures **20.000 B / 32 vals** —
`TQ4_1S`. The id dates from the 2026-04-01..04-03 window when the fork numbered `TQ4_1S = 45`.

## The fix

Rewrite the declared type id 45 → 46 in the tensor-info block. **No weight byte is touched** —
108 `u32` fields, **432 bytes total**, in a 21.89 GiB file.

```bash
# safety first: the whole metadata + tensor-info region lives in the first ~11 MB
dd if=model.gguf of=~/moe_header_backup.bin bs=1M count=16      # sha256 efd9fcae63acebd2
python3 ~/patch_tq_ids.py model.gguf --from-id 45 --to-id 46 --inplace
#   wrote 108 fields; remaining type 45 = 0 ; type 46 = 108
```

Post-patch layout check confirms agreement between declared type and payload:

```
type ?46    n=108
   blk.2.ffn_gate_exps.weight   ne=268435456  bytes=167772160  -> 20.000 B per 32 vals (5.00 bpw)
```

Reverting is symmetric: `--from-id 46 --to-id 45 --inplace`, or restore the 16 MiB header backup.

## Result — the file works

Loaded on `d0e2a8b64` (`-c 4096 -fa on -np 1 -ngl 99 -sm tensor`, temp 0):

> the transistor, the integrated circuit, and the laser. The transistor was invented in 1947 by
> John Bardeen, Walter Brattain, and William Shockley at Bell Labs. The integrated circuit was
> invented in 1958 by Jack Kilby at Texas Instruments and Robert Noyce at Fairchild Semiconductor.
> The laser was invented in 1960 by Theodore Maiman at Hughes Research Laboratories.

Not merely coherent — **factually correct in specifics**. Throughput **29.64 / 29.83 / 29.94 t/s**,
`cuda_err=0`.

**This settles the open question from the diagnosis.** Equal block size proved the *layout* matched
but not the *semantics* — the WHT rotation and Lloyd-Max centroids could have changed since April
without changing the byte count. Correct factual output over 128 tokens rules that out: TQ4_1S
block semantics are unchanged, and the id was the only defect.

## Second, independent reproduction of the TQ4_1S regression

The same patched file on `6aa97d810` (post-#256) loads fine and runs at **the same speed** —
29.65 / 30.05 / 29.92 t/s — but emits:

> `,渣rettyheadarro brabantittルドhanaCollection DOCUM企业新闻却▷ Collec heats RokINHeton…`

So the regression documented in `TQ4_1S_PASCAL_REGRESSION.md` reproduces on a **second model** of a
**different architecture** (`qwen35moe` vs `qwen35` dense). Identical throughput with garbage output
is worth noting on its own: the fault is numerical, not a fallback to a slower path.

## Throughput context

| model | file | experts | t/s (`-sm tensor`, no MTP) |
|---|---|---|---|
| `Qwen3.6-35B-A3B-UD-IQ4_NL-MTP` | 17.26 GiB | IQ4_NL/IQ3_S mix | **47.42** |
| `Qwen3.6-35B-A3B-UD-Q8_K_XL-TQ4_1S` (recovered) | 21.89 GiB | 72×TQ4_1S + 36×Q4_K + 12×Q8_0 | **29.83** |

The TQ file is 37% slower, but this is **not** a TQ-vs-IQ4_NL comparison: it is a `Q8_K_XL` build
whose non-expert tensors are Q8_0, it is 27% larger, and under default settings its TQ4_1S experts
are additionally converted to q8_0 at load (see `TQ4_1S_PASCAL_REGRESSION.md`). It also has **no MTP
head**, so the 70.50 t/s the IQ4_NL model reaches with MTP is unavailable to it. Treat 29.83 as a
data point for this specific file, not as a verdict on TQ4_1S for MoE.

## Takeaway

A file that presented as a corrupt 21.89 GiB download was recovered by a 432-byte metadata edit.
The failure mode — declared type id drifting out from under a payload, with no provenance stamp to
detect it — is checkable in under a second from tensor offsets alone, and worth checking before
concluding any TQ GGUF is broken.

Current state on `.73`: the file is **left patched** (id 46) and therefore usable. Header backup at
`~/moe_header_backup.bin`; revert command above.
