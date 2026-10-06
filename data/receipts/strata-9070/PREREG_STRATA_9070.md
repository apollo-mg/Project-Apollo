# Pre-registration: how fast is Strata (adaptive expert cache + CPU-in-place experts + MTP) on a 16 GB RX 9070 XT with 31 GB of RAM, measured like a LocalMaxxing row, and how much is the MTP?

**Registered 2026-10-05 ~21:20, before any timed row.** Mark: "the model itself is insignificant, we can adapt the
tech to any model."

**The engine:** `Niko1221/Strata` v0.1.39 (`6f32ec0`), built here for gfx1201 against system ROCm 7.2.
- **Pack:** its installer's choice for 31 GB of RAM, the Coder `ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-Coder-GGUF`
  IQ1_M (2 shards, 58.4 GB).
- **Mode:** low-RAM. The GPU holds ~47 % of the experts and the rest stay in RAM. KV is int8 in VRAM (KV streaming is
  off, RAM too small).
- **Strata's own claim for this card and pack:** 44 tok/s answers (4K) and 1,420 tok/s prompts (32K), on their 47 GB
  RAM machine with engine 0.1.26.

**Prior art checked:** `ledger_precheck.py "Flash-Next GSQ-RCO Coder IQ1_M decode tok/s desktop 9070 expert
streaming"` -> receipts found:
- **INDEX L186:** the Coder loses 30.4 pp IKP and its fabrication goes 14 -> 52 % against its unpruned parent;
  HumanEval+ is unchanged. Quality is not re-tested here.
- **L49 / L50:** GSQ-RCO decode on P100s with llama.cpp (21 tok/s with the HC Q8 conversion) and the mmvf kernel.
- **expert-spill-cost-curve (memory):** static `-ncmoe` spill cost on .194.
- **What this adds:** the first measurement here of an engine with an ADAPTIVE expert cache plus CPU computing in
  place, on a consumer card short of RAM, with the leaderboard's own tool.

## Instrument

- **Measurement:** `lmx` v0.1.48 (official binary), `speed-test run llama.cpp --mode remote` against Strata's
  OpenAI API.
  - Canonical prompts: **code-v1** (the Coder's domain) and **reasoning-v1**.
  - 1 warmup + 3 timed requests, median; temperature 0, 256 output tokens.
  - Requests go through `gemma4-9070-spec/g4_proxy.py`, which records the evidence and does no timing.
- **Thinking off:** Strata's shared setting `{"reasoning_effort": "none"}` (the file its chat page writes,
  `strata-coder-iq1_m.shared-settings.json`). The server applies it to requests that set no effort of their own.
- **Server per arm:** fresh start, ready when `/health` reports `"loaded": true`. Free RAM and VRAM are recorded
  after load.
- **Gates:**
  - captured `content` is non-empty (thinking really off);
  - 256 completion tokens;
  - the server answered from the Coder pack (the `/health` model name).

## Arms

| arm | change |
|---|---|
| **S_code** x2 fresh starts | installer config, code-v1 |
| **S_reason** x1 | installer config, reasoning-v1 |
| **S_nomtp** x1 | `--spec 1` and no `--mtp` (the source's no-speculation path), code-v1 |
| **L_code** x1 | upstream llama.cpp b11433 on the same two GGUF shards, code-v1, thinking off, `-ngl 99 -fa on` with `-ncmoe` set to the most expert layers on the CPU that fit 16 GB, `-c 8192`. If it cannot load or run in 31 GB of RAM, it is reported as failed with the reason. |

## Predictions

| # | claim | confidence |
|---|---|---|
| P1 | S_code decode is 30-50 tok/s (Strata claims 44 with more RAM) | 0.55 |
| P2 | MTP is worth at least 1.4x (S_code / S_nomtp) | 0.6 |
| P3 | Strata at least 3x llama.cpp's static offload on the same files (S_code / L_code), or L_code fails | 0.6 |

## Reporting

- Every arm's median, samples, TTFT and prompt tokens are reported, with draft counts where Strata exposes them.
- The comparison with Strata's README figure is context only: their method is different (4K answers).
- **Nothing is submitted without Mark's OK.**

## Not tested

- Quality (see L186).
- Other packs.
- Long contexts.
- Batching.
- The P100 path (a later campaign).

## Deviations

Any change after the first timed row gets a numbered Deviation here before the affected rows run.
- **Incident (10-05 21:33, not a deviation):** a global kernel OOM during S_code_r1's run.
  - Strata had ~24 GB resident with 7 GB available, while Mark was using the desktop.
  - The OOM killed the Claude CLI (Konsole) and Spectacle. S_code_r1 lost its measurement (no LMX output) and S_code_r2
    failed at start.
  - S_reason ran cleanly afterwards: 65.5 tok/s, TTFT 1,874 ms, content gate passed.
  - The S_code arms are to be rerun only with RAM headroom: with Mark away, or under a declared RAM budget. A budget
    becomes a numbered Deviation before its rows.
