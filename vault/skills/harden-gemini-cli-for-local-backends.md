---
name: harden-gemini-cli-for-local-backends
description: Implement retry logic, role-alternation fixes, and tool-parameter fallbacks in Gemini CLI to handle local server instability and model chaotic behavior.
---

## When to Use
Use this skill when developing or maintaining the Gemini CLI integration with local LLM servers (like `llama-server`) that are prone to restarts, connection drops, or transient 502/503 errors. This is specifically relevant when using a VRAM watchdog that kills and restarts the backend.

## Procedure

### 1. Identify Error Triggers
Determine which errors should trigger a retry. Common ones include:
- `ECONNREFUSED`: Server is currently down or restarting.
- `fetch failed`: Network-level failure to reach the port.
- `502 Bad Gateway` / `503 Service Unavailable`: Proxy or server is not yet ready.

### 2. Implement the Retry Loop
In the content generator logic (e.g., `sovereignContentGenerator.ts`), wrap the `fetch` call in a `while` loop.

```typescript
let maxRetries = 3;
let response: Response | null = null;

while (maxRetries > 0) {
  try {
    response = await fetch(`${this.baseUrl}/v1/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (response.ok) break; // Success

    if (response.status === 502 || response.status === 503) {
      console.log(`
[Sovereign] Backend unavailable (Status ${response.status}). Retrying in 5 seconds...`);
      await new Promise((resolve) => setTimeout(resolve, 5000));
      maxRetries--;
      continue;
    }
    
    // Non-retryable error
    throw new Error(`API error: ${response.status} - ${await response.text()}`);
  } catch (e: any) {
    if (e.code === 'ECONNREFUSED' || e.message.includes('fetch failed')) {
      console.log(`
[Sovereign] Connection refused. Retrying in 5 seconds...`);
      await new Promise((resolve) => setTimeout(resolve, 5000));
      maxRetries--;
    } else {
      throw e;
    }
  }
}
```

### 3. Build and Deploy
After modifying the source, rebuild the core package:
```bash
npm run build -w @google/gemini-cli-core
```

### 4. Maintain the Translation Layer (The Shock Absorber)
The `sovereignContentGenerator.ts` file acts as a translation layer to bridge CLI expectations with local model quirks.

#### Debug Role Alternation (Gemma 4)
- **Symptom:** `500 API Error: Jinja Exception: Conversation roles must alternate`.
- **Fix:** Locate the role-merging loop. Ensure `system` messages are prepended to the first `user` message and `tool` responses are wrapped in XML tags (e.g., `<tool_response>`) and merged into the user message.

#### Fix Tool Parameter Hallucinations (Qwen Fallback)
- **Symptom:** "params must have required property 'url'" despite the model generating a URL in its thought block.
- **Fix:** Implement a Regex fallback in `sovereignContentGenerator.ts`. When an empty `args: {}` object is detected for tools like `web_fetch`, scan the model's text output using `/https?:\/\/[^\s"'<>]+/i` and inject the found URL into the payload.

#### Sanitize Reasoning Tags
- **Symptom:** Non-standard reasoning tags (e.g., `<|channel>thought`, `<channel|>`) bleed into the UI or cause infinite recursion loops.
- **Fix:** In `generateContentStream`, aggressively replace variant tags with standard `<think>` and `</think>` tags before yielding the stream to the CLI.

#### Inject Dynamic Context
- **Procedure:** Update the `sysText` construction to inject the current `new Date().toLocaleDateString()` and behavioral constraints (e.g., "You are a small model... rely on tools").

## Pitfalls and Fixes
- **Infinite Loops:** Always include a `maxRetries` counter to prevent the CLI from hanging forever if the backend fails to restart.
- **Silent Failures:** Always log a message to the user (`console.log`) when a retry is happening, so they don't think the CLI has frozen.
- **Context Loss:** Ensure the retry happens at the `fetch` level so the conversation history stored in the client is preserved and sent fresh to the new server instance.
- **Jinja Mismatch:** If the server still throws role errors, verify that no `tool` or `system` roles were added to the `messages` array for models identified as `isGemma`.
- **UI Tag Bleed:** If raw tags still appear, the sanitizer regex in `sovereignContentGenerator.ts` must be updated to match the new tag variant.

## Verification
1. Start `llama-server`.
2. Initiate a prompt in Gemini CLI.
3. While the CLI is "Responding...", manually kill the `llama-server` process.
4. Verify that the CLI prints a retry notice and waits.
5. Restart `llama-server`.
6. Verify that the CLI successfully completes the turn without user intervention.

