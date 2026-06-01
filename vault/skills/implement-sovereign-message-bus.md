---
name: implement-sovereign-message-bus
description: Implement and maintain a robust, SQLite-backed task queue for distributed agent orchestration (Coordinator -> Worker).
---

## When to Use
Use this skill when designing a system where multiple local agents (e.g., Desktop, Pi 5, S21) need to communicate and execute sub-tasks without race conditions or fragile JSON file-passing.

## Procedure

### 1. Database Configuration (Concurrency)
Initialize the SQLite database using `PRAGMA journal_mode=WAL;` (Write-Ahead Logging).
- This is critical for distributed AI nodes to read the queue simultaneously without locking out the writer (the Architect).

### 2. Task Schema
The `task_queue` table should include the following fields:
- `task_name` (string)
- `status` (pending, claimed, completed, failed)
- `assigned_node` (string, the ID of the worker)
- `requirements_json` (stringified JSON for Capability Routing)
- `input_payload` (string/JSON)
- `output_payload` (string/JSON)
- `timestamps` (created_at, updated_at)

### 3. Capability-Based Routing
Integrate the `CapabilityRouter` to filter tasks based on the "Physics" of the hardware:
- `min_context`: Does the node have enough VRAM/RAM for the window?
- `min_precision`: Does the node's quantization match the reasoning requirement?
- `min_tps`: Is the node's throughput fast enough for the user's wait limit?
- `requires_internet`: Can the node reach the web?

### 4. Atomic Task Claiming
Workers MUST use an exclusive transaction to claim tasks to prevent the "Double-Claim" bug (where two nodes grab the same task).
```python
# Atomic Claim Pattern
with sqlite3.connect(db_path) as conn:
    cursor = conn.cursor()
    cursor.execute("BEGIN EXCLUSIVE TRANSACTION")
    # 1. Find the first pending task matching capabilities
    # 2. UPDATE task_queue SET status='claimed', assigned_node='NodeID' WHERE id=TASK_ID
    # 3. conn.commit()
```

## Pitfalls and Fixes
- **Symptom:** Task queue corruption or "Database is locked" errors.
  - **Cause:** WAL mode was not enabled, or a node held a transaction open for too long.
  - **Fix:** Verify `PRAGMA journal_mode=WAL;` and ensure transactions are extremely short (less than 1ms). Perform the LLM work *outside* the database transaction.
- **Symptom:** A task remains "claimed" but never finishes.
  - **Cause:** The worker node (e.g., Pi 5) crashed or lost power while processing.
  - **Fix:** Implement a "Heartbeat" or a timeout checker that resets `claimed` tasks back to `pending` if `updated_at` is older than X minutes.

## Verification
- Run a test script with two simulated workers (running in parallel threads) attempting to claim the same set of 5 tasks.
- Confirm that no task ID is ever assigned to more than one worker.
- Confirm that the `assigned_node` matches the hardware node that claimed it.
