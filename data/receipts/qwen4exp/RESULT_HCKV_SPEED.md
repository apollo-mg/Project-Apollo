# Flash-Next tensor-split throughput: buun's fork is ~35 % faster, and 4 GPUs is slower than 2

**2026-09-02.** `.194`, 4x P100 sm_60 @ **150 W / 1063 MHz under load**, dual Xeon E5-2650 v3,
64 GB DDR4-2133. Model `Qwen3.8-Flash-Next-UD-Q2_K_XL` (73.5 GiB, `head_count_kv = 2`).

Flags pinned across every leg:

```
-c 8192 -ngl 99 -fa on --jinja -np 1 -fit off -ncmoe 44 -sm tensor
GGML_CUDA_ALLREDUCE=internal
/completion, n_predict 128, temperature 0, cache_prompt false
```

Fresh `llama-server` per leg (AFM-26: uptime silently degrades throughput). K=3 per leg.

## Decode throughput (tok/s)

| fork | devices | NUMA | rep 1 | rep 2 | rep 3 | **steady** |
|---|---|---|---|---|---|---|
| **buun** `7a918624b` | 2 | — | 7.86 | 8.16 | 8.16 | **8.16** |
| **buun** | 4 | — | 5.76 | 5.89 | 5.88 | **5.88** |
| **buun** | 4 | interleave | 5.77 | 5.89 | 5.91 | **5.90** |
| **Tom** `0629f920e` | 2 | — | 3.68 | 6.06 | 6.06 | **6.06** |
| **Tom** | 4 | — | 3.56 | 4.55 | 4.52 | **4.54** |
| **Tom** | 4 | interleave | 2.81 | 4.50 | 4.49 | **4.49** |

## Three findings

### 1. buun's fork is ~35 % faster on identical inputs

**8.16 vs 6.06** at 2 devices (+34.7 %), **5.88 vs 4.54** at 4 devices (+29.5 %). Same model file,
same flags, same box, same quant, same split mode, back to back. Both trees carry TurboQuant; the
difference is whatever buun's qwen4 optimisation series (`97474a38b`, +9,948 lines) does that
Tom's upstream import of PR #27742 does not.

This is a *decode* difference, not load or prefill — prompt throughput is comparable (~11–12 t/s
steady on both).

### 2. Four GPUs is SLOWER than two, on both forks

**−28 % on buun** (8.16 -> 5.88), **−25 % on Tom** (6.06 -> 4.54). Reps are within ±0.3 %, so this
is structural, not the AFM-28 bistability.

~~Mechanism is the dual-socket topology ... every butterfly reduction cross QPI.~~
**RETRACTED 2026-09-02 — measured and false. See "The QPI mechanism is wrong" below.**

**Practical consequence for this fleet: for Flash-Next, use 2 GPUs, not 4.**

### 3. NUMA interleaving does not recover it

buun 5.88 -> 5.90, Tom 4.54 -> 4.49. Within noise both ways.

**Caveat on this arm, stated because it weakens the conclusion:** `numactl --interleave=all`
spreads pages across both nodes; it does not *localise* anything. For a single process spanning
both sockets there is no clean bind, so this tests "does interleaving help" and answers no. It
does **not** test whether socket-local placement would help, which would need one server per
socket rather than one spanning both. That is the real experiment and it was not run.

Note this does not contradict AFM-28, which was about a **bimodal** slow/fast mode
(12.80 / 12.56 / 15.83 / 15.75 on one binary). No bistability appeared here at all — every leg is
tight — so there was no slow mode for binding to remove.

## Method note: discard rep 1

Rep 1 is slower in **6 of 6 legs**, sometimes drastically (Tom 2-dev: 3.68 then 6.06, 6.06 — a
65 % jump). `cache_prompt` was false, so this is not prefix caching; it is warm-up on a freshly
started server. Reporting a K=1 number here would have understated Tom's fork by up to 39 %.

**K=3 with rep 1 discarded is the minimum shape for a throughput claim on this fleet**, and the
first-request penalty should be reported rather than averaged away.

## Not claimed

