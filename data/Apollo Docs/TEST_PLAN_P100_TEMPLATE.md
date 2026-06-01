# Test Plan: P100 CUDA Engine & Buun Chat Template Validation

## Objective
Validate the performance and stability of the newly compiled CUDA `llama-server` engine on the dual P100 server, utilizing Buun's hardened Qwen 3.6 Jinja chat template. The primary goal is to confirm whether the new template features (empty-think fix, tool-truncation, and thinking preservation) resolve the context-compaction hallucination loops during deep agentic tasks.

## Hardware & Software Stack
*   **Target Node:** Dual Tesla P100 Server (32GB VRAM total)
*   **Engine:** `buun-llama-cpp` (CUDA optimized for sm_60)
*   **Template:** `buun-Qwen3.6-chat_template/chat_template.jinja`
*   **Model:** Qwen 3.6 MoE variant (e.g., Darwin-36B or Qwopus-27B)
*   **Sub-agent:** `software_engineer`

## Configuration Conflict Resolution
**Before launching, we must resolve a conflict regarding the `--chat-template-kwargs` parameter:**

*   **The User's Goal:** Set `"preserve_thinking": true`. This allows the model to "remember" its past thoughts in the context window. While it bloats context, it is invaluable for "Foundry" logging, providing rich, high-fidelity traces of *why* an agent made a decision, which is perfect for future distillation and fine-tuning.
*   **NotebookLM's Suggestion:** Set `"preserve_thinking": false`. This strips the `<think>` blocks from previous turns, keeping the context window incredibly lean and preventing the compaction crash loops we've seen previously.

**Recommendation:** For *this specific stress test*, we should follow your instinct and set `"preserve_thinking": true`. We need to see if the engine can handle the bloated context now that the other bugs (like empty-think and triple-quotes) are fixed. If it OOMs, we can fall back to NotebookLM's suggestion.

## Proposed Launch Arguments (The "High-Fidelity" Configuration)
```bash
/mnt/TG_2TB/Projects/Apollo/engines/buun-llama-cpp/build/bin/llama-server \
  -m /path/to/your/Qwen3.6-MoE.gguf \
  -c 32768 \
  -sm row \
  --tensor-split 50,50 \
  --chat-template-file /mnt/TG_2TB/Projects/Apollo/engines/buun-Qwen3.6-chat_template/chat_template.jinja \
  --chat-template-kwargs '{"auto_disable_thinking_with_tools": true, "preserve_thinking": true, "max_tool_response_chars": 100000}' \
  --port 8082 \
  --host 0.0.0.0
```

## The Execution Plan
1.  **Launch the Server:** SSH into the P100 node and spin up the `llama-server` using the arguments above.
2.  **Verify Health:** Check `http://<p100-ip>:8082/health` to ensure the server is ready.
3.  **Invoke Sub-agent:** Use the local Apollo CLI (Architect) to delegate a complex task to the `software_engineer`.
    *   *Proposed Task:* "Write a Python script that recursively scans a directory, parses all JSON files, extracts any keys matching a specific regex pattern (e.g., 'API_KEY'), and outputs a formatted markdown report. Create a dummy directory with 5 nested JSON files to test it, execute the script using the `bash` tool, and verify the output."
4.  **Monitor Telemetry:** Watch the P100 terminal for token generation speeds and watch the Apollo CLI for the `[Tool output compressed]` markers to ensure the 100k truncation limit is respected.
5.  **Evaluate:** Did it loop? Did it successfully strip `<think>` tags when calling tools (`auto_disable_thinking_with_tools: true`)? Did it successfully *preserve* its internal monologue across turns?