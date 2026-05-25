# Gemma 4 Integration & Optimization Guide

This guide compiles essential tips, tricks, and architectural requirements for integrating Google's Gemma 4 models (both Dense and Mixture-of-Experts variants) into the Apollo Sovereign Engine, based on Unsloth's day-0 documentation.

## 1. Model Variants & Architecture
Gemma 4 introduces a mix of dense and Mixture-of-Experts (MoE) models:
*   **E2B & E4B (Dense + PLE):** Smallest variants (2B and 4B). Support **Text, Image, and Audio**. Optimized for edge devices (phones/laptops).
*   **26B-A4B (MoE):** Features **4B active parameters**. Supports **Text and Image**. Offers the best speed/quality tradeoff for desktop use.
*   **31B (Dense):** The strongest model in the family. Supports **Text and Image**. Higher quality but slower inference than the 26B MoE variant.

## 2. Key Features & Capabilities
*   **Context Window:** 128K for E2B/E4B; **256K** for 26B-A4B/31B.
*   **Multilingual:** Supports 140+ languages.
*   **Multimodal:** E2B and E4B are the only variants supporting **Audio** (up to 30s). All variants support images and video (up to 60s at 1fps).
*   **License:** Released under **Apache-2.0**.

## 3. "Thinking Mode" (Reasoning Control)
Gemma 4 includes an explicit internal reasoning channel that behaves differently from DeepSeek R1 or Qwen.
*   **How to Enable:** Add the token `<|think|>` at the very start of the **system prompt**.
*   **Behavior:** When enabled, the model outputs its reasoning inside `<|channel>thought` blocks before the final answer.
*   **CRITICAL TRAP:** For multi-turn chat, **do not** feed prior thought blocks back into the history. Only keep the final visible answer to avoid confusing the model. Apollo's `llm_interface.py` must regex-strip `<|channel>thought...` blocks before appending to the context window.

## 4. Hardware Requirements & VRAM Constraints
*   The 26B-A4B (MoE) and 31B (Dense) variants both feature a massive 256K context window.
*   **RX 9070 XT Constraints (16GB VRAM):** A 4-bit quant (like Q4_K_M) of the 31B dense model requires **~17-20 GB of VRAM** just to load. To fit the 31B dense model into 16GB while leaving room for the context cache, we must stick to extreme quants (IQ2_XXS / IQ3_S).

## 5. Recommended Settings & Formatting Quirks
*   **Sampling:** Temperature = `1.0`, Top_p = `0.95`, Top_k = `64`.
*   **EOS Token:** The End of Sentence token is `<turn|>`. Ensure `llama.cpp` and the Python backend are configured to listen for this to prevent infinite hallucination.
*   **Context:** Start with 32K for responsiveness before scaling up.

## 6. Multimodal Prompting
*   **Order Matters:** Always place **images or audio before the text instruction** in the prompt array.
*   **Visual Token Budgets:** Use variable budgets based on the task:
    *   `70-140`: Captioning/Classification.
    *   `280-560`: General UI reasoning/Charts.
    *   `1120`: OCR, document parsing, and small text.
*   **Audio Note:** Only E2B and E4B support audio. 26B and 31B dropped audio support to maximize reasoning/vision parameters.