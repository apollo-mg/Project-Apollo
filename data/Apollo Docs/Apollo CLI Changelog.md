# Apollo CLI Changelog

**Current working CLI main file:** `/mnt/TG_2TB/Projects/Apollo/engines/open-multi-agent-upstream/examples/apollo_cli.ts`

---

## 🐛 Bug Tracking

### 1. Context Overflow on Large Directory Scans
*   **Date:** 4/18/2026
*   **Issue:** Asking the agent to look through folders (e.g., `recovered_source`) can cause a massive context overflow. The native `bash` tool had no guardrails, capturing megabytes of `stdout` and instantly overflowing the 64k context limit, resulting in a silent timeout error.
*   **Fix:** Implemented a hard context-protection limit in `bash.ts` by strictly truncating `stdout` and `stderr` to 100,000 characters and appending a `[TRUNCATED]` warning.
*   **Status:** ✅ **Validated** (Fixed by Gemini Pro)

> **Code Patch (`bash.ts`):**
> ```typescript
> const MAX_LENGTH = 100000 // Strict truncation to prevent context window overflow
> 
> const truncate = (str: string) => {
>   if (str.length > MAX_LENGTH) {
>     return str.substring(0, MAX_LENGTH) + `\n\n... [TRUNCATED: Exceeded ${MAX_LENGTH} characters] ...`
>   }
>   return str
> }
> ```

### 2. Agent Amnesia / Context Loss
*   **Date:** 4/19/2026
*   **Issue:** Agent loses track of conversation quickly, resulting in short, unhelpful responses. The `apollo_cli.ts` script was explicitly setting `history.length = 0` every time a turn finished, instantly deleting the entire conversation history.
*   **Fix:** Patched `apollo_cli.ts` to properly append new messages (`history.push(...result.messages)`) to the ongoing context array rather than replacing it.
*   **Status:** ✅ **Validated** (Fixed by Gemini Pro)

> **Code Patch (`apollo_cli.ts`):**
> ```typescript
> } else if (event.type === 'done') {
>   // Append the new messages generated during this turn to the existing history
>   const result = event.data as any
>   history.push(...result.messages)
> }
> ```

### 3. Sub-Agent Silent Failures
*   **Date:** 4/19/2026
*   **Issue:** The `codebase_investigator` and `delegate_task` tools were failing silently and returning empty reports. If the sub-agent threw an error (e.g., an API timeout or context budget exceeded), the internal streaming loop ignored it and returned an empty string.
*   **Fix:** Patched `codebase-investigator.ts` and `delegate-task.ts` to capture `error` events from the sub-agent's `AgentRunner` stream and explicitly throw them, ensuring the main agent is informed of why the task failed.
*   **Status:** ✅ **Validated** (Fixed by Gemini Pro)

> **Code Patch (`codebase-investigator.ts` & `delegate-task.ts`):**
> ```typescript
> for await (const event of runner.stream(history)) {
>   if (event.type === 'text') {
>     finalSummary += event.data;
>   } else if (event.type === 'error') {
>     throw event.data;
>   }
> }
> ```

### 4. Premature Turn Endings (Budget Exceeded Silencing)
*   **Date:** 4/22/2026
*   **Issue:** The agent's generation would abruptly stop mid-sentence without logging an error. This occurred when the session breached the 50k token compaction threshold set in `profiles.json`. The underlying `AgentRunner` emitted a `budget_exceeded` stream event to halt generation and protect the context window, but the CLI lacked a handler for this specific event type, causing it to fail silently and drop back to the Readline prompt.
*   **Fix:** Added an explicit `else if (event.type === 'budget_exceeded')` handler in the `apollo_cli.ts` Readline loop to catch the event and print a visible `[Context Budget Exceeded]` warning. Also explicitly wired `profile.context_strategy?.maxTokens` to the `maxTokenBudget` property when initializing `AgentRunner`.
*   **Status:** ✅ **Validated**

