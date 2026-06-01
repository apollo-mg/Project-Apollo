---
name: extend-gemini-cli-tools
description: Add custom tools to Gemini CLI by modifying its source code, ensuring correct registration and type safety.
---

## When to Use
Use this skill when you need to integrate new functionality directly into the Gemini CLI (e.g., hardware-specific tools like `dispatch_task`, local database bridges, or custom API wrappers) that cannot be handled by standard shell commands.

## Procedure

### 1. Define the Tool Class
Create a new TypeScript file in `packages/core/src/tools/<tool-name>.ts`.

- **Imports:**
  ```typescript
  import { z } from 'zod';
  import {
    BaseDeclarativeTool,
    BaseToolInvocation,
    type ToolInvocation,
    type ToolResult,
  } from './tools.js';
  ```
- **Params Schema:** Define parameters using Zod for strict type checking and LLM discovery.
- **Invocation Class:** Extend `BaseToolInvocation<ParamsType, ToolResult>`.
- **Tool Class:** Extend `BaseDeclarativeTool<ParamsType>`.

### 2. Implement the `execute()` method
The result must adhere to the `ToolResult` interface (specific to the CLI version):
```typescript
async execute(): Promise<ToolResult> {
  // ... implementation logic ...
  return {
    llmContent: [{ text: "Result for the model" }],
    returnDisplay: "Result for the user display" // Can be string or structured display object
  };
}
```

### 3. Register the Tool in `config.ts`
Modify `packages/core/src/config/config.ts`:
1. **Import the Tool:**
   ```typescript
   import { YourCustomTool } from '../tools/your-tool.js';
   ```
2. **Instantiate and Register:** Locate the constructor where core tools are registered and add:
   ```typescript
   maybeRegister(YourCustomTool, () =>
     registry.registerTool(new YourCustomTool(this, this.messageBus)),
   );
   ```

### 4. Sync and Build
If the upstream CLI has updated, align your source before building:
1. Identify global version: `gemini --version`.
2. Sync source to tag:
   ```bash
   git stash
   git fetch --all --tags
   git checkout v0.X.Y-preview.Z
   git stash pop
   ```
3. Build the project:
   ```bash
   npm install && npm run build:all
   ```

## Pitfalls and Fixes
- **Symptom:** `error TS2304: Cannot find name 'YourCustomTool'`.
  - **Cause:** Missing import in `config.ts` or the tool class is not exported.
  - **Fix:** Verify exports in the tool file and imports in `config.ts`.
- **Symptom:** `Object literal may only specify known properties... 'text' does not exist in type 'ToolResult'`.
  - **Cause:** The `ToolResult` interface has changed in the current branch/version.
  - **Fix:** Check `packages/core/src/tools/tools.ts` for the `ToolResult` definition. Use `llmContent` for the model's view and `returnDisplay` for the user's view.
- **Symptom:** `git stash pop` fails due to conflicts.
  - **Cause:** Changes in `config.ts` between versions.
  - **Fix:** Manually re-apply the import and `maybeRegister` call at the correct locations in the new version of `config.ts`.

## Verification
1. Run the local build: `node packages/cli/dist/index.js`.
2. Verify the tool appears in the agent's available tools list.
3. Execute a test call and confirm both `llmContent` and `returnDisplay` are handled correctly.
