# DRAFT — correction for PR #324. For Mark to review. NOT POSTED.

---

Correction to my throughput note. I said tensor split was 2.5x slower and implied that was a
property of this box. **That was wrong**, and it came from one sample on the noisiest arm.

Re-ran the historical benchmark apples-to-apples — same model (`Qwen3.8-27B-Q6_K`), same tool
(`llama-bench -ngl 99 -p 512 -n 128 -r 3`), `GGML_CUDA_ALLREDUCE=internal`, clocks pinned
1063 MHz / 150 W:

| arm | Aug 21 (different build) | today, `d929da17b` + FA patch |
|---|---|---|
| 2 GPU, `-sm layer` | 7.70 ± 0.00 | **7.83 ± 0.00** |
| 2 GPU, `-sm tensor` | 13.00 ± 0.02 | **13.20 ± 0.01** |
| 4 GPU, `-sm tensor` | 15.34 ± 0.05 | **15.83 / 15.75 / 12.80 / 12.56** |

**No regression anywhere** — the PR build matches or slightly beats every historical arm. And on
dense 27B, tensor split is ~**1.7x faster** than layer split, not slower.

## The 4-GPU arm is bistable

Four unbound runs gave two clean modes, ~12.6 and ~15.8 — not a spread. My first sample landed in
the slow one. The tell I should have chased: `llama-bench` reported `± 1.20` where the historical
run reported `± 0.05`, a 24x jump in its own error bar.

The historical script binds the 2-GPU arms with `numactl` but leaves the 4-GPU arm unbound, since
those GPUs span both sockets. Binding removes the slow mode:

| binding | tg128 |
|---|---|
| none | 12.80, 12.56, 15.83, 15.75 |
| `numactl --interleave=all` | 15.35, 14.68 |
| `numactl --cpunodebind=0 --membind=0` | 15.88, 15.21 |

4 of 4 bound runs >= 14.68; 2 of 4 unbound at ~12.6. With GPU0/1 on NUMA 0 and GPU2/3 on NUMA 1,
an unbound process lands on whichever socket the scheduler picks, which changes host-memory and
PCIe locality for the per-layer all-reduce. n=4 per condition, so suggestive rather than settled —
but enough that I'll NUMA-bind and repeat every 4-way number from here.

## What is actually true about Flash-Next

The 6.20 tok/s figure holds, but it is a property of the **model**, not the topology:

| model | `-sm layer` | `-sm tensor`, 4 GPU |
|---|---|---|
| Qwen3.8-27B (dense, 27B active) | 7.83 (2 GPU) | **15.8** — tensor wins |
| Qwen3.8-Flash-Next (MoE, **6B active**) | **15.85** | 6.20 — layer wins |

Flash-Next has ~6B active parameters and `n_ff_exp = 640`; split 4 ways that's a **160-wide
expert matmul** per device, far too small to keep a P100 busy, while still paying an all-reduce
on each of 48 layers. Tensor split trades communication for parallel compute and Flash-Next has
very little compute per layer to trade. 27B dense has ~4.5x the active parameters and
`n_embd = 5120`, so its split matmuls stay big enough to win.

So: tensor split is a solid win on dense models here and a loss on this sparse MoE. Sorry for the
noise — the mistake was one sample, on the highest-variance arm, generalised across model
families. Everything else in my previous comment (the abort, the FA mirror fix, the coherent 3-
and 4-device output, the VRAM figures) is unaffected.
