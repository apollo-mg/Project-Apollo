---
name: configure-gemma4-sovereign-integration
description: Procedural integration of Gemma 4 (Dense/MoE) models into the Apollo Sovereign architecture, including thinking mode, prompt engineering hacks, and context hygiene.
---

## When to Use
Use this skill when configuring a Gemma 4 model (specifically the 26B MoE or 31B Dense variants) as the "Lead Architect" or a reasoning node in the Sovereign Engine. It is particularly useful for fixing tool-calling failures, reasoning loops, and chat template role alternation errors.

## Procedure

### 1. EOS and Template Configuration
Gemma 4 uses a specific End of Sentence (EOS) token and template structure.
- **EOS Token:** Set `<turn|>` as the primary EOS token in `llama-server`.
- **System Prompt:** Add the `<|channel>thought` token at the absolute beginning of the system prompt to enable the internal reasoning channel.
- **Prompt Ordering:** For multimodal tasks, images or audio must be placed **before** the text instruction in the prompt array.

### 2. Strict Role Alternation Fixes (CRITICAL)
Gemma 4 chat templates (Jinja) strictly enforce alternating `user` and `assistant` roles (`loop.index0 % 2 == 0`). Standalone `system` or `tool` roles often cause a `500 Internal Server Error`.
- **System Prompt Integration:** Do NOT send a standalone `{ role: 'system' }` message. Instead, prepend the system instructions to the **very first** user message in the conversation array.
- **Tool Response Mapping:** Intercept tool responses (which standard APIs send as `role: 'tool'`). Instead of a new message, wrap the tool output in XML tags (e.g., `<tool_response name="...">...</tool_response>`) and append it to the end of the **next user message** (or the previous one if the turn allows).
- **Sequence Preservation:** Ensure the final array sent to the server is strictly `[user, assistant, user, assistant, ...]`.

### 3. VRAM Optimization for RX 9070 XT (16GB)
- **31B Dense:** Requires extreme quants (`IQ2_XXS` or `IQ3_S`) to fit within 16GB while leaving room for the KV cache.
- **26B-A4B MoE (e.g., Gemopus):** Best suited for desktop use.
- **APEX Quantization:** For MoE models, prefer **APEX (Adaptive Precision for EXpert Models)** quants. APEX uses a precision gradient:
    - **Edge Layers:** (Start/End) high precision (e.g., 5+5 symmetric gradient) to preserve signal/logic.
    - **Middle Layers:** Aggressive compression to save space.
- **Importance Matrix:** Use **I-Mini** or **I-Balanced** variants (imatrix calibrated) for better reasoning in small sizes (~13GB).
- **KV Cache:** Use **TurboQuant Asymmetric KV Caching**: `-ctk q8_0 -ctv turbo4` (8-bit keys, 4-bit rotors for values). This reliably unlocks 64k context on 16GB hardware.

### 4. Multi-turn Context Hygiene
To prevent "reasoning loops," the assistant's previous reasoning blocks must be stripped from the history before the next turn.
- **Action:** Use a regex in the message formatter to remove content inside `<|channel>thought` tags.
- **Logic:** Only the final "visible" answer and tool calls should be fed back into the context window.

### 5. The "Gemma 4 Survival Kit" (Tool-Use Optimization)
- **"Low Self-Esteem" Prompt:** Instruct the model: *"You are a small model with limited world knowledge. You MUST rely on external tools to double-check everything."*
- **Time-Anchoring:** Inject the current date into the system prompt to prevent refusal of "future" tasks.
- **Schema Alignment:** Rename the `web_fetch` parameter from `prompt` to `url`. Gemma 4 has a hardcoded bias for `url`.

## Pitfalls and Fixes
- **Symptom:** `Jinja Exception: Conversation roles must alternate user/assistant/user/assistant/...`
  - **Cause:** A `system` role at the start or a `tool` role in the middle broke the alternating sequence.
  - **Fix:** Merge the offending message into the adjacent user/assistant message as text.
- **Symptom:** The model starts repeating its reasoning or gets "stuck" in a logic loop.
  - **Cause:** Previous `<|channel>thought` blocks were not stripped.
  - **Fix:** Verify the regex-stripping logic.
- **Symptom:** VRAM OOM at ~40k tokens despite 64k configuration.
  - **Cause:** ROCm memory fragmentation (common on RDNA 4).
  - **Fix:** Use a watchdog (e.g., `vram_watchdog.py`) to restart the server when free VRAM < 400MB.

## Verification
- Inspect the raw API payload; confirm it alternates `user`/`assistant` roles perfectly.
- Run a tool-calling turn and verify the tool response is wrapped in XML inside a user message.
- Monitor VRAM usage during long sessions; confirm `turbo4` rotors are keeping the footprint stable.