### 5. Auto-Compaction Amnesia (Context Strategy Bug)
*   **Date:** 4/22/2026
*   **Issue:** The `contextStrategy` auto-compaction feature (triggered at 50k tokens) was failing silently. `AgentRunner.stream()` was only applying the context strategy on subsequent turns (`turns > 1`) and, crucially, failed to return the fully compacted context to the caller. This caused the CLI to retain the full, uncompacted history, endlessly growing until VRAM exhaustion.
*   **Fix:** Refactored `AgentRunner.stream()` in the `open-multi-agent` framework to apply the context strategy on the first turn and to return the fully compacted history as `finalContext` within `RunResult`. Updated `apollo_cli.ts` to detect `finalContext` and replace its persistent history array, allowing the CLI to successfully shed old context.
*   **Status:** ✅ **Validated**

### 6. Post-Compaction Token Count (Recursive Bloat)
*   **Date:** 4/22/2026
*   **Issue:** After a successful context compaction, the CLI was reporting a massive token footprint (e.g., `[Context: ~35k tokens]`) despite the history having just been summarized. The root cause was the `prependSyntheticPrefixToFirstUser` utility in `AgentRunner.summarizeMessages()`, which blindly merged the `[Conversation summary]` string into the first user message's text block. On repeated compactions, this string grew recursively, massively inflating the token heuristic.
*   **Fix:** Removed the `prependSyntheticPrefixToFirstUser` call. The framework now injects the summary as a brand new, isolated user message directly following the original `firstUser` block, preventing recursive string concatenation and restoring accurate token counts.
*   **Status:** ✅ **Validated**

### 7. Silent Failures on Malformed XML Tool Calls
*   **Date:** 4/23/2026
*   **Issue:** The local Qwen 3.6 27B model would occasionally hallucinate malformed XML tool calls (e.g., `<function=glob>` instead of strict JSON or Hermes formats) under context pressure. The upstream `text-tool-extractor.ts` lacked the regular expressions to parse these edge cases, causing the CLI to silently drop the tool call and return an empty response.
*   **Fix:** Restored and fortified a custom `extractMalformedXMLToolCalls` parser in `src/tool/text-tool-extractor.ts`. It uses highly permissive regexes to explicitly capture `<function=name>`, `<|name|>`, and `<name>name</name>` variants that highly quantized local models occasionally slip into, ensuring the CLI accurately catches and executes (or errors on) the hallucinated tools.
*   **Status:** ✅ **Validated** (Tests passing)

---

## ✨ New Features

### 🧬 Dynamic Sub-Agent Sampling Parameter Inheritance
*   **Date:** 4/25/2026
*   **Description:** Sub-agents (`codebase_investigator`, `delegate_task`, `software_engineer`) no longer use hardcoded models (e.g., `Qwopus-27B`) and rigid sampling parameters. They now dynamically load their configuration from `profiles.json`.
*   **Implementation:**
    1. **Inheritance:** Sub-agents default to inheriting the `min_p`, `top_k`, `top_p`, `frequency_penalty`, and `extra_body` from the main `architect` (or `qwopus_coder`) profile.
    2. **Overrides:** Users can create specific blocks in `profiles.json` (e.g., `"codebase_investigator": { ... }`) to explicitly override sub-agent behavior.
    3. **Safety Defaults:** Tools requiring deterministic execution (`codebase_investigator`, `delegate_task`) safely default to `temperature: 0.0` unless explicitly overridden by their specific profile block, preventing hallucinatory search commands.

* Modified /mnt/TG_2TB/Projects/Apollo/engines/open-multi-agent-upstream/examples/apollo_cli.ts to natively parse the -p and --prompt flags.                 
                                                                                                                                                                    
  When provided, the CLI will now bypass the interactive REPL entirely, run a single-shot execution of the provided prompt, stream the model's response (including  
  full tool-call execution), and then automatically process.exit(0) when the done event is fired.                                              

### 🏛️ Delegation Economics Framework
*   **Date:** 4/23/2026
*   **Description:** Implemented an economic cost model to constrain the agent's delegation choices, solving the issue of over-delegating trivial tasks or hoarding expensive multi-turn work.
*   **Implementation:** 
    1. **System Instructions:** Injected a `DELEGATION ECONOMICS` Decision Matrix and set of Hard Constraints directly into the `architect` profile in `profiles.json`. It teaches the model the context and overhead costs of spawning sub-agents (`software_engineer`, `codebase_investigator`) versus executing tasks inline.
    2. **Reactive Telemetry:** Wired a proactive `[CONTEXT PRESSURE WARNING]` directly into the `apollo_cli.ts` streaming loop. Whenever the session footprint exceeds 70% of the profile's configured `maxTokens`, a localized system warning is pushed to the history. This acts as a "biological pain response," forcing the Sovereign Engine to delegate heavy tasks before the context window collapses.

