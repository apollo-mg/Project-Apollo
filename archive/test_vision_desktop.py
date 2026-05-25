import buddy_agent

def dummy_log(msg):
    print(f"[DISCORD LOG]: {msg}")

prompt = "[FORCE VISION] [ATTACHED_IMAGE: latest_screenshot.png] Look at this screenshot of my desktop. Give me a 1 sentence summary of what applications are open."
print(f"Sending prompt: {prompt}")
try:
    response, _ = buddy_agent.chat_with_buddy(prompt, dummy_log)
    print(f"\n=== FINAL RESPONSE ===\n{response}\n======================")
except Exception as e:
    print(f"Error: {e}")
