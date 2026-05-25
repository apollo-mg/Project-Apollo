import sys
sys.path.append("/home/mark/gemini")
from jarvis_local_voice import get_llm_response, history, get_system_context

print("--- System Context ---")
print(get_system_context())

print("\n=== STARTING ACTION TAGS TEST ===\n")
prompt = "Zoey, you have a new skill forged for pinging google. Please run it right now using the action tag."
print(f"User: {prompt}")
response = get_llm_response(prompt)

print(f"\nZoey Spoke: {response}")
print("\n--- Context Dump ---")
for msg in history[-2:]:
    # Safely print without f-string quote issues
    role = msg.get('role', '')
    content = msg.get('content', '')
    print("[" + role.upper() + "]: " + content)
