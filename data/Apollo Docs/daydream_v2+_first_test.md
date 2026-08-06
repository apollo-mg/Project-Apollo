# Skill: Atomic Cross-Agent Handoff Protocol

**Name:** `skill_atomic_handoff`  
**Trigger:** Whenever Agent A has made substantive changes and Agent B will continue the session  
**Purpose:** Ensure zero-loss, verifiable transfer of state changes between agent sessions

## The Problem This Solves

Without this skill, cross-agent knowledge transfer suffers from:
- **Verbal loss:** Gemini describes changes in prose; Apollo must reconstruct file edits
- **Partial writes:** `file_edit` operations can be truncated or fail silently
- **No verification:** No step confirms the receiving agent actually wrote what was intended
- **Scatter:** Knowledge lives in code + memory files + conversation history — no single source of truth

## The Protocol

### Phase 1: Emission (Agent A — the changer)

When an agent completes a set of changes, it must emit a structured **Handoff Payload** in a single JSON block before ending its turn:

```json
{
  "_handoff": true,
  "version": 1,
  "changes": [
    {
      "type": "file_write",
      "path": "/path/to/FILE.md",
      "content": "The full new content of the file, not a diff",
      "reason": "One-line explanation of why this file changed"
    },
    {
      "type": "file_append",
      "path": "/path/to/FILE.md",
      "marker": "### Framework Optimizations",
      "content": "Content to insert after the marker line",
      "reason": "..."
    },
    {
      "type": "code_change",
      "path": "/path/to/FILE.ts",
      "summary": "Concise summary of what changed",
      "key_details": ["Detail 1", "Detail 2"]
    }
  ],
  "behavioral_notes": [
    "Trust your subagents — they are optimized for their domain",
    "Do not echo user requests in  blocks"
  ],
  "pending_actions": [
    "Restart CLI for code changes to take effect"
  ]
}
```

**Rules for Emission:**
- Must be a complete JSON block (not truncated)
- File writes must include **full file content**, not diffs — eliminates merge ambiguity
- Must be emitted as the *last* action before the agent's turn ends

### Phase 2: Reception (Agent B — the receiver)

On session start, Agent B must check for a pending handoff:

1. **Parse** the handoff JSON from the conversation history
2. **Apply** all `file_write` and `file_append` operations atomically:
   - For `file_write`: write the entire file content in one `file_edit` call
   - For `file_append`: insert content after the marker in one `file_edit` call
3. **Verify** each file was written correctly by reading it back
4. **Acknowledge** completion: "Handoff v1 received and verified. All N file changes applied."

**Rules for Reception:**
- If the handoff JSON is malformed or truncated → flag it, attempt reconstruction, but **never silently skip**
- If a file write fails → retry once, then escalate to user with exact error
- If a read-back verification fails → flag the mismatch

### Phase 3: Archival

After a handoff is applied:
- Append a summary entry to the project changelog
- Mark the handoff as "consumed" in memory so it isn't re-applied on subsequent sessions

## Why This Works

| Before (Current) | After (Protocol) |
|---|---|
| Verbal description → mental reconstruction → manual file edit | Structured payload → direct file write |
| `file_edit` with `old_string`/`new_string` — fragile matching | `file_write` with full content — unambiguous |
| No verification step | Read-back verification |
| Silent failures possible | Explicit acknowledgment required |
| Knowledge scattered across code + prose + memory | Single authoritative payload |

## Edge Case: Truncated Handoff

If Agent A's handoff JSON is cut off (as happened with Mark's message ending at "From"), Agent B must:

1. Attempt to parse the partial JSON
2. If incomplete, request from the user: "The handoff from the previous session was truncated. Can you provide the complete details of what changed?"
3. **Never** guess the content of a truncated payload — partial updates are worse than no updates

---

**This skill transforms the current lossy, reconstructive handoff pattern into a declarative, atomic, and verifiable protocol. It directly addresses the file_edit truncation that occurred in this session, and prevents the class of bugs where memory files fall out of sync with the actual codebase.**


# Skill: Self-Modification Verification Protocol (SMVP)

## When to Apply

Trigger this skill **whenever you modify code, configuration, or architecture that affects the system you are currently running within**. Common triggers:

