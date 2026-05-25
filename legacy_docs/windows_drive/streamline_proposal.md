# PROPOSAL: Unified Tool Interception (UTI)
**Goal:** Reduce latency by 60% by eliminating the 3-pass Llama/DeepSeek split.

## Current Workflow:
1. Pass 1: Llama (Bouncer)
2. Pass 2: System Feedback (if failed)
3. Pass 3: DeepSeek (Reasoning)

## Proposed Workflow (Single Pass):
1. **Unified Call:** We send the prompt ONLY to DeepSeek-R1.
2. **Thinking Interception:** We use a regex to watch for `ACTION:` or ````json` *inside* the model's generated thought process.
3. **Execution Break:** If a tool call is detected, the script interrupts the stream, runs the tool, appends the result to the context, and restarts the generation.
4. **Final output:** The user only sees the final, grounded answer.

## Feedback Request:
Buddy, as the lead engineer, do you think DeepSeek-R1 is disciplined enough to consistently output a tool call block before it starts its "Final Answer" text if we simplify the system prompt? Or will you fall back into the "47 ohms" trap?
