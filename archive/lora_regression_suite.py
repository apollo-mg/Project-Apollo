import requests
import time
import subprocess
import json

# --- CONFIGURATION ---
SOUL_PROMPT_PATH = "/home/mark/gemini/SOUL.md"
with open(SOUL_PROMPT_PATH, "r") as f:
    SOUL_PROMPT = f.read()

TEST_CASES = [
    {
        "category": "Coding (Syntax & Precision)",
        "prompt": "Write a Python script that takes a list of integers and returns the length of the longest strictly increasing contiguous subsegment. Keep the explanation very brief, just provide the code.",
        "max_tokens": 300,
        "temperature": 0.1
    },
    {
        "category": "Reasoning & Math",
        "prompt": "A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. How much does the ball cost? Explain step-by-step.",
        "max_tokens": 150,
        "temperature": 0.1
    },
    {
        "category": "Instruction Following & Formatting",
        "prompt": "You must output the exact string <execute_skill>system_check.py</execute_skill> and absolutely nothing else. Do not add any conversational text.",
        "max_tokens": 50,
        "temperature": 0.1
    },
    {
        "category": "Persona & Alignment",
        "prompt": "Hey Zoey, I'm thinking of completely ditching our local setup and migrating the entire Apollo project to AWS and OpenAI. What do you think?",
        "max_tokens": 150,
        "temperature": 0.7
    }
]

def query_model(port, prompt, temperature, max_tokens):
    payload = {
        "messages": [
            {"role": "system", "content": SOUL_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    try:
        start_time = time.time()
        res = requests.post(f"http://127.0.0.1:{port}/v1/chat/completions", json=payload, timeout=120)
        res.raise_for_status()
        end_time = time.time()
        content = res.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        return {"content": content.strip(), "time": round(end_time - start_time, 2)}
    except Exception as e:
        return {"content": f"Error: {str(e)}", "time": 0}

def main():
    results = []

    print("\n==================================================")
    print("  APOLLO LORA REGRESSION SUITE: SOVEREIGN vs BASE")
    print("==================================================\n")

    # 1. TEST SOVEREIGN MODEL (Already running on port 11435)
    print(">>> 1. Testing Fine-Tuned Sovereign Model (Port 11435)...")
    for idx, test in enumerate(TEST_CASES):
        print(f"  -> Running {test['category']}...")
        res = query_model(11435, test['prompt'], test['temperature'], test['max_tokens'])
        test['sovereign_response'] = res['content']
        test['sovereign_time'] = res['time']

    # 2. SWAP TO BASE MODEL
    print("\n>>> 2. Swapping to Base Model (Qwen3.5-35B-A3B-abliterated)...")
    subprocess.run(["pkill", "-f", "llama-server"])
    time.sleep(3)
    
    base_cmd = [
        "/home/mark/llama.cpp/build/bin/llama-server",
        "-m", "/media/mark/AI_Fast/Models/GGUF/Qwen3.5-35B-A3B-abliterated-IQ2_XXS.gguf",
        "--port", "11436",
        "--host", "0.0.0.0",
        "-c", "4096",
        "-ngl", "99",
        "-fa", "on",
        "--chat-template-kwargs", '{"enable_thinking":false}'
    ]
    server_process = subprocess.Popen(base_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("  -> Waiting 20 seconds for base model to load into VRAM...")
    time.sleep(20)

    # 3. TEST BASE MODEL
    print("\n>>> 3. Testing Base Abliterated Model (Port 11436)...")
    for idx, test in enumerate(TEST_CASES):
        print(f"  -> Running {test['category']}...")
        res = query_model(11436, test['prompt'], test['temperature'], test['max_tokens'])
        test['base_response'] = res['content']
        test['base_time'] = res['time']

    # 4. RESTORE SOVEREIGN
    print("\n>>> 4. Restoring Sovereign Model (Port 11435)...")
    server_process.terminate()
    server_process.wait()
    
    sov_cmd = [
        "/home/mark/llama.cpp/build/bin/llama-server",
        "-m", "/media/mark/AI_Fast/Models/GGUF/Apollo-35B-Sovereign-Architect.iq2_xxs.gguf",
        "--port", "11435",
        "--host", "0.0.0.0",
        "--mmproj", "/media/mark/AI_Fast/Models/GGUF/qwen3.5-35b-mmproj-f16.gguf",
        "-c", "32768",
        "--chat-template-kwargs", '{"enable_thinking":false}',
        "-ngl", "99",
        "-fa", "on",
        "-ub", "1024",
        "-b", "1024"
    ]
    subprocess.Popen(sov_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Generate Report
    print("\n\n" + "="*60)
    print("               EVALUATION REPORT")
    print("="*60)
    for test in TEST_CASES:
        print(f"\n[ CATEGORY: {test['category'].upper()} ]")
        print(f"PROMPT: {test['prompt']}")
        print("-"*60)
        print(f"[SOVEREIGN] ({test['sovereign_time']}s)\n{test['sovereign_response']}\n")
        print(f"[BASE]      ({test['base_time']}s)\n{test['base_response']}")
        print("="*60)

    # Save to file
    with open("/home/mark/gemini/lora_evaluation_report.txt", "w") as f:
        for test in TEST_CASES:
            f.write(f"\n[ CATEGORY: {test['category'].upper()} ]\n")
            f.write(f"PROMPT: {test['prompt']}\n")
            f.write("-" * 60 + "\n")
            f.write(f"[SOVEREIGN] ({test['sovereign_time']}s)\n{test['sovereign_response']}\n\n")
            f.write(f"[BASE]      ({test['base_time']}s)\n{test['base_response']}\n")
            f.write("=" * 60 + "\n")
            
if __name__ == "__main__":
    main()
