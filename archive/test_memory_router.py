from modules.router import classify_intent
from modules.memory_core import vmm

# Fake some history
vmm.history = [
    {"role": "user", "content": "I prefer to use Rust for all new CLI tools."},
    {"role": "assistant", "content": "Understood. I will default to Rust instead of Python for CLI tasks."}
]
vmm.current_session_tokens = 30000

print("1. Forcing compaction to create a memory in ChromaDB...")
vmm.perform_compaction_flush()

print("\n2. Testing the Router with a vague request...")
result = classify_intent("Write a quick new CLI tool to parse these logs.")
print("\nRouter Result:")
print(result)