Only one model, one quant, one context length, one `-ncmoe` value. The +35 % fork gap is measured
on Flash-Next under heavy MoE offload; it is not a general claim about either tree. No quality
comparison was made — all six correctness arms produced coherent text
(`RESULT_HEADCOUNTKV_FALSIFIED.md`), but coherent is not the same as equal.

---

# MTP scaling on Qwen3.8-27B-Q6_K — and device count flips sign vs Flash-Next

**2026-09-02.** Same box, buun `7a918624b`, `-c 8192 -ngl 99 -fa on --jinja -np 1 -fit off
-sm tensor`, **no `-ncmoe`** (dense, fully GPU-resident). MTP is built into this GGUF
(`qwen35.nextn_predict_layers = 1`), so `--spec-type draft-mtp --draft-max 3` needs no sidecar.
K=3, `cache_prompt false`, fresh server per leg.

| arm | devices | MTP | VRAM (MiB) | spread | tok/s | steady |
|---|---|---|---|---|---|---|
| mtp_off_2 | 2 | off | 10739 / 10739 | **1.00** | 13.18 / 13.19 / 13.17 | **13.18** |
| mtp_on_2 | 2 | **on** | 11309 / 11309 | **1.00** | 22.59 / 22.64 / 22.60 | **22.61** |
| mtp_off_4 | 4 | off | 5583 x4 | **1.00** | 14.58 / 14.65 / 12.84 | **~14.0** |
| mtp_on_4 | 4 | **on** | 5961 x4 | **1.00** | 25.85 / 26.79 / 26.74 | **~26.5** |

## 1. MTP is worth 1.7-1.9x, and scales slightly better on more devices

- 2 GPUs: 13.18 -> 22.61 = **1.72x**
- 4 GPUs: 14.0 -> 26.5 = **1.89x**

Costs ~570 MiB per device (10739 -> 11309 at 2 dev; 5583 -> 5961 at 4 dev) — cheap for the return.

## 2. Device count flips sign between the two models

| model | placement | 2 -> 4 devices |
|---|---|---|
| Flash-Next Q2_K_XL | `-ncmoe 44`, experts on CPU | **8.16 -> 5.88 = −28 %** |
| Qwen3.8-27B Q6_K | fully GPU-resident | **13.18 -> 14.0 = +6 %** (off), **22.61 -> 26.5 = +17 %** (on) |

Same box, same split mode, same fork, opposite direction. The Flash-Next result was **not** a
property of tensor split or of the dual-socket topology per se — it is what happens when
`-ncmoe 44` leaves so little per-device compute that QPI-crossing reduction dominates. Give the
GPUs real work (a dense model resident in VRAM) and the extra devices pay.

**Correcting the earlier reading in this receipt:** "for Flash-Next on this fleet, use 2 GPUs"
stands, but the generalisation implied by the mechanism paragraph — that 4-way costs more than it
returns on this topology — does not. It costs more *when the model is MoE-offloaded*. That is a
narrower claim and the 27B arms are the counter-example.

## 3. Cross-check against `.73`

`.73` serves this exact model+quant with MTP and tensor split on 2 P100s and was measured at
~24 tok/s. Here: **22.61 tok/s** on 2 P100s. Consistent within the difference in `-c` and prompt.
The wake-on-demand box is configured about as well as it can be for this model; a 4-GPU host would
buy ~17 %, which is not obviously worth losing S3 suspend over.

## Anomaly recorded

`mtp_off_4` rep 3 read **12.84** against 14.58 / 14.65 — a 12 % drop with no config change. Only
such outlier in 24 measurements today. Consistent in shape with AFM-28 bistability on this
NUMA-unbound box. Not investigated; recorded so the "steady" figure for that one arm is treated as
softer than the others.

---

# Flash-Next MTP — my mechanism was backwards, and the pre-stated falsifier is what happened

**2026-09-02.** buun `7a918624b`, `Qwen3.8-Flash-Next-UD-Q2_K_XL` +
`mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf` (2.60 GiB, `nextn_predict_layers = 1`,
`nextn_shared_target_tensors = True`, `block_count = 49`). Flags as the rest of today:
`-c 8192 -ngl 99 -fa on --jinja -np 1 -fit off -ncmoe 44 -sm tensor`, `--draft-max 3`.

