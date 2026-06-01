---
name: manage-a2a-state-sync
description: Manage the Architect-to-Agent (A2A) state-synchronization loop using the SQLite Message Bus `scratchpad` API. Use when a lead orchestrator (9070 XT) needs to pass complex data structures or files to a remote sub-agent (P100) that lacks shared filesystem access (Split-Brain).
---

# Manage A2A State-Sync

This skill provides a procedure for synchronizing state between a lead architect and remote sub-agents using the SQLite Message Bus `scratchpad`. This is the primary solution for the "Split-Brain" problem in distributed LLM swarms.

## Procedure

### 1. Architect: Push State
Before delegating a task that requires local file data or complex context, push that data to the `scratchpad`.

**Action:** Use `starbuck_write_scratchpad` to store the data under a unique key. 
**Best Practice:** The orchestrator's `delegate_task` tool now supports a `provided_resources` array. Always list your scratchpad keys here to ensure the sub-agent knows which resources are available.

```typescript
// Pattern: Writing a file's content for a sub-agent
await starbuck_write_scratchpad({
  key: "sync_12345_ui_state.json",
  value: JSON.stringify(localData)
});

// Pattern: Pushing a resource key to delegate_task
await delegate_task({
  task: "Analyze the UI state and propose layout changes.",
  provided_resources: ["sync_12345_ui_state.json"]
});
```

### 2. Delegate Task
Pass the scratchpad key to the sub-agent.

**Instruction to Sub-agent:** "Read the base data from the scratchpad key `sync_12345_ui_state.json` instead of attempting to read from `/mnt/TG_2TB/...`."

### 3. Sub-agent: Pull and Process
The remote sub-agent retrieves the data, performs the task, and pushes the result back to a new scratchpad key.

**Action:** Sub-agent uses `starbuck_read_scratchpad` to pull the base data and `starbuck_write_scratchpad` to push the result.
**Verified Key Pattern:** `ui_state_json_updated` is used for UI state sync loops.

### 4. Architect: Pull Result
The lead architect retrieves the final result and writes it back to the local filesystem.

## Verification & Troubleshooting

### Standardize the API Endpoint
Ensure all remote nodes have the `MESSAGE_BUS_API` environment variable pointing to the **Architect's LAN IP** (e.g., `http://10.0.0.71:8000`), not `127.0.0.1`.

### Environment Drift Check
If a sub-agent fails with `ENOENT`, it likely ignored the scratchpad instruction and tried to read a local path.
- **Fix**: Re-delegate the task with a stricter instruction: "You MUST NOT use file_read on absolute paths. Use starbuck_read_scratchpad exclusively for source data."
