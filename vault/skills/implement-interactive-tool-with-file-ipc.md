---
name: implement-interactive-tool-with-file-ipc
description: Implement human-in-the-loop interactive tools for autonomous agents using file-based Inter-Process Communication (IPC). Use when an agent needs to prompt a user via a separate GUI or terminal process without blocking the main event loop or when integrating with non-web interfaces (e.g., PyQt6, raw terminal).
---

# Implement Interactive Tool with File IPC

This pattern allows an autonomous agent (like those in the `open-multi-agent` framework) to yield execution to a human user via a shared filesystem. It is ideal for "Sovereign" setups where the agent and UI are separate processes.

## Procedure

### 1. Define the Shared State Paths
Choose a common directory (e.g., `data/`) for the IPC files.
- `ui_state.json`: The "push" from the agent to the UI (contains questions/prompts).
- `user_response.json`: The "pull" from the UI back to the agent (contains answers).

### 2. Implement the Tool Definition (TypeScript/Node)
The tool must write the prompt, poll for the answer, and handle abort signals.

```typescript
import { z } from 'zod';
import * as fs from 'fs';
import { defineTool } from '../framework.js';

export const askUserTool = defineTool({
  name: 'ask_user',
  description: 'Ask the user a question via the GUI.',
  inputSchema: z.object({
    question: z.string(),
    options: z.array(z.string()).optional()
  }),
  execute: async ({ question, options }, context) => {
    const uiPath = 'data/ui_state.json';
    const responsePath = 'data/user_response.json';

    // 1. Push payload to GUI
    fs.writeFileSync(uiPath, JSON.stringify({ type: 'ask_user_prompt', question, options }));

    // 2. Poll for response
    return new Promise((resolve, reject) => {
      const pollInterval = setInterval(() => {
        // CRITICAL: Handle AbortController (Ctrl+C)
        if (context?.signal?.aborted) {
          clearInterval(pollInterval);
          reject(new Error('Operation aborted by user.'));
          return;
        }

        if (fs.existsSync(responsePath)) {
          clearInterval(pollInterval);
          const responseData = JSON.parse(fs.readFileSync(responsePath, 'utf8'));
          fs.unlinkSync(responsePath); // Cleanup

          // CRITICAL: Return must be stringified and wrapped in { data }
          resolve({ data: JSON.stringify(responseData) });
        }
      }, 500); // 500ms polling is usually sufficient
    });
  }
});
```

### 3. Implement the UI Receiver (Python/PyQt6 Example)
The UI monitors the state file and writes the response.

```python
import json
import os

def check_for_prompts():
    if os.path.exists("data/ui_state.json"):
        with open("data/ui_state.json", "r") as f:
            payload = json.load(f)
        if payload.get("type") == "ask_user_prompt":
            # Render your UI buttons/fields here
            answer = render_gui_and_get_answer(payload)
            
            # Write response back
            with open("data/user_response.json", "w") as f:
                json.dump({"answer": answer}, f)
            
            # Optionally clear UI state
            os.remove("data/ui_state.json")
```

## Verification Checklist
- [ ] **Type Safety**: Use `inputSchema:` instead of `schema:` in the `ToolDefinition`.
- [ ] **Abort Handling**: Ensure `context?.signal?.aborted` is checked inside the polling loop to prevent hanging processes on `Ctrl+C`.
- [ ] **Return Format**: The `execute` function must return `{ data: string }`. If the data is an object, use `JSON.stringify()`.
- [ ] **Cleanup**: Ensure the `user_response.json` file is deleted immediately after reading to avoid stale answers in future turns.

## Pitfalls
- **Double-Polling**: Avoid race conditions where both the agent and UI delete the same file. The Agent should be the primary "owner" of the response file cleanup.
- **Lost in Polling**: If the user takes too long, ensure the agent's underlying HTTP connection (if using a remote server) doesn't timeout. Local servers are usually fine.
- **Undefined Signal**: Always use optional chaining (`context?.signal`) as the signal object might not be initialized by the orchestrator in all execution modes.
