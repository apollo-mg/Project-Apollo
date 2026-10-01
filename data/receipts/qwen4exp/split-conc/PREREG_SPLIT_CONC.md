# Pre-registration: fully resident Flash-Next on 4x P100 -- layer vs tensor split, and what parallel streams buy

**Registered 2026-10-01, before any row.** Mark: "Is it the sparsity of Flash-Next that makes it perform better in layer vs
tensor splitting?" and "Is the bottleneck conducive to running parallel sessions, or would it just proportionately
decrease per slot?" Then: "let's go ahead and finish out those last tests."

**Prior art checked:** `ledger_precheck.py "Flash-Next tensor split layer split concurrent streams np"` -> receipts found:
- `qwen4exp/RESULT_HCKV_SPEED.md` (09-02/03): Flash-Next under `-ncmoe 44` with tensor split ran 4 GPUs 28 % *slower*
  than 2 (8.16 -> 5.88 tok/s). The fully resident 27B gained (+6 %, +17 % with MTP).
- `np4-vram/NOTE_NP4_MMVQ_LIMIT.md` (09-30): on the 27B, streams x (1 + draft) > 8 fails (HTTP 500), and up to 4
  streams scaled 21.7 -> 35.1 tok/s total at draft 1.
- `qwen4exp/RESULT_FLASHNEXT_RESIDENCY.md`: fully resident UD-Q2 with layer split runs ~21 tok/s.
- Tensor split is denied for qwen4exp upstream (NaN logits). buun re-admitted it on 09-10.

**What this adds:**
- the first layer-vs-tensor comparison with Flash-Next **fully resident**;
- the first concurrency measurement on Flash-Next;
- whether the 8-token limit holds for a MoE (`MUL_MAT_ID`) model.

## Instrument

- **Host and build:** .194, 4x P100 at 150 W / 1063 MHz (read back), buun `0b2789f23`. Flash-Next UD-Q2_K_XL
  (`-ngl 99`), `-c 16384 -np 4 -fa on -fit off`, f16 KV, thinking off. MTP: `-md mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf
  --spec-type draft-mtp --spec-draft-n-max 3`.
- **Page-fault control** (`sm60-types/NOTE_WARMUP_DIAGNOSIS.md`): the per-layer embedding shard (`...-00002-of-00003`)
  is read to /dev/null after each server start. Every cell runs two passes; **pass 2 is the measurement.**
- **Cells,** each on a fresh verified server (own log loaded, `/props` file, 49/49 on GPU):

| cell | split | MTP | streams |
|---|---|---|---|
| L0 | `-sm layer -ts 1,1,1,0.6` | off | 1, 2, 4 |
| L3 | `-sm layer -ts 1,1,1,0.6` | draft 3 | 1, 2, 4 |
| T0 | `-sm tensor` | off | 1, 2, 4 |
| T3 | `-sm tensor` | draft 3 | 1, 2, 4 |

- **Streams:** N parallel requests with 4 distinct fixed prompts, 256 tokens each, temp 0. Aggregate = tokens / wall.
- **Tensor-split correctness gate** (upstream's NaN history): at temp 0, thinking off, the reply to "Count from 1 to 20"
  must contain exactly 1..20, and the first 64 tokens of one fixed prompt must match L0's. A failure marks the cell
  invalid and its speed is not reported.

## Predictions (`analyze_split_conc.py`)

| # | claim | rule | confidence |
|---|---|---|---|
| S1 | **Parallel streams pay** (layer, MTP off) | aggregate at 4 streams >= 1.6x one stream | 0.6 |
| S2 | **The 8-token limit holds for MoE** | L3 at 4 streams (16 tokens/step): any request fails, or aggregate < L3 at 2 streams | 0.6 |
| S3 | **Even fully resident, tensor split loses at one stream** | T0 single stream < L0 single stream | 0.6 |
| S4 | **Tensor split gains more from streams** | T0 aggregate 4/1 ratio > L0's | 0.5 |

**Reported without a prediction:** per-stream speeds, MTP acceptance, VRAM per card, the T3 numbers.

## Deviations

Any change after the first row gets a numbered Deviation here before the affected rows run.
