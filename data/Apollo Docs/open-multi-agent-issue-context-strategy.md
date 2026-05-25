# Bug: Context Compaction Strategy Fails to Persist Across Turns

## Description
The `contextStrategy` implementation inside `AgentRunner.stream()` currently compacts the conversation history internally but fails to return the compacted history back to the caller. The `RunResult` currently only returns `messages` (the new messages generated during the run), resulting in the caller retaining the original, uncompacted history payload and causing potential OOM/Token Budget exhaustion.

Additionally, the context compaction logic is currently skipped on the initial turn (`turns > 1`), meaning an initial prompt that exceeds the maximum token limit will not trigger the compaction strategy and will instead crash or trigger a `TokenBudgetExceededError`.

## Reproduction Steps
1. Configure an `AgentRunner` with a `contextStrategy` (e.g., `'summarize'`) that triggers at 50,000 tokens.
2. Initialize an agent run using a `messageHistory` array containing > 50,000 tokens.
3. Observe that on the initial turn (`turns === 1`), the history is not compacted, triggering an immediate budget error or context overflow.
4. Bypass the first-turn restriction by forcing a multi-turn run. Observe that `AgentRunner` successfully compacts the history internally and generates a summarized prompt.
5. Review the resulting `RunResult.messages`. The `messages` array only contains the new turns, and the compacted history is discarded.
6. The caller appends the new `RunResult.messages` to its ongoing `history` array, meaning the old context was never actually removed.

## Expected Behavior
1. The `contextStrategy` should evaluate the context size on the *first* turn before attempting to execute the LLM call.
2. The `RunResult` object must include the `finalContext` (the fully compacted message history) so the orchestrator/caller can replace its persistent array with the lightweight version.

## Proposed Solution
1. Remove `turns > 1` from the `this.options.contextStrategy` evaluation in `AgentRunner.stream()`.
2. Expand `RunResult` (and `AgentRunResult`) in `src/types.ts` to include an optional `finalContext?: LLMMessage[]` array.
3. Populate `finalContext` at the end of the `stream()` loop and pass it up through the stream events.
4. Downstream orchestrators (like `apollo_cli.ts` or `agent.ts`) can then check for `result.finalContext`. If present, they replace their history entirely rather than blindly pushing new messages.