### 🔍 Codebase Investigator Sub-Agent
*   **Date:** 4/18/2026 (~10:55PM EST)
*   **Description:** Built a hyper-specialized sub-agent tool (`codebase_investigator`) to safely explore massive codebases without bloating the main context window.
*   **Key Capabilities:**
    1.  **Read-Only Tool Registry:** Strictly limited to `bash`, `file_read`, `glob`, `grep`, and `json_parse`. It cannot edit, write, or delete files, ensuring safe exploration.
    2.  **Specialized System Prompt:** Instructed to use systematic search, ignore binaries/caches during shell searches, and return structured architectural reports.
    3.  **Hyper-Deterministic Execution:** Hard-locked to `temperature: 0.0` for infallible, robotic execution.

### 🛑 Graceful Interrupts (Ctrl+C)
*   **Date:** 4/18/2026 (~9:00PM EST)
*   **Description:** Injected an `AbortController` into the Readline loop. Pressing `Ctrl+C` now safely aborts an active LLM generation or long-running tool execution and returns to the prompt without crashing the Node process.

> **Implementation:**
> ```typescript
> let activeAbortController: AbortController | null = null
> 
> rl.on('SIGINT', () => {
>   if (activeAbortController) {
>     console.log('\n\x1b[33m[User Interrupted] Cancelling active turn...\x1b[0m')
>     activeAbortController.abort()
>     activeAbortController = null
>   } else {
>     console.log('\nExiting Apollo. Goodbye!')
>     process.exit(0)
>   }
> })
> ```

### 🚨 "Silent Exit" Bug Fix & Error Logging
*   **Date:** 4/18/2026 (~9:00PM EST)
*   **Description:** The CLI previously exited silently if the underlying `llama-server` threw an error (like a timeout or token limit). Added explicit logging for unhandled `error` events emitted by the `AgentRunner`.