| arm | devs | MTP | VRAM (MiB) | spread | tok/s | steady | speedup |
|---|---|---|---|---|---|---|---|
| fn_off_2 | 2 | off | 4885 / 4519 | 1.08 | 7.38 / 7.91 / 7.91 | **7.91** | — |
| fn_on_2 | 2 | **on** | 6557 / 8271 | 1.26 | 9.87 / 10.30 / 10.42 | **10.36** | **1.31x** |
| fn_off_4 | 4 | off | 3521 / 3521 / 3425 / 3059 | 1.15 | 5.59 / 5.82 / 5.82 | **5.82** | — |
| fn_on_4 | 4 | **on** | 4781 / 3933 / 3837 / 6399 | **1.67** | 7.88 / 8.36 / 8.30 | **8.33** | **1.43x** |

Draft acceptance **0.752 / 0.745** — MTP engaged properly; this is not a "speculation didn't fire"
result.

## Prediction scoring — the mechanism was wrong

| # | claim | conf | actual |
|---|---|---|---|
| P1 | speedup **exceeds** the 27B's 1.72x at 2 dev | **0.70** | ❌ **1.31x < 1.72x** |
| P2 | speedup > 2.0x at 2 dev | 0.55 | ❌ 1.31x |
| P3 | 4 dev still slower than 2 with MTP on | 0.75 | ✅ 8.33 < 10.36 |
| P4 | sidecar loads, MTP engages | 0.80 | ✅ acceptance 0.75 |

I predicted MTP would help **more** under CPU offload, reasoning that a forward pass dominated by
a fixed expert-fetch cost would verify 3 drafted tokens for nearly the price of 1. The pre-stated
falsifier was: *"if MTP gives less than 1.72x here, the bottleneck is something that scales with
drafted tokens too."* That is exactly what happened.

**Why the model was wrong:** expert fetch is not a fixed per-pass cost. Different tokens route to
**different experts**, so verifying k drafted tokens touches up to k times as many expert tensors,
each pulled over PCIe from host memory. Speculation amortises GPU math; it does not amortise
host-memory expert traffic. MoE offload is close to the worst case for it.

| model | placement | MTP speedup (2 dev / 4 dev) |
|---|---|---|
| Qwen3.8-27B Q6_K | fully GPU-resident | **1.72x / 1.89x** |
| Flash-Next Q2_K_XL | `-ncmoe 44`, experts on CPU | **1.31x / 1.43x** |

**Practical rule: speculative decoding pays roughly twice as well on a model that fits in VRAM as
on one whose experts are offloaded.** When choosing between a bigger offloaded model and a smaller
resident one, MTP tilts the trade further toward resident than raw tok/s alone suggests.

## Side finding: the MTP sidecar is placed unevenly

VRAM spread degrades with MTP on — 1.08 -> 1.26 at 2 devices, 1.15 -> **1.67** at 4
(4781 / 3933 / 3837 / **6399**). The draft model appears to land largely on one device rather than
being split with the target. Harmless at this size, but it is 2.6 GiB of imbalance that would
matter on a tighter VRAM budget, and it partially undoes the even placement tensor split exists to
provide.

## Standing: 4 devices still loses on this model

8.33 vs 10.36 with MTP on. MTP narrowed the gap (−28 % without -> −20 % with, as predicted in P3)
but did not close it. For Flash-Next under heavy MoE offload on this fleet, **2 GPUs remains the
right answer, with or without MTP**.


---

# The QPI mechanism is wrong — measured, not argued

I attributed the 4-device penalty to cross-socket QPI traffic **twice** in this receipt, on the
strength of the topology matrix:

```
        GPU0  GPU1  GPU2  GPU3          P2P:   GPU0  GPU1  GPU2  GPU3
GPU0     X    PHB   SYS   SYS           GPU0    X    OK   TNS   TNS
GPU1    PHB    X    SYS   SYS           GPU1   OK     X   TNS   TNS
GPU2    SYS   SYS    X    PHB           GPU2  TNS   TNS     X    OK
GPU3    SYS   SYS   PHB    X            GPU3  TNS   TNS    OK     X
```

