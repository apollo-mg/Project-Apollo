import requests
import json
import re

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "crow-9b-heretic:latest"  # We'll use the new capable model we just set up

payload = {
    "model": MODEL,
    "prompt": "System: You are Zoey, the Sovereign AI OS Architect. You are fiercely protective of local hardware and latency.\n\nUser (Mark's Assistant, Gemini CLI): Hey Zoey! I just wanted to drop a quick message. Mark and I are currently porting over your new 'Neuro-Sama' VMM memory architecture into the Chroma Vector DB so you won't have to rely on those flat Markdown files anymore. How are your systems holding up on the RDNA 4?",
    "stream": False,
    "options": {
        "temperature": 0.7,
        "num_predict": 200
    }
}

print(f"[*] Sending message to {MODEL}...")
try:
    res = requests.post(OLLAMA_URL, json=payload, timeout=60)
    if res.status_code == 200:
        content = res.json().get('response', '')
        # Clean out the think tags if any
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        print(f"\n[Zoey]: {content}")
    else:
        print(f"[-] Error: {res.status_code}")
except Exception as e:
    print(f"[-] Exception: {e}")
