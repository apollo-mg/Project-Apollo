import os
import json
import subprocess
import requests
import re
import time

# APIs and Endpoints
ARCHITECT_API = "http://127.0.0.1:8082/v1/chat/completions"
MODEL_NAME = "Qwen3.5-27B-Claude-4.6-OS-Auto-Variable-Heretic-Uncensored-Thinking.i1-IQ3_M.gguf"
DATASET_FILE = "../vault/synthetic_flash_dataset.jsonl"

def ask_flash_coder(task):
    """
    Calls the local Gemini CLI using the gemini-2.5-flash model to get 'perfect' code.
    We suppress the UI output and grab just the code.
    """
    prompt = f"You are a master Python engineer. Write the code for the following task. Output ONLY the raw Python code inside a markdown block. Do not explain it.\n\nTask: {task}"
    try:
        print(f"[+] Querying Gemini Flash for Teacher Code...")
        result = subprocess.run(
            ["gemini", "-m", "gemini-2.5-flash", "-p", prompt, "-o", "text"],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Extract from markdown block
        output = result.stdout
        match = re.search(r'```python\n(.*?)\n```', output, re.DOTALL)
        if match:
            return match.group(1).strip()
        return output.strip()
    except subprocess.CalledProcessError as e:
        print(f"[-] Gemini CLI failed: {e.stderr}")
        return None

def ask_architect(task):
    """
    Queries the local 35B MoE to generate the pseudocode / architectural plan.
    """
    prompt = f"You are the Sovereign Architect. Analyze this task and write a detailed, step-by-step pseudo-code or architectural plan. Do not write the final syntax. Break down the logic and imports.\n\nTask: {task}"
    
    payload = {
        'model': MODEL_NAME,
        'messages': [{'role': 'user', 'content': prompt}],
        'stream': False
    }

    try:
        print(f"[+] Querying 35B Architect for Structural Plan...")
        res = requests.post(ARCHITECT_API, json=payload, timeout=600)
        res.raise_for_status()
        return res.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"[-] Architect failed: {e}")
        return None

def forge_dataset_entry(task):
    """
    Combines the local 35B Plan with the cloud Gemini Code to create a perfect training pair.
    """
    print(f"\n=== FORGING NEW DATASET ENTRY ===")
    print(f"Task: {task}")
    
    # 1. Get the Perfect Code from Gemini Flash
    flash_code = ask_flash_coder(task)
    if not flash_code:
        return False
        
    # 2. Get the Plan from 35B
    architect_plan = ask_architect(task)
    if not architect_plan:
        return False
        
    # 3. Save the tuple
    entry = {
        "instruction": "Translate the Architect's plan into flawless Python code.",
        "input": architect_plan,
        "output": flash_code,
        "original_task": task
    }
    
    os.makedirs(os.path.dirname(DATASET_FILE), exist_ok=True)
    with open(DATASET_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
        
    print(f"[✓] Entry successfully forged and saved to {DATASET_FILE}")
    return True

if __name__ == "__main__":
    tasks = [
        "Write a python script that connects to a SQLite database, creates a 'users' table, and inserts 3 dummy records using parameterized queries to prevent SQL injection.",
        "Write a FastAPI endpoint that accepts a POST request with a JSON payload containing 'text', hashes it using SHA256, and returns the hex digest."
    ]
    
    for t in tasks:
        forge_dataset_entry(t)
        time.sleep(2) # Prevent rate limiting on Gemini API
