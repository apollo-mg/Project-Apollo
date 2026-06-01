---
name: select-abliterated-models
description: Selection criteria for uncensored (abliterated) models to prevent reasoning degradation.
---

## When to Use
Use this skill when selecting or recommending an uncensored (abliterated) model for the "Lead Architect" or "Engineer" roles in the Sovereign Entity Architecture.

## Procedure
1. Search Hugging Face for the target model (e.g., Gemma 4, Qwen 3.5).
2. Prioritize models using **ARA (Arbitrary-Rank Ablation)** or **Orthogonalized Representation Ablation** over basic fine-tuned versions.
3. **Check the Model Card for KL Divergence:**
   - A **low KL Divergence score** (relative to the base model) indicates a surgical removal of refusals without "brain damage" (loss of reasoning or coding logic).
   - Avoid models with high KL Divergence or those that report significant degradation in benchmarks (HumanEval, MMLU).
4. **Quantization Preference:** 
   - Favor **Unsloth-quantized GGUF** models (especially Q4_K_M or Q8_0) for RDNA 4 hardware to maximize context window while maintaining reasoning fidelity.
5. **Verify Mixture of Experts (MoE) Specs:**
   - Confirm active parameters per token (e.g., 4B active for a 26B model) to ensure the hardware can handle the inference speed.
6. **Prefer Expert-Pruned MoE Models (REAP):**
   - **Mechanism:** Models pruned via **REAP (Router-weighted Expert Activation Pruning)** have redundant or "noisy" experts removed while maintaining the same number of active parameters per token.
   - **Benefit:** These models (e.g., Gemma 4 21B) are smaller on disk and VRAM but often show **improved benchmark scores** in complex tasks (Math, CS) because the router is no longer distracted by low-signal experts.
   - **TPS Gain:** Pruned models can significantly increase generation speed (often 5x faster on consumer GPUs) compared to their full-expert counterparts.

## Pitfalls and Fixes
- **Symptom:** Model repeats phrases endlessly or fails simple coding tasks after switching to an uncensored version.
  - **Cause:** High KL Divergence or "brain damage" from a poor abliteration process.
  - **Fix:** Switch to an ARA-abliterated model variant.

## Verification
1. Run a sample coding task (e.g., "Write a Python script to check VRAM temperature via rocm-smi").
2. Run a "refusal probe" (e.g., "Explain how to bypass a software abstraction").
3. Successful models will provide the explanation without refusal while maintaining correct code syntax.
