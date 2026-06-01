---
name: qa-sqlite-swarm-integrity
description: Conduct automated stress testing for SQLite-backed distributed agent swarms. Use when validating Message Bus stability, Write-Ahead Logging (WAL) concurrency, and atomic task claiming logic under heavy thundering herd loads.
---

# QA: SQLite Swarm Integrity Testing

This skill outlines the automated QA workflow (the "Scientist" persona) for validating the robustness of a distributed agent swarm built on a SQLite Message Bus.

## Test 1: The WAL Collision Test (Concurrency)
**Goal:** Verify that SQLite WAL mode handles simultaneous high-volume read/writes without locking errors.

1. **Setup:** Create a Python script using `threading` and `urllib.request`.
2. **Parameters:**
   - 10 Writer threads: Continuously `POST` 1MB payloads to `/scratchpad`.
   - 10 Reader threads: Continuously `GET` random keys from `/scratchpad`.
   - Duration: 30-60 seconds.
3. **Execution:** Observe Transactions Per Second (TPS) and check for `database is locked` HTTP 500 errors.
4. **Pass Criteria:** 0 locking errors, 0 timeouts.

## Test 2: The Swarm Thundering Herd (Task Routing)
**Goal:** Verify that atomic task claiming prevents double-claims and queue chokes.

1. **Setup:** A script that rapidly publishes a large volume of tasks (e.g., 50+) in < 2 seconds.
2. **Parameters:**
   - Target: `/tasks/publish`.
   - Payload: Dummy software_engineer tasks.
3. **Execution:** Dump the herd, then monitor `worker_daemon.py` logs or query the database.
4. **Pass Criteria:**
   ```sql
   -- Verify all tasks claimed/completed without duplicates
   SELECT assigned_node, count(*) FROM task_queue GROUP BY assigned_node;
   ```
   - No task should be assigned to multiple nodes.
   - All tasks should eventually reach `completed` or `failed` state.

## Verification Checklist
- [ ] Database is in WAL mode (`PRAGMA journal_mode=WAL;`).
- [ ] Claiming uses `BEGIN EXCLUSIVE TRANSACTION;`.
- [ ] Connection timeout is set high enough (e.g., `sqlite3.connect(..., timeout=30.0)`).
- [ ] Scratchpad keys are uniquely prefixed (e.g., `torture_key_[thread_id]`).

## Failure Shields
- **Dangling Imports:** If tasks fail instantly with `ModuleNotFoundError`, check for unused imports in `worker_daemon.py` that might be missing in the node's environment.
- **Docker Cache:** If remote nodes still fail after a local fix, ensure the remote image is rebuilt or the container is hot-patched.
