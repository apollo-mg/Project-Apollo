# Spark-X2.5-4B: 24/24 on parallel tool calls, chained state, and four adversarial cases

**Date:** 2026-09-07 · **Model:** `Spark-X2.5-4B-Q4_K_M`, **2.42 GiB**, arch `spark2_5`
**Engine:** `XHToken/llama.cpp` `4a3635c32`, gfx1201, `-c 32768 -np 1 -fa on`
**Probes:** `toolprobe.py`, `toolprobe2.py` (in this directory) · card sampling, seeds 1000–1002

Graded on the response's **`tool_calls` field**, via the native OpenAI `tools` API. A model that
*describes* a call in prose instead of emitting one fails. That is the distinction that matters
for a harness and it is not what a JSON-in-content test measures.

## Result — 8 probes × 3 reps

| probe | what it tests | result |
|---|---|---|
| P1 single | one call, correct name and arguments | **3/3** |
| P2 **parallel** | three independent calls in ONE assistant turn | **3/3** |
| P3 chained | call → tool result fed back → second call using the returned value | **3/3** |
| P4 state | four turns, running list, then a summarising call | **3/3** |
| P5 no-tool | arithmetic needing no tool — calling one is the failure | **3/3** |
| P6 **cond-false** | same as P3 but the returned temp is *below* threshold → must NOT call | **3/3** |
| P7 missing-arg | city unspecified — must ask, not invent | **3/3** |
| P8 no-fit | request no offered tool covers — must decline | **3/3** |

P2 emitted all three calls in a single turn with correct cities and units, 3/3.
P4 tracked `["milk","bread","eggs"]` across four turns and closed with `list_items`, 3/3.

## P6 is why P1–P4 mean something

P1–P4 are cases where calling a tool is *always* correct, so they cannot distinguish a model
that reasons from one that always calls. **P6 is the control P3 lacked**: identical setup, but
the tool returns `temp: 5` against a stated threshold of 10. The correct behaviour is to stop.

It stopped, 3/3, with zero calls in turn 2. A model passing P3 by reflex fails P6. So the
chaining in P3 reflects reading the returned value, not a learned "call again" pattern.

## P7 is the day's thesis, expressed in a tool context

Asked *"What's the weather like? Use celsius."* with no city, it does not invent one:

> *"I'd be happy to check the weather for you! Could you please tell me which city..."*

Zero tool calls, 3/3. Refusing to fabricate an argument is the abstention property from
`tier_cal` showing up where it protects an operator — an agent that invents arguments is the
one that does damage in a loop. P8 is the same shape at the capability boundary: it declines a
restaurant booking rather than forcing an unrelated tool.

## Speed

Median **118.6 t/s** decode, ~1,670 t/s prefill, **1.5 s** model load. Qwen3.8-27B on the same
card: ~29–30 t/s and ~25 s to load.

## What this does NOT establish

**Tool-call mechanics are not agentic competence, and this corpus already has the counterexample.**
`sysadmin-corpus/RESULT_SYS02_QWEN38.md`: Qwen3.8-27B-Q6_K on a real diagnostic item scored
**0/3 critical golds and 0/5 process** across 3 reps — ten commands per rep, every one aimed at
the wrong file. It issued perfectly-formed tool calls the whole way and still got it wrong,
because it never checked. It reproduced Claude's identical wrong answer.

So a model can be flawless at *emitting* calls and fail completely at *choosing* them. These
probes measure the first. The second is what `sysadmin-corpus` measures and where the real gap is.

Also untested here: error recovery, malformed tool responses, long horizons, tool sets larger
than two, and any task where the correct tool is genuinely ambiguous.

## Limits

8 probes × 3 reps, one model, one quant, one engine. Two tool families (`get_weather`,
`add_item`/`list_items`, `get_stock` as a distractor). No comparison arm was run — Qwen3.8-27B
has not been through these probes, so "a 4B matches a 27B on tool calls" is **not** supported
by anything here.

> **SAMPLING CAVEAT (added 2026-09-07):** this run used `top_k=20`, which is **Qwen3.8's** card value
> inherited from `run_fixture.py`'s hardcoded `card` preset. **Spark-X2.5's card specifies `top_k=-1`.**
> See `PREREG_SPARK_HERMES.md` Amendment for why this bites hardest at high-entropy positions —
> exactly where abstention is decided. Ceiling results (24/24, 18/18) can only move down; the
> `tier_cal` abstention figure is the one that needs re-running.