> **Implementation:**
> ```typescript
> } else if (event.type === 'error') {
>   console.error(`\n\x1b[31m[Agent Error]\x1b[0m`, event.data)
> } else {
>   console.log(`\n\x1b[34m[Agent Event]\x1b[0m ${event.type}`)
> }
> ```

### 🎛️ Granular Model Parameters via Profiles
*   **Date:** 4/19/2026
*   **Description:** Exposed advanced sampling parameters (`top_p`, `top_k`, `min_p`, `frequency_penalty`, `presence_penalty`, `extra_body`) dynamically via `profiles.json`. Modified the internal `RunnerOptions` and `AgentRunner` initialization in `apollo_cli.ts` to consume these values directly from the active profile.
*   **Benefit:** Enables swapping between optimal Unsloth presets for different local models (like Gemma 4's reasoning preset vs Qwen 3.6's precise coding preset) entirely through configuration, without recompiling the CLI.

### 📝 Multiline Pasting & Native Editor Support
*   **Date:** 4/19/2026
*   **Description:** Resolved a critical UI issue where pasting multiline text into the Readline prompt would trigger multiple, overlapping LLM calls due to the `\n` characters.
*   **Fix 1 (Pasting):** Wrapped the `rl.on('line')` event in a 50ms asynchronous debounce buffer. If multiple lines are sent in rapid succession, they are seamlessly concatenated into a single cohesive prompt. The `isGenerating` flag now strictly prevents overlapping execution.
*   **Fix 2 (Composing):** Added a new `/editor` slash command. Executing this opens the user's default `$EDITOR` (e.g., `nano` or `vim`) in a temporary Markdown file. When the user saves and exits the editor, the CLI reads the multi-line file and submits the entire buffer to the active Agent Runner instantly.

### 🧠 Context Window Awareness
*   **Date:** 4/19/2026
*   **Description:** The CLI agent is now aware of its own token consumption in real-time.
*   **Implementation:** The `apollo_cli.ts` runner was updated to estimate the current context size using `estimateTokens()` before starting an active generation stream. This value is injected into `process.env.APOLLO_SESSION_TOKENS`. The `system_metrics` tool was expanded with a new `session` component flag, enabling the agent to query its active token count versus the 65,536 max limit. This empowers the agent to autonomously decide when to compact its memory or delegate heavy tasks to sub-agents.
*   **Token Estimation Fix:** The underlying `estimateTokens()` utility in `tokens.ts` was originally flawed, summing and returning the raw string character count (which caused 155k character responses to be mistakenly logged as 155k tokens). This was corrected to accurately divide the character sum by 4 to mimic standard BPE tokenization heuristics.

### 📉 Native Chat Compaction
*   **Date:** 4/19/2026
*   **Description:** Wired the framework's native `compressToolResults` and `contextStrategy` directly into `apollo_cli.ts`.
*   **Implementation:** These settings are now configurable in `profiles.json`. Both the `architect` and `daydreamer` profiles are now configured to compress large tool outputs between turns and dynamically offload to a background LLM summarization pipeline (`type: "summarize"`) when the context exceeds 50,000 tokens.

### 🛡️ Sequential Tool Calling Enforcement
*   **Date:** 4/19/2026
*   **Description:** Hardcoded the `parallel_tool_calls: false` parameter into the OpenAI API adapter.
*   **Rationale:** Local, highly-quantized models (like the IQ3_XXS Qwen MoE) suffer from "2-bit drunk" hallucination loops when forced to manage the structural overhead of generating multiple concurrent JSON tool schemas in a single output block. Enforcing `parallel_tool_calls: false` acts as a strict guardrail, forcing the `llama.cpp` inference engine to execute complex tool chains sequentially, preserving structural integrity and stability at the cost of slower round-trip times.

### 💻 Software Engineer Sub-Agent
*   **Date:** 4/20/2026
*   **Description:** Built a dedicated `software_engineer` subagent tool for heavy implementation tasks.
*   **Implementation:** The subagent is initialized with a high turn limit (`maxTurns: 30`) and a strict system prompt targeting "Act-then-Refine" implementation loops. It dynamically loads its sampling configurations from the `qwopus_coder` profile in `profiles.json` (favoring a lower temperature for coding accuracy). It is exposed to the main `architect` profile to allow offloading of intense software engineering tasks without bloating the primary conversational context.

### 🧠 Selective Fidelity Tool Truncation (Zero-Cost Abstraction)
*   **Date:** 4/22/2026
*   **Description:** Replaced the crude 100k-character hard chop in the `bash` tool with an algorithmic "Selective Fidelity" compression tier. This prevents the loss of critical exit state (errors/stack traces) that frequently occurred when massive logs were blindly truncated.
*   **Implementation:** Implemented purely in TypeScript (zero VRAM, zero token cost):
    *   **Tier 1 (Verbatim):** Outputs under 2,000 characters pass through perfectly intact.
    *   **Tier 2 (Line-Based):** For standard logs, returns the first 50 lines (context), inserts a `[... X lines omitted ...] ` marker, and appends the final 50 lines (exit state/errors).
    *   **Tier 3 (Character-Based):** For dense blobs (like JSON without newlines), performs a strict character split at half the verbatim threshold to preserve head and tail without breaking.

### 👁️ Native Vision Support (/image)
*   **Date:** 4/22/2026
*   **Description:** Added native image capabilities to the `apollo_cli.ts` orchestrator to support local Vision-Language Models (VLMs) like Qwen 3.6 MoE and Holo3-35B.
*   **Implementation:** Introduced a new `/image <path>` slash command. The CLI reads the specified local image file (supporting JPEG, PNG, GIF, WEBP), determines its MIME type, base64-encodes the data, and stages it in memory. Upon the user's next text prompt, the staged images are bundled as Anthropic-style `image_url` content blocks within the user message and sent to the underlying API runner.
*   **Safety Guardrails Added:** 
    1. **Vision Capability Check:** Requires `"vision": true` in `profiles.json` to prevent sending image tokens to text-only models.
    2. **VRAM Protection:** Hard limits file size to 8MB to prevent ROCm out-of-memory (OOM) crashes.
    3. **Token Awareness:** Checks image dimensions and prints a warning if width/height exceeds 6000px, alerting the user to massive context consumption.

### 🩺 Verbose Tool & Thinking Diagnostics
*   **Date:** 4/22/2026
*   **Description:** Increased the diagnostic visibility of the CLI interface to expose more of the model's internal processing, specifically addressing models whose thinking blocks were blending into standard text.
*   **Implementation:**
    1. **Auto-Formatting Think Blocks:** Models like Qwen 3.6 MoE often output their reasoning stream immediately without a leading `<think>` tag, causing the CLI to render it as normal white text until it hits the trailing `</think>`. Added logic in `apollo_cli.ts` to detect orphaned `</think>` tags and automatically inject `<think>\n` at the start of the stream. This forces the UI to properly isolate and render the entire reasoning block in cyan.
    2. **Verbose Tool Inputs:** Expanded the `tool_use` event handler in the CLI to natively print the full JSON payload of the tool arguments requested by the model, granting full transparency into the model's decision-making before the tool executes.

### 🎛️ Native Advanced Sampling & Reasoning Parsing (Upstream PR Submitted)
*   **Date:** 4/23/2026
*   **Description:** The previous "Granular Model Parameters" were technically dead code in the upstream framework because they weren't wired into the API adapters. We have fully implemented and wired `topP`, `topK`, `minP`, `frequencyPenalty`, `presencePenalty`, and `extraBody` through the entire `open-multi-agent` stack (`AgentConfig` -> `RunnerOptions` -> `openai.ts`/`anthropic.ts` payloads).
*   **Implementation:** 
    1. **Parameter Wiring:** Passed parameters through the orchestration layers down to the HTTP payload configurations.
    2. **DeepSeek/llama-server Reasoning:** Implemented native stream parsing for `reasoning_content` deltas in the OpenAI adapter. This correctly translates the invisible thought streams from local models like DeepSeek R1 or Qwen 3.6 into explicit `<think>` tags so the CLI can render them accurately.

### 🔄 Background Process Orchestration
*   **Date:** 5/01/2026
*   **Description:** Built a `background_process` tool to allow sub-agents (like `software_engineer`) to spawn long-lived, non-blocking servers (e.g., `npm run dev`), tail their logs asynchronously, and gracefully terminate them, unlocking autonomous full-stack testing workflows.
*   **Implementation:** 
    1. Spawns `child_process.spawn()` with `detached: true` to prevent blocking the `AgentRunner` loop.
    2. Redirects `stdout` and `stderr` to isolated temp files `/tmp/apollo-bg-*/`.
    3. Maintains a module-scoped `activeProcesses` registry to track PIDs.
    4. Implements a `process.on('exit')` hook to automatically hunt down and `SIGKILL` any orphaned zombie processes if the main Apollo CLI crashes or exits.

### 🧩 Qwen Command-Style Parsing (AEON Artifact Support)
*   **Date:** 5/01/2026
*   **Description:** The heavily abliterated AEON fine-tunes abandoned JSON and began hallucinating command-line style tool invocations (e.g., `<tool_call>\ntool_codebase_investigator|prompt=...\n</tool_call>`).
*   **Implementation:** Wrote a second dedicated fallback regex parser (`extractQwenCommandStyleToolCalls`) in `text-tool-extractor.ts`. It detects the pipe-delimited syntax, strips hallucinated prefixes (`tool_`), correctly manages quotation stripping, handles merged-line variants, and perfectly reconstructs the resulting Zod-compliant JSON object so the CLI can safely execute the hallucinated syntax without crashing.

### 📝 YAML Profile Migration
*   **Date:** 5/04/2026
*   **Description:** Migrated the CLI's configuration architecture from `profiles.json` to `profiles.yaml`.
*   **Implementation:** 
    1. Converted existing JSON profile schemas to YAML format, utilizing the `|` operator for multi-line system prompts to dramatically improve readability and allow for inline `# comments` regarding sampling theories.
    2. Updated `apollo_cli.ts` to utilize the `yaml` npm package (`YAML.parse`) and load from `profiles.yaml`. This eliminates the fragility of strict JSON syntax (e.g., trailing commas) when rapidly tuning sub-agent hyperparameters.

### 🎨 PyQt6 Dynamic Canvas IPC Integration (`ask_user` tool)
*   **Date:** 5/10/2026
*   **Description:** Implemented the `ask_user` tool natively within the `open-multi-agent-upstream` orchestrator, bridging the Node CLI output to a native Python PyQt6 GUI (`dynamic_canvas.py`) via file-based Inter-Process Communication (IPC).
*   **Implementation:**
    1. **TypeScript Orchestrator (`ask-user.ts`):** Created a Zod-schema tool supporting `choice`, `text`, and `yesno` questions. The execution safely yields the active LLM stream, writes a JSON payload to `ui_state.json`, and enters a non-blocking poll loop awaiting user input. Fixed a critical crash caused by undefined `.aborted` signals using optional chaining (`context?.signal?.aborted`).
    2. **Python GUI (`dynamic_canvas.py`):** Patched the existing `render_payload` method to intercept `ask_user_prompt` types. Dynamically renders corresponding PyQt6 interactive widgets (QPushButtons, QLineEdits) styled with Amber/Black Sovereign aesthetics.
    3. **Resumption:** When the user interacts with the canvas, it drops the response into `user_response.json`, clears the screen, and the TypeScript side instantly reads, deletes, and injects the human response back into the LLM context to resume generation.

### ⚡ Programmatic Tool Calling (Zero-Context-Cost Turns)
*   **Date:** 5/13/2026
*   **Description:** Implemented Hermes-style Programmatic Tool Calling (PTC) via the `run_python_script` tool. Allows the agent to write a single Python script that executes multiple native Apollo tools (e.g., `bash`, `file_read`, `grep`) locally, collapsing complex multi-step reasoning loops into a single turn without bloating the context window with intermediate tool results.
*   **Implementation:**
    1. **Ephemeral RPC Server:** The `python-ptc.ts` tool spins up an ephemeral HTTP server on `127.0.0.1` upon execution, binding to an available port.
    2. **Python Stub Injection:** Automatically prepends a Python stub library (`apollo_tool()`) that uses `urllib` to translate Python function calls into JSON POST requests routed back to the Node.js HTTP server.
    3. **Synchronous Dispatch:** The Node server parses incoming requests, triggers the native `ToolExecutor` (e.g., running a real `bash` command), and returns the JSON result back to the Python script.
    4. **Context Savings:** Upon script completion, the ephemeral server shuts down and the CLI returns *only* the script's `stdout` to the LLM. Intermediate tool results never enter the LLM's prompt history.

### 🔄 Subagent Tracing, Auto-Testing & Auto-Bootstrapping (Framework Optimizations)
*   **Date:** 5/16/2026
*   **Description:** Gemini implemented critical framework-level optimizations to improve subagent reliability, reduce Sovereign Coordinator cognitive overhead, and eliminate "flying blind" on first turns. Requires CLI restart to take effect.
*   **Implementation:**
    1.  **Subagent Tracing & IPC Stripping:** `delegate_task`, `software_engineer`, and `codebase_investigator` all now use the async runner.stream() loop under the hood. As subagents generate tokens, they stream directly to process.stdout.write on your console. Once they hit a stop token, the framework runs a Regex strip across the final output to remove the `<thinking>...</thinking>` block before returning it to the Sovereign Coordinator — keeping your context window clean.
    2.  **Auto-Testing (software_engineer):** Added an optional `test_command` string to its JSON schema. If the Coordinator provides one (e.g., `npm test`), the framework executes it using child_process.execSync immediately after the subagent finishes, and injects the stdout/stderr block directly into the IPC payload so the Coordinator doesn't have to manually verify code quality.
    3.  **Auto-Bootstrapping (codebase_investigator):** Before it initializes the agent, it now runs `tree -L 2` (ignoring node_modules, .git, etc.) and injects the output into the [Auto-Bootstrapped Project Directory] block in its system prompt. It will never "fly blind" on turn 1 again — critical for accurate architectural analysis.
    4.  **Sovereign Coordinator Persona Update:** Explicit mandates added telling it to "Trust your specialized subagents" and specifically instructed it not to echo or summarize requests in its own `<thinking>` blocks — reducing cognitive overhead and context window pressure on multi-agent tests.

