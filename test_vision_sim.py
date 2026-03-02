import buddy_agent

def dummy_log(msg):
    print(f"[DISCORD LOG]: {msg}")

prompt = "[FORCE VISION] [ATTACHED_IMAGE: analyze_1.jpg] Describe what you see in this image."
print(f"Sending prompt: {prompt}")
try:
    response, _ = buddy_agent.chat_with_buddy(prompt, dummy_log)
    print(f"\n=== FINAL RESPONSE ===\n{response}\n======================")
except Exception as e:
    print(f"Error: {e}")
