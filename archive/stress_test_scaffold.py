import requests
import time
import json

# Adjusting the prompt to be extremely strict about the tags, because the conversational fine-tune makes her want to talk instead of act.
user_prompt = """
You are a machine automation agent. You must output the requested architecture strictly using XML tags.
Do not describe the files. Just emit the tags.

I need a complete, multi-file Hardware Topology Mapper to understand the current OS state.
Create it inside a folder called 'hardware_mapper'.

Requirements:
1. Use a shell command to create the directory structure: 'hardware_mapper/core'
2. Write 'hardware_mapper/core/cpu.py' that gets the CPU model via /proc/cpuinfo.
3. Write 'hardware_mapper/core/gpu.py' that runs rocm-smi to get the GPU model.
4. Write 'hardware_mapper/main.py' that imports both of those, prints a formatted system report, and exits.

You MUST use <execute_shell> and <write_file path="..."> for every action.
"""

payload = {
    "messages": [
        {"role": "user", "content": user_prompt}
    ],
    "temperature": 0.1,
    "max_tokens": 1500
}

print("Running Stricter Stress Test against 35B Sovereign Model...")
try:
    res = requests.post("http://10.0.0.5:11435/v1/chat/completions", json=payload, timeout=120)
    res.raise_for_status()
    
    content = res.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    print(f"\n--- ZOEY'S RESPONSE ---\n")
    print(content)
except Exception as e:
    print(f"Test Failed: {e}")
