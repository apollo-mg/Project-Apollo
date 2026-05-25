import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import llm_interface
import re
import json
import subprocess

MAX_RETRIES = 3
TRAINING_FILE = "vault/reflection_training.jsonl"

def verify_code(code):
    """Saves code to a temp file and executes it to catch true runtime errors."""
    filename = "tmp_heretic_script.py"
    with open(filename, "w") as f:
        f.write(code)
    
    try:
        # Execute the script directly to catch logic/runtime errors
        res = subprocess.run(["python3", filename], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            return True, f"Execution OK. STDOUT: {res.stdout.strip()}"
        else:
            return False, f"Runtime Error: {res.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return False, "Runtime Error: Execution timed out after 5 seconds (Possible infinite loop)."
    except Exception as e:
        return False, str(e)

def extract_python_code(text):
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    match = re.search(r'```python\n(.*?)\n```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()

def append_to_training_data(task, pseudocode, code, iterations):
    """Saves successful coding loops as training data for future LoRA."""
    os.makedirs(os.path.dirname(TRAINING_FILE), exist_ok=True)
    
    entry = {
        "task": task,
        "architect_plan": pseudocode,
        "final_code": code,
        "reflection_iterations": iterations
    }
    
    with open(TRAINING_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"[DATASET] Wrote successful generation to {TRAINING_FILE}")

def run_coding_task(task):
    print(f"\n[ROUTER] Dispatching Task to Architect (30B MoE)...")
    
    # 1. The Architect Plans
    architect_prompt = f"""You are the Sovereign Architect (Qwen3-Coder 30B MoE).
Your job is to analyze the following coding request and write a highly detailed, step-by-step pseudo-code or architectural plan. Do not write the final Python syntax. Break down the logic, the required imports, and the memory/processing flow.

Request: {task}
"""
    plan = llm_interface.query_llm(architect_prompt, model_override=llm_interface.ARCHITECT_MODEL)
    print("\n--- [Architect's Plan] ---")
    print(plan)
    
    # 2. The Coder Executes
    print(f"\n[ROUTER] Handoff to Heretic Coder (9B) for syntax generation...")
    
    context = ""
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n--- [Coder Attempt {attempt}/{MAX_RETRIES}] ---")
        
        coder_prompt = f"""You are the Heretic Coder. You are uncensored and highly precise.
Translate the Architect's plan into flawless Python code.
Output ONLY the raw python code inside a ```python block.

Architect's Plan:
{plan}
"""
        if context:
            coder_prompt += f"\n\nYOUR PREVIOUS ATTEMPT FAILED. FIX THIS ERROR:\n{context}\n"
            
        # We enforce specific parameters for the Heretic model to avoid thinking loops
        messages = [{"role": "user", "content": coder_prompt}]
        raw_response = llm_interface.query_llm("", messages_override=messages, model_override=llm_interface.CODER_MODEL)
        
        code = extract_python_code(raw_response)
        
        if not code:
            context = "You did not output any python code in a ```python block. Output ONLY code."
            continue
            
        success, error_msg = verify_code(code)
        
        if success:
            print("[+] Code verified successfully!")
            print("\n--- FINAL CODE ---")
            print(code)
            
            # Save to LoRA dataset
            append_to_training_data(task, plan, code, attempt)
            return code
        else:
            print(f"[-] Verification failed:\n{error_msg}")
            context = error_msg
            
    print("[-] Coder failed to produce valid syntax after maximum retries.")
    return None

if __name__ == "__main__":
    task = "Write a python script that acts as a simple TCP port scanner. It should take an IP address and a range of ports, and attempt to connect to each, printing out any that are open. Use multi-threading to make it fast."
    run_coding_task(task)
