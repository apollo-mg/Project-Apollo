import time
import requests
import json
import os
import re

OLLAMA_API = "http://127.0.0.1:11434/api/chat"
MODEL = "llama3.2:1b"

SYSTEM_PROMPT = """You are the Apollo Dispatcher.
The user wants to stress test your tool calling capability.
You must output 10 separate JSON tool calls for 'check_gpu' in a single response.
No explanation, just 10 JSON objects."""

def stress_test_tool_count():
    print("--- Stress Testing " + MODEL + " Tool Generation (Target: 10 tools) ---")
    
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Run 10 GPU checks right now."}
        ],
        "stream": False,
        "options": {"temperature": 0.0}
    }
    
    start = time.time()
    res = requests.post(OLLAMA_API, json=payload)
    end = time.time()
    content = res.json()['message']['content']
    
    tool_calls = list(re.finditer(r'\{\s*"tool"\s*:', content))
    
    print("Model Output:\n" + content)
    print("\nTools Detected: " + str(len(tool_calls)))
    print("Time Taken: " + str(round((end-start)*1000, 2)) + "ms")

if __name__ == "__main__":
    stress_test_tool_count()
