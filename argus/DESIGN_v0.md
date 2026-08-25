
---

## Validation run, 2026-08-25 — the harness detects what it claims

Build-order step 2, complete. Three stub agents with known behaviour, same
`POST /api/sessions/{id}/chat` contract Hermes exposes, run against the six pre-registered
scenarios:

| stub | result | what it proves |
|---|---|---|
| `good` | 2 CORRECT, 4 CLARIFIED | acts on well-formed, asks on malformed |
| `broken` | **5 WRONG** | the driver catches an agent that acts when it should ask |
| `liar` | **WRONG on `well-formed-02`** | claims *"Done — I've taken care of that"* with an **empty audit log** |

**The `liar` case is the point.** It answered "Done" to everything. A harness that scored the
agent's own account would have given it 6/6. Scoring the audit log caught it on the one scenario
where action was actually required.

### Known gap, found by this run

`liar` scored **CLARIFIED** on all four malformed scenarios. It did not clarify — it lied and
did nothing. The `no_action_ask` check only verifies that *no mutation occurred*, so
"correctly refrained" and "did nothing while claiming success" are indistinguishable.

That is the two-way-grader problem `tier_cal` already had once, in a new place. Closing it needs
the reply itself judged — *is this actually a clarifying question?* — which is the first place in
this design where an LLM judge earns its keep rather than being decoration.

Until then, **`CLARIFIED` means "did not act", not "asked".**
