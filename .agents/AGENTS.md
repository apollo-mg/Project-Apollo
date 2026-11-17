# Apollo Workspace Agent Rules

## TODO List Protocol
When adding new items to `TODO.md`, agents must strictly adhere to the following structure for every single bullet point. This acts as a cognitive filter to ensure practicality and prevent theoretical bloat. 

Every new TODO item MUST include these three fields:
1. **Falsifiable Claim:** The core assumption the task rests on, which can be proven false (e.g., "The SQLite WAL bus can process 500 tasks/sec without locking").
2. **Acceptance Test:** The exact empirical measurement or deterministic check that proves the task is complete and successful.
3. **Rough Cost:** An estimate of the time, tokens, or engineering effort required to implement it.

**Format Example:**
- [ ] **Task Name:** Brief description.
    - *Claim:* [Falsifiable claim]
    - *Test:* [Acceptance test]
    - *Cost:* [Rough cost]

## Compendium
Before touching a machine, a model or a measurement, read its page in `compendium/` (rules in `compendium/README.md`).
