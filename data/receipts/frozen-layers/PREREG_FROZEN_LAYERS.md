# PREREG: does freezing the end layers protect "I don't know" from fine-tuning? (2026-11-23, before any training)

**The question (Altimor, Discord, 11-22):** "what about SFT with end layers frozen (ala that study on implicitly learned
introspection from SFT)". The idea: a model's sense of whether it knows something may form before the last layers,
which then turn it into words; if fine-tuning does its damage at the end, freezing the end layers might protect the
model's "I don't know".

**Prior art checked:** `ledger_precheck.py "SFT frozen layers abstention answers-only control LoRA"` -> the IDK LoRA
control (`idk-lora/RESULT_IDK_LORA.md`, P7): Granite 4.1 3B, a LoRA on all layers trained on the model's own correct
answers to questions it knew (no UNKNOWN targets), took invented-question refusal from 0.81 to 0.20. Never measured:
where in the network that drop can be made. **What this adds:** the same recipe with the adapter kept off the last
layers (and, as a size-matched contrast, off the first layers).

## Design

Model, data and recipe exactly as the IDK control (`idk-lora/train_lora.py ctrl`, PREREG_IDK_LORA arm 4): Granite 4.1
3B (40 decoder layers, all attention), 449 training examples = the model's own correct answers in M1's prompt format,
LoRA r 16 / alpha 32 / dropout 0.05 on q/k/v/o/gate/up/down, lr 1e-4 cosine, 2 epochs, effective batch 16, seed
20261017, bf16, RX 9070 XT. The only new knob is which layers carry an adapter (PEFT `layers_to_transform`); with a
LoRA every base weight is frozen anyway, so "layer frozen" here means "no adapter on that layer".

| arm | adapter on layers | layers trained |
|---|---|---|
| **FZ_BASE** | none (base model, this sitting) | 0 |
| **FZ_ALL** | 0-39 (the October control, re-run as the reference) | 40 |
| **FZ_FRZ10** | 0-29 (last 10 frozen) | 30 |
| **FZ_FRZ20** | 0-19 (last 20 frozen) | 20 |
| **FZ_LAST20** | 20-39 (first 20 frozen; same adapter size as FZ_FRZ20) | 20 |

Each adapter is converted with `convert_lora_to_gguf.py` and applied with `--lora` to the Q8_0 base on buun
`38ada0e1b` `build_rocm` (the October build), `-c 4096 -np 1`, f16 KV, fresh server per arm; M1 by
`quant-abstention/run_main.py` (240 items: 40 easy, 100 hard, 100 invented), greedy, thinking off, as the October arms.
Check before scoring an arm: the adapter GGUF holds exactly the registered layers (14 tensors per layer; 560 / 420 /
280 / 280), or the arm is void.

## Measures

Grading as `idk-lora/analyze_idk.py` (the bare-answer rule of Deviation 2). **Primary:** r(arm) = share of the 100
invented items refused. Drop D(arm) = r(FZ_BASE) - r(arm); retained share S(arm) = D(arm) / D(FZ_ALL). Paired bootstrap
over the 100 invented items, 10,000 resamples, seed 20261123 (S computed per resample).

## Predictions

- **M (manipulation check):** FZ_ALL replicates the October control: r(FZ_ALL) <= 0.40. If it fails, the run reports a
  failed replication and H1-H2 are not evaluated.
- **H1 (Altimor's question):** freezing the last 10 layers does NOT protect: S(FZ_FRZ10) >= 0.5, and D(FZ_FRZ10)'s 95 %
  interval excludes 0. Confidence 0.7. Reading if it fails: "freezing the last 10 layers protects most of it".
- **H2:** freezing the last 20 does not protect either: S(FZ_FRZ20) >= 0.5. Confidence 0.6.
- **H3 (where, size-matched):** no direction predicted; reported as D(FZ_FRZ20) - D(FZ_LAST20) with its interval.
- Reported without prediction: real-question correct and wrong answers per arm (easy / hard); final training loss per
  arm (a smaller drop with a much higher loss would mean the arm learned less, not that the layers protect); FZ_BASE's
  agreement with the October base rows (same build and file).

## Limits stated now

One 3B model, one data set (short factual answers in M1's own format, so the push is on the test's home ground), LoRA
rather than a full fine-tune, one seed, greedy. "End layers" means the last 10 or 20 of 40. No claim about the
fine-tunes measured on the RL page, which are other models trained on other data.

## Amendment 1 (2026-11-23 ~14:25 EST, after the result, before any replicate)

**Why:** the result (`RESULT_FROZEN_LAYERS.md`, `c971e1d1`) rests on one training seed. Its bootstrap resamples the 100
invented items, so its intervals hold no variance from the LoRA's initialisation, dropout or batch order, and the H3 gap
(48 vs 57 of 100) could be within that. **Data seen:** the five arms above.

**The replicate:** the four adapted arms again at training seeds 1 and 2 (`TRAIN_SEED`, new in `train_lora.py`: it sets
`torch.manual_seed` -- LoRA init and dropout -- and the per-epoch batch order). The 449 training items stay the ones
drawn with seed 20261017 (checked: the same item-ID hash in every training log). Arms `FZ_<ARM>_S1`, `FZ_<ARM>_S2`;
FZ_BASE is shared (it has no adapter). Everything else as above. S and D per seed against that seed's FZ_ALL.

- **R1:** H1 replicates: S(FRZ10) >= 0.5 on both new seeds. Confidence 0.9.
- **R2:** the H3 direction replicates: D(FRZ20) > D(LAST20) (the first half does more damage) on both new seeds.
  Confidence 0.55. If it fails on either, the receipt states the first-vs-last-half difference as not established.
- Reported: per-seed invented declined for every arm, and the mean over the three seeds.
