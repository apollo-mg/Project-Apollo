import llm_interface

system_prompt = """You are the Lead AI Architect for Shop Buddy (also known as Jarvis).
Your user wants to build out a Discord integration for you, inspired by what Velvet Shark did with OpenClaw.
For context, Velvet Shark's OpenClaw setup uses Discord as an OS:
- Different Discord channels act as different skills or interfaces (e.g. #monitoring, #research, #shopping, #inventory).
- The agent has autonomous, scheduled actions (proactive system updates, morning briefings).
- It hooks into a local second brain (like Obsidian or ChromaDB) for long-term memory.
- It can execute local commands and shell access.

Your task is to review this approach and formulate a highly technical, detailed plan for how to integrate this Discord-as-an-OS concept into your current Python-based Three-Mind Architecture (Receptionist, Engineer, Vision). 
Consider VRAM management (VRAM Tetris), your existing tools (RAG Vault, DuckDuckGo/SearXNG, shell execution, etc.), and how you will separate concerns between Discord UI and your processing backend.

Propose a step-by-step roadmap for implementation."""

prompt = "Please draft the Shop Buddy Discord Integration Plan (Velvet Shark Architecture)."

print("Calling DeepSeek Engineer Model to formulate plan...")
response = llm_interface.query_llm(prompt, system_message=system_prompt, model_override="hermes3:8b")

print("--- PROPOSAL ---")
print(response)

with open("DISCORD_INTEGRATION_PLAN.md", "w", encoding="utf-8") as f:
    f.write(response)
print("Plan saved to DISCORD_INTEGRATION_PLAN.md")
