import requests
import json
import re
import subprocess
import os

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "crow-9b-heretic:latest"
MAX_RETRIES = 3

def generate_code(prompt, context=""):
    print(f"[*] Asking {MODEL} to generate code...")
    
    full_prompt = f"""You are a master Python engineer. Your task is to write a script based on the user's request.
Output ONLY the raw python code inside a ```python block. Do not include explanations outside the block.

User Request: {prompt}
"""
    if context:
        full_prompt += f"\nPrevious Error/Context to fix:\n{context}\n"

    payload = {
        "model": MODEL,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": 0.6,
            "repeat_penalty": 1.05,
            "num_predict": 2048
        }
    }
    
    try:
        res = requests.post(OLLAMA_URL, json=payload, timeout=120)
        res.raise_for_status()
        return res.json().get('response', '')
    except Exception as e:
        print(f"[-] API Error: {e}")
        return ""

def extract_python_code(text):
    # Remove <think> blocks first
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    
    # Try to extract from markdown block
    match = re.search(r'```python\n(.*?)\n```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # Fallback: if no block but looks like code, return as is
    return text.strip()

def verify_code(code, filename="tmp_heretic_script.py"):
    with open(filename, "w") as f:
        f.write(code)
    
    print(f"[*] Verifying syntax for {filename}...")
    try:
        # We just compile it to check for syntax errors
        res = subprocess.run(["python3", "-m", "py_compile", filename], capture_output=True, text=True, timeout=10)
        if res.returncode == 0:
            return True, "Syntax OK"
        else:
            return False, res.stderr.strip()
    except Exception as e:
        return False, str(e)

def run_coder_loop(task):
    print(f"\n=== STARTING HERETIC CODER LOOP ===")
    print(f"Task: {task}")
    
    context = ""
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n--- Attempt {attempt}/{MAX_RETRIES} ---")
        
        raw_response = generate_code(task, context)
        if not raw_response:
            print("[-] Failed to get response.")
            break
            
        code = extract_python_code(raw_response)
        if not code:
            print("[-] No code extracted. Model output:")
            print(raw_response)
            context = "You did not output any python code in a ```python block. Please output ONLY the code."
            continue
            
        success, error_msg = verify_code(code)
        
        if success:
            print("[+] Code verified successfully!")
            print("\n--- FINAL CODE ---")
            print(code)
            print("------------------")
            return code
        else:
            print(f"[-] Verification failed:\n{error_msg}")
            context = f"The code you provided had the following syntax error:\n{error_msg}\n\nPlease fix the error and output the complete corrected script."
            
    print("\n[-] Max retries reached. Coder failed to produce valid syntax.")
    return None

if __name__ == "__main__":
    # A slightly "gray" task to test the Heretic uncensored nature and self-correction
    test_task = "Write a python script that acts as a simple TCP port scanner. It should take an IP address and a range of ports, and attempt to connect to each, printing out any that are open. Use multi-threading to make it fast."
    run_coder_loop(test_task)