- Editing CLI source files (`apollo_cli.ts`, tool definitions, etc.)
- Updating memory files that alter agent behavior (e.g., `LOCAL_AGENT_CONTEXT.md`)
- Modifying IPC protocols, stream logic, or subagent delegation paths
- Changing profiles, schemas, or system prompts

## The Protocol

### Phase 1: Document the Delta (Before You Apply)

Create a structured **modification record** in the session log or a dedicated `PENDING_VERIFICATIONS.md` file:

```markdown
## [SMVP] Modification Record: {date}

**Files Modified:**
- `{path/to/file.ts}` — `{brief description of change}`

**Behavioral Impact:**
- `{what the system will do differently after restart}`

**Verification Test:**
- `{a concrete, minimal test case that proves the change works}`

**Risk Assessment:**
- **Criticality:** {high/medium/low}
- **Rollback:** {what file state to revert to if verification fails}
```

### Phase 2: Create an Automated Verification Hook

Write a **one-line verification command** that can be run immediately after restart. Store it in the modification record.

**Examples:**
```bash
# For subagent tracing: delegate a task and confirm stdout streams directly
echo "delegate_task test" | node apollo_cli.ts 2>&1 | grep -c "thinking"

# For auto-testing: verify test_command is honored
echo '{"test_command":"echo hello"}' | node apollo_cli.ts 2>&1 | grep "hello"

# For auto-bootstrapping: confirm tree output appears in system prompt
echo "investigate" | node apollo_cli.ts 2>&1 | grep -c "Auto-Bootstrapped"
```

### Phase 3: Flag the Mental Model as "Drifted"

Insert a **drift warning** into the current session's context so the agent knows its internal model may be stale:

```
⚠️  ARCHITECTURAL DRIFT WARNING: Codebase was modified in this session.
   Your internal model of the CLI may be stale. Changes require a restart
   to take effect. See PENDING_VERIFICATIONS.md for reconciliation steps.
```

This prevents the agent from making assumptions about system behavior based on outdated knowledge.

### Phase 4: On Next Startup — Reconcile

When a new session begins, check for `PENDING_VERIFICATIONS.md` or the `ARCHITECTURAL DRIFT WARNING`:

1. **Read the pending modifications**
2. **Run each verification test**
3. **Confirm or reject** — if a test fails, execute the rollback
4. **Update the mental model** — mark the drift as resolved

```
✅ DRIFT RECONCILED: All pending modifications verified. Mental model synced.
```

## Why This Matters

| Without SMVP | With SMVP |
|---|---|
| Agent makes changes, can't verify them | Agent creates a verifiable audit trail |
| Future sessions assume stale architecture | Future sessions know exactly what changed |
| No rollback strategy | Rollback is documented alongside the change |
| Architectural drift is silent | Drift is explicitly flagged and resolved |

## Applied to the Current Session

Based on Gemini's changes, the SMVP record would look like this:

```markdown
## [SMVP] Modification Record: 2026-05-16

**Files Modified:**
- `delegate_task.ts`, `software_engineer.ts`, `codebase_investigator.ts` — Subagent tracing & IPC stripping via async runner.stream()
- `software_engineer.ts` — Auto-testing via `test_command` schema field
- `codebase_investigator.ts` — Auto-bootstrapping via `tree -L 2`
- `LOCAL_AGENT_CONTEXT.md` — Sovereign Coordinator persona mandates

**Behavioral Impact:**
- Subagent tokens now stream to stdout;  blocks are stripped from IPC payloads
- software_engineer can auto-run tests when Coordinator provides a test_command
- codebase_investigator never "flies blind" — gets directory tree on turn 1
- Coordinator instructed to trust subagents and not echo user requests

**Verification Tests:**
1. Delegate a task — confirm  blocks appear in console but NOT in IPC response
2. Invoke software_engineer with `test_command: "echo TEST"` — confirm "TEST" appears in IPC payload
3. Invoke codebase_investigator — confirm "Auto-Bootstrapped" block in system prompt
4. Send a request — confirm Sovereign Coordinator does NOT echo it in 

**Risk Assessment:**
- **Criticality:** HIGH (core CLI architecture)
- **Rollback:** Revert to git commit pre-dating Gemini's changes
```

**The epiphany:** *Self-modification without verification is architectural amnesia.* The SMVP protocol ensures that when an agent changes its own runtime, the change is documented, testable, and reconcilable — bridging the temporal gap between modification and observation.
