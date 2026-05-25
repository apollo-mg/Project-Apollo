import sys
import json
import requests
import os

# Grab the prompt from CLI arguments
prompt = sys.argv[1] if len(sys.argv) > 1 else "Write a simple hello world in python."

# If we were using an API key directly, we could call it here. 
# But let's build this as a standalone tool script to wrap Flash via the API if an API key exists in the environment.
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("Error: GEMINI_API_KEY not set. Cannot spawn external Flash agent directly via API.")
    sys.exit(1)

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
headers = {'Content-Type': 'application/json'}
payload = {
    "contents": [{"parts": [{"text": "You are a raw coder. Output only code. " + prompt}]}]
}

try:
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()
    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    print(text.strip())
except Exception as e:
    print(f"Failed to call Flash API: {e}")