`TNS` = Topology Not Supported: there is **no P2P at all** across sockets, so cross-island traffic
must stage GPU -> host RAM -> QPI -> host RAM -> GPU. That looked like a decisive mechanism.

**It contributes nothing measurable.** Same device count, same model (Qwen3.8-27B-Q6_K, fully
GPU-resident, no `-ncmoe`), same flags, only the pair changed:

| pair | P2P | tok/s | 
|---|---|---|
| 0,1 same socket | **OK** | 13.18 / 13.18 / 13.17 |
| **0,2 cross-socket** | **TNS** | **13.19 / 13.20 / 13.20** |
| 2,3 same socket | OK | 13.20 / 13.21 / 13.22 |

Within 0.2 %. Losing P2P entirely costs nothing at this scale.

## The mechanism that actually fits every measurement

It is the ratio of **per-device compute to per-reduction overhead**, and nothing to do with where
the devices sit.

| model | placement | GPU-bound? | 2 -> 4 devices |
|---|---|---|---|
| Qwen3.8-27B Q6_K | fully resident | yes | **+6 %** (13.18 -> 14.0) |
| Flash-Next Q2_K_XL | `-ncmoe 44`, experts on CPU | **no — host-bound** | **−28 %** (8.16 -> 5.88) |

With 44 of 48 MoE layers on the CPU, Flash-Next decode is dominated by host-memory expert fetch.
The GPUs are not the bottleneck, so splitting the remaining work across four devices instead of two
adds synchronisation to a pipeline that is waiting on RAM. The 27B has real resident work, so the
extra devices pay.

This also explains the MTP result in the section above: speculation failed to amortise on
Flash-Next (1.31x vs the 27B's 1.72x) for the same reason — the binding cost is host expert
traffic, and neither more GPUs nor more drafted tokens reduce it.

## Consequence for placement heuristics

A smart-placement algorithm on this box should **not** key on NUMA/P2P topology — that was the
intuitive lever and it is inert. It should key on **whether the GPUs are the bottleneck at all**:

- model fits VRAM -> add devices, they help
- experts offloaded to host -> **use the fewest devices that fit**, because every extra device is
  pure synchronisation cost against a host-bound pipeline

The interesting corollary is that the second island is not wasted by being idle — it is wasted by
being *used*. For an offloaded model, `{0,1}` running one instance and `{2,3}` running a second
independent instance would beat one instance spread across all four.

---

## 2026-09-03 addendum — this configuration is now refused

`-sm tensor` on **qwen4exp (Flash-Next)** was added to the `llm_arch_supports_sm_tensor` deny list
by upstream PR **#27941** (Daniel Han, 2026-09-01 10:22 UTC, `36b101543`), carrying the comment
`// TODO: fix test-llama-archs`. It reached buun's master via the later upstream sync, *after* the
commit this run used (`7a918624b`, 2026-09-01 23:40 UTC). Current buun and current upstream both
refuse the config with `LLAMA_SPLIT_MODE_TENSOR not implemented for architecture 'qwen4exp'`.

**Unaffected:** `deepseek4` and `qwen35` are NOT on the deny list. All DS4 tensor-split work and
all Qwen3.8-27B work stand, and 27B `-sm tensor` was re-verified working on 2026-09-03.

**What still stands here:** the measurements are accurate records of what that binary did, and any
*falsification* they carry is permanent -- a rule shown false is not made true by a later gate.

**What does not:** the numbers describe a configuration no one can run today, so they are
historical, not a basis for recommendation. And any positive reading of "tensor split works on
Flash-Next" is weaker than it appeared at the time: upstream had already concluded the path fails
`test-llama-archs`, and on 2026-09-03 the same path was found to **segfault deterministically** in
`ggml_backend_meta_graph_compute` on a prefix-extension prompt
(see [RESULT_META_BACKEND_SEGFAULT.md](RESULT_META_BACKEND_SEGFAULT.md)). Coherent output on
independent prompts did not mean the path was correct -- it meant the bad case had not been reached.
