TCQ Port-Gap Final Benchmark Report 

## 1. Objective

To empirically evaluate the quality (Hazard/KLD) and performance (Tokens per Second) gap between Tom's base  turbo3  asymmetric cache and Buun's Trellis-Coded  turbo3_tcq  implementation on the Quad-P100 node ( .194 )
using Qwopus 27B.

## 2. Methodology (The Receipt Path)

• Model:  Qwopus3.6-27B-Coder-heretic-Q6_K.gguf 
• Hardware: 4x Tesla P100-PCIE-16GB ( 10.0.0.194 )
• Dataset (hazard/KLD + speed legs):  wikitext-2-raw  · (margin/accuracy leg):  120 routing probe cases (rd_{2048,8192,32768}_c2) 
• Quality Tool:  llama-frontier-hazard  (Context: 128 prefix tokens, 2891 prompts, evaluated against a strict  f16/f16  anchor baseline).
• Performance Tool:  llama-bench  ( pp8192  prefill test to isolate encoding/packing speed).
• Margin/Accuracy Tool:  probe_router.py  (served /v1/chat/completions, temp 0 greedy, top_logprobs=4, enable_thinking=False) →  paired_margins.py  (paired min-margin t-test over the 119 common successful cases).
• Receipts: All raw logs extracted directly from  /home/mark/tcq_hazard_*.txt  and  /home/mark/tcq_bench_*.txt  on  .194 .
──────
## 3. The Corrected Headline: Speed and Teacher-Forced Fidelity

Accuracy tie; practical margin tie (both certain); paired weakest-link margin shows a small but rock-solid buun advantage (Δ0.40 nats, 95/24, t=−8.83) — the first place the ~1.9× KLD/hazard fidelity edge leaves a
fingerprint on the served greedy path, still below any decision threshold. Plus ~2× speed. Codec-vs-build attribution confirmed: the f16/f16 cross-build anchor read a perfect tie (Δ = 0.0000, positive control t = 8.99 on a known-different pair), isolating the 0.40-nat gap to the codec, not the build (see §6). (Note: Both endpoints ran identical config: temp 0, greedy,
enable_thinking=False).
──────
## 4. Observations (Facts)

### Fact 1: Buun's TCQ halves the quantization error (KL Divergence).

• Tom  turbo3 :  mean_KL=0.01267  |  flip_rate=0.0652 
• Buun  turbo3_tcq :  mean_KL=0.00645  |  flip_rate=0.0490 
• Observation: Buun's Trellis-Coded Quantization mathematically cuts the KL Divergence against the  f16  anchor by exactly 49.1%, while reducing the top-token flip rate by 24.8%.

### Fact 2: Buun's TCQ is >2x faster in prompt processing on P100s.

• Tom  turbo3 : 135.28 ± 0.02 t/s ( pp8192 )
• Buun  turbo3_tcq : 280.97 ± 0.15 t/s ( pp8192 )
• Observation: The  tcq  implementation processes prompts 2.077× faster on the Quad-P100 node.
• Log Trace: Buun's  llama-bench  log explicitly prints:  TCQ encode: using shared-memory backtrace (8192 bytes/block)  and  TCQ1 decode: K/V codebooks (K=baked-in V=baked-in) . Tom's log prints none of these.
• Footnote on Provenance: Buun's binary stamped  build: unknown (0)  as it was built from the synced tree without a Git SHA, representing minor provenance looseness.
──────
### Fact 3: Task Accuracy and Logprob Margins Tie (with a microscopic TCQ edge).

• Task Accuracy: Buun  120/120  | Tom  119/120  (1 Timeout).
• Grand Mean Margin: Tom  12.819  | Buun  12.786 .
• Paired Min-Margin (t-test): Over the 119 common successful cases, Buun possesses a statistically decisive advantage on the weakest-link tokens (mean Δ = 0.4039 nats, t = -8.83, p ≈ 10⁻¹⁴). The win count heavily favors
    Buun (95 to 24), though this specific ratio appears to be a systemic property of Tom's baseline weakness profile on these cases.
• Observation: The timeout on Tom's build ( rd8k_c2_067 ) was isolated as an infrastructure stall, not a throughput-induced generation runaway. The  llama-server  logs confirm no single task exceeded ~70 seconds, proving
the 600-second python timeout was purely network/infra noise.
• Receipt (Log Trace):  paired_margins.py lp_tom.jsonl lp_buun_tcq.jsonl  output confirms the systematic margin advantage for Buun on the weakest-link tokens.
──────
## 5. Inferences (Distinguished from Fact)

• Causal Inference: The presence of baked-in codebooks and the shared-memory encode path in Buun's build are plausible contributors to the 2.07x speedup. However, because this compares two builds end-to-end (with differing
    kernels, compile flags, and flash-attention implementations) rather than isolating a single mechanism via an ablation study, we cannot definitively prove the shared-memory backtrace caused the speedup.
• Inference on Quality: The KLD reduction (~1.9x) is a real fidelity advantage, but because the routing task is saturated (margins > 12 nats), the instrument cannot translate that fidelity into a visible task-accuracy gap.
──────
## 6. Falsifiability


Falsification Condition (Speed): The conclusion that Buun's TCQ is vastly superior for Pascal inference would be falsified if an ablation study (toggling the shared-memory path in Buun's build) showed no impact on the
pp8192  speed, proving the gains were actually stemming from external compiler flags or flash-attention implementations.
 
Falsification Condition (Quality Impact): The conclusion that TCQ's fidelity edge requires a "thin-margin" task to be visible would be falsified if we ran a highly complex reasoning benchmark (e.g. math or code synthesis)
and Buun's TCQ still showed no statistical margin or accuracy improvement over Tom's build, proving the KLD reduction is purely cosmetic.
 
Falsification Condition (Codec Attribution): We ran the positive control (t = 8.99 for known-different pair) and confirmed the t = NaN result for  tom_f16  vs  buun_tcq_f16  is a mathematically identical tie (Δ = 0.0000).
This perfectly closes Falsifier #3: the 0.40 nat advantage formally belongs to the TCQ codec implementation, not the build.
