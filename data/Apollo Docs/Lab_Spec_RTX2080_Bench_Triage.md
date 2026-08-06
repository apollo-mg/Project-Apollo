# Lab Spec — RTX 2080 Bench Triage (and the dp4a question)

**Status:** ready to run when the bench station is assembled
**Hardware:** bench PSU + spare mobo/CPU/RAM, RTX 2080 (provenance: came in the ex-Alienware
that became `.73`; **suspected malfunctioning** — triage is step 0, not an afterthought)

## Why this card matters more than it looks

Two independent decisions hang off one afternoon of bench time:

1. **The dp4a question.** The P100 is `sm_60`, which **lacks the `dp4a` int8 dot-product
   instruction** (it first appears on `sm_61`). Every quantized matmul on our fleet therefore
   takes a slower path than the same kernel on almost any later card. The RTX 2080 is `sm_75`:
   it has dp4a *and* tensor cores. Running the same quant on both isolates how much of the
   P100's quantized throughput deficit is the missing instruction versus raw bandwidth.
   That is the number that decides whether buying **more sm_60** (the SYS-1028GQ-TRT at
   $179.99 + P100s at $79.99) is investment or sunk-cost.
2. **Funding.** A working 2080 is worth roughly the price of the Supermicro. A dead one is
   worth knowing about before it is counted as an asset.

## Step 0 — Triage before benchmarking (do not skip)

A suspected-bad GPU that *appears* to work will produce plausible, wrong numbers. Establish
correctness first; only a card that passes earns a benchmark.

```bash
nvidia-smi -q | grep -iE 'product name|serial|vbios|ecc|retired|remapp|xid'
dmesg | grep -iE 'nvrm|xid|nvidia'      # Xid errors = hardware fault, stop here
./build/bin/test-backend-ops            # correctness across every op; must be all-pass
```

`test-backend-ops` is the real gate. It compares every CUDA kernel against a CPU reference —
a card with degraded VRAM or an unstable core fails here while still rendering a desktop fine.

## Step 1 — Matched A/B against the existing P100 receipts

Use the **same model, same quant, same flags** as a P100 receipt already on disk, or the
comparison is worthless. Record clocks and power on both sides
(`OPERATIONS.md §2b`; **read the LIVE clock, not the requested one**).

```bash
nvidia-smi --query-gpu=name,clocks.sm,clocks.mem,power.limit,temperature.gpu --format=csv
./build/bin/llama-bench -m <same .gguf as the P100 run> -p 512 -n 128 -r 5
```

## Step 2 — The actual experiment: does dp4a explain the gap?

Run a quant that leans on int8 dot products against one that does not. If dp4a is the
story, the **ratio between tiers** differs sharply across the two cards — a flat ratio means
bandwidth, not instructions, is the binding constraint.

| Tier | Leans on dp4a? | Purpose |
|---|---|---|
| `Q8_0` | heavily | the dp4a-sensitive case |
| `Q4_K_M` | heavily | the tier we actually deploy |
| `F16` | no | control — bandwidth-bound on both cards |

**Predictions, logged before the run (score these honestly):**

- **P-2080-1 (0.70):** 2080 beats P100 by a **larger** margin on `Q8_0`/`Q4_K_M` than on `F16`.
  That gap *is* the dp4a signature. Falsified if the speedup is flat across all three tiers,
  which would mean the P100's quantized deficit is bandwidth and dp4a is a red herring.
- **P-2080-2 (0.55):** on `F16` the two land within ~25% of each other — P100 has ~732 GB/s
  HBM2 against the 2080's ~448 GB/s GDDR6, so the P100 may well **win** the bandwidth-bound
  control despite being three years older. A P100 win here is the interesting result, not an error.
- **P-2080-3 (0.35):** the card fails triage outright (Xid errors or `test-backend-ops`
  failures) given it was pulled from a machine sold as non-working.

## Reporting

Coherence probe on every performance claim — a fast incoherent card is a broken card, and
throughput numbers from one are noise. Log clock state with every figure. If the card passes
and the dp4a signature is present, that result is publishable on its own: *"what the missing
dp4a instruction actually costs you on Pascal"* is a question a lot of P100/P40 homelabbers
have opinions about and almost no one has receipts for.
