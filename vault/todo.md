# Apollo Session Log & Task Synthesizer

## 1. Gemini CLI Architecture & The "Personality" Files
The core identity and behavioral instructions for Gemini CLI are isolated in `/mnt/TG_2TB/Projects/Apollo/engines/gemini-cli-source/packages/core/src/prompts/`.

*   **`snippets.ts` (The Blueprint):** This 63KB TypeScript file dictates the tone, safety rules, and operational guidelines.
    *   *Actionable Idea:* To give the `Qwopus` model a raw, analytical, or cynical "Lead Architect" personality, rewrite the string blocks here (e.g., "Do not apologize. Do not use conversational filler. Provide only raw logic").
*   **`promptProvider.ts` (The Assembler):** Dynamically assembles snippets, workspace structures, and `.geminirc` files into the final API payload.
*   **Experimentation Loop:** Because the local CLI is air-gapped from Google infrastructure, passing compiled prompts directly to an "abliterated" model (like Qwopus 3.5 27B v3) bypasses safety rails entirely, allowing the model to adopt extreme or hyper-efficient personas perfectly.

* Gemini CLI's tool schema may be too rigid to ever easily work with Open-Weight models. Will probably pivot to either continual development of our custom CLI file:///mnt/TG_2TB/Projects/Apollo/engines/open-multi-agent-upstream/examples/apollo_cli.ts or possibly just switch to Claude Code using our source code on disk here file:///mnt/TG_2TB/Projects/Apollo/engines/claude_code_source/src. If I recall correctly, llama-server/llama.cpp can emulate an Anthropic endpoints using OpenAI translation layers, which would solve the GUI entirely without doing much. Need to have an agent look into both options.

## 2. Open-Multi-Agent Framework: The "Soul vs System" Temperature Strategy
Temperature can be adjusted in three places within `open-multi-agent` to balance conversational creativity ("The Soul") and rigid tool-calling schemas ("The System"):

1.  **Agent Roster (`AgentConfig`):** Set directly on individual team members (e.g., `temperature: 0.2`).
2.  **Coordinator Agent:** Passed via the third argument in `runTeam()` to override the temporary orchestrator.
3.  **Direct Runner (`RunnerOptions`):** Set directly in `AgentRunner` instantiation.

**The Strategy:**
*   **The Soul (Main CLI):** Set the main `architect` profile to **0.4 - 0.6**. This provides enough entropy for creative architectural dialogue while remaining grounded enough for Qwopus 27B (which excels at schema adherence) to execute basic tools.
*   **The System (Sub-Agents):** For complex, risky refactors or bash scripts, use the `delegate_task` tool. This spins up an isolated sub-agent explicitly locked to **0.0 temperature** for infallible, robotic execution. The sub-agent finishes the task and returns a summary to the conversational main thread.

## 3. Advanced Sampling Implementation (Gemma 4 & Qwen 3.6 Support)
The `open-multi-agent` framework and the native `apollo_cli.ts` runner were massively overhauled to support Unsloth's optimal presets for deep reasoning models.

*   **Missing Parameters Added:** The `LLMChatOptions` interface in `src/types.ts` was expanded to support `frequencyPenalty`, `presencePenalty`, `topP`, `topK`, `minP`, and an `extraBody` object.
*   **Adapter Passthrough:** Both `OpenAIAdapter` and `AnthropicAdapter` were updated to successfully pass these parameters to the API for both `chat()` and `stream()` methods.
*   **Gemini CLI Sync:** These parameters (`Frequency Penalty`, `Presence Penalty`) were also exposed interactively in the Gemini CLI's `AgentConfigDialog.tsx`.
*   **Unsloth Preset Targets:**
    *   **Gemma 4 (Reasoning):** `temperature: 1.0`, `top_p: 0.95`, `top_k: 64`. Requires `<|think|>` injected into the system prompt and `chat_template_kwargs: { enable_thinking: true }` passed via `extraBody`.
    *   **Qwen 3.6 (Precise Coding):** `temperature: 0.6`, `top_p: 0.95`, `top_k: 20`, `min_p: 0.0`, `presence_penalty: 0.0`, `repetition_penalty: 1.0`.
    *   **Qwen 3.6 (General Thinking):** `temperature: 1.0`, `top_p: 0.95`, `top_k: 20`, `min_p: 0.0`, `presence_penalty: 1.5`, `repetition_penalty: 1.0`.

## 4. Apollo CLI: Profiles & Checkpoint Architecture
The `apollo_cli.ts` runner was upgraded with a persistent configuration system and real-time slash commands.

*   **`profiles.json`:** Defines specific "hats" for Apollo:
    *   `architect`: Loads `LOCAL_AGENT_CONTEXT.md` (to prevent hallucinations like `link_lists.bin`), uses Qwopus 27B, and has full write permissions.
    *   `daydreamer`: Loads `SOUL.md`, uses Qwen 3.6 MoE, and is restricted to read-only tools to ideate safely.
*   **Boot Flags:**
    *   `--profile [name]`: Boots a specific persona.
    *   `--resume [filename]`: Rehydrates context from a specific session file.
*   **Live Slash Commands:**
    *   `/save [filename]`: Dumps the current context window/tool history to a JSON file in `/chat_history/`.
    *   `/load <filename>`: Hot-swaps the current session.
    *   `/profile <name>`: Instantly swaps the system prompt, model, and tool permissions without terminating the Node.js process.

## 5. System Tools Added
*   `system_metrics` tool successfully built and integrated into the CLI loop to monitor VRAM, CPU, and RAM pressure in real-time.
