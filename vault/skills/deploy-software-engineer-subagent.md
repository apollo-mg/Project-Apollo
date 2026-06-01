---
name: deploy-software-engineer-subagent
description: Procedure to create and deploy a specialized "Senior Software Engineer" sub-agent tool for heavy implementation tasks. Use when a coding task is too large or error-prone for the main conversational context.
---

# Deploy Software Engineer Sub-Agent

This skill describes how to build a resilient sub-agent tool specifically designed for complex software engineering tasks. This agent operates in an isolated context window with an "Act-then-Refine" mandate.

## Procedure

1. **Define the Coder Profile**:
   Create a dedicated profile in `profiles.json` (e.g., `qwopus_coder`).
   - Use a lower temperature (e.g., `0.1` to `0.4`) for high-accuracy code generation.
   - Use a dense model or a high-quality MoE optimized for coding.

2. **Build the Sub-Agent Tool**:
   Create a native TypeScript tool (e.g., `software-engineer.ts`) that the main agent can invoke.
   - **Inheritance**: Program the tool to dynamically inherit the model and sampling settings from the coder profile.
   - **Loop Allowance**: Set a high turn limit (e.g., `maxTurns: 30`) to give the agent room to iterate through compilation errors and test failures.

3. **Craft the "Act-then-Refine" System Prompt**:
   Initialize the sub-agent with a strict mandate:
   - **Mandate**: "You are a Senior Software Engineer. You must not only write code but also execute it, run tests/benchmarks, and debug failures autonomously."
   - **Process**: Mandate an iterative loop: Write -> Compile -> Test -> Observe Error -> Read Code -> Fix -> Repeat until verified.
   - **Reporting**: Instruct the sub-agent to return only a concise final report to the main conversation once the task is proven to work.

4. **Expose to the Main Architect**:
   Register the new `software_engineer` tool in the main agent's `allowed_tools` list.

## Usage Pattern

- **User**: "Use the software_engineer tool to implement a new token counting utility in modules/utils."
- **Main Agent**: Realizes the task is implementation-heavy, invokes the sub-agent, and waits.
- **Sub-Agent**: Swaps to the coder profile, executes 15 turns of writing, testing, and fixing a `tsconfig.json` error, and then returns: "Utility implemented and verified with 5 green tests."

## Verification Checklist

- [ ] Verify that the sub-agent can autonomously fix its own syntax errors and environment issues (e.g., missing dependencies).
- [ ] Confirm that the main conversation history remains clean, containing only the final report from the sub-agent.
- [ ] Ensure the sub-agent's high turn limit doesn't result in infinite loops by implementing a basic "same-error" detector.

## Pitfalls

- **Context Bloat**: If the sub-agent tries to return the *entire* generated codebase to the main conversational agent, it will defeat the purpose of isolation. Always instruct it to return only a concise status summary.
- **Module Resolution**: Sub-agents often struggle with `tsconfig.json` paths in multi-file projects. Ensure the "Act-then-Refine" prompt explicitly tells them to read the `tsconfig` if they hit compilation errors.
