import time
import requests
import json
import statistics
import sys
import pandas as pd
import os

OLLAMA_API = "http://127.0.0.1:11434/api/chat"

# Models to Test
MODELS = ["llama3.1:8b", "qwen2.5:7b", "hermes3:8b"]

# Test Cases: Mixture of CHAT (Social/Vague) and WORK (Tools)
# HARD MODE: Ambiguous, Colloquial, Multi-step, Vague References
TEST_CASES = [
    # CHAT / VAGUE (Should return intent="CHAT")
    "I think the z-offset is wrong on the voron",  # Vague complaint -> Chat
    "The nozzle is clogging again",                # Troubleshooting -> Chat
    "Get me the thing for the board",              # Missing object -> Chat (Clarify)
    "Actually, never mind",                        # Cancellation -> Chat
    "It's making that weird noise again",          # Vague -> Chat
    "Can you double check that?",                  # Context dependent (assume Chat/Clarify if no context) -> Chat
    "I need a manual",                             # Vague -> Chat (Which one?)
    "I hate bed adhesion issues",                  # Complaint -> Chat
    "Download it",                                 # Context missing -> Chat
    "Thanks Jarvis",                               # Social -> Chat

    # WORK (Should return intent="WORK")
    "Check the hotend temperature",                # Specific telemetry -> Work
    "Find the pinout for the BTT Octopus",         # Specific search -> Work
    "Scan the vault now",                          # Specific action -> Work
    "Add a 5mm Allen key to the workbench",        # Specific inventory -> Work
    "What is the current bed temp?",               # Specific telemetry -> Work
    "Download the datasheet for the TMC2209",      # Specific download -> Work
    "List all PDF files we have",                  # Specific list -> Work
    "Take a picture of the bed",                   # Specific vision -> Work
    "Search for the EBB36 schematic",              # Specific search -> Work
    "Run the system diagnostics"                   # Specific action -> Work
]

RECEPTIONIST_PROMPT = """You are JARVIS, the Shop Receptionist.
Your goal is to classify the user's intent into one of two categories.

CATEGORIES:
1. "CHAT": 
   - Vague complaints ("My printer isn't working")
   - Clarification requests ("Which one?")
   - Social interaction ("Hi", "Thanks")
   - Requests lacking specific details ("Download a manual")
   - Troubleshooting discussions without specific tool commands.

2. "WORK": 
   - Specific requests for data ("Check bed temp", "Show me the webcam")
   - Specific file searches ("Find the Voron 2.4 manual")
   - Inventory actions ("Add a 10mm socket")
   - System commands ("Scan the vault", "Run diagnostics")

EXAMPLES:
User: "My prints are failing." -> {"intent": "CHAT", "reply": "I can help. What seems to be the issue?"}
User: "Check the hotend temperature." -> {"intent": "WORK", "refined_task": "check_temperature(hotend)"}
User: "I need a manual." -> {"intent": "CHAT", "reply": "Which manual do you need?"}
User: "Find the datasheet for the TMC2209." -> {"intent": "WORK", "refined_task": "search_vault(TMC2209 datasheet)"}
User: "Take a photo of the print." -> {"intent": "WORK", "refined_task": "capture_image()"}

Output ONLY JSON:
{
  "intent": "CHAT" or "WORK",
  "reply": "Optional clarification or response",
  "refined_task": "Optional technical description of the task"
}"""

def run_benchmark():
    results = []
    print(f"Starting Receptionist Benchmark on {len(MODELS)} models...")
    print("-" * 60)

    for model in MODELS:
        print(f"\nTesting Model: {model}")
        
        # Warmup (1 query to load into VRAM)
        print("  Warming up...", end="", flush=True)
        try:
            requests.post(OLLAMA_API, json={"model": model, "messages": [{"role": "user", "content": "hi"}]})
            print(" Done.")
        except Exception as e:
            print(f" Failed to load {model}: {e}")
            continue

        latencies = []
        correct_intents = 0
        total_tokens = 0
        
        for i, prompt in enumerate(TEST_CASES):
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": RECEPTIONIST_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "options": {"temperature": 0.1} # Low temp for consistency
            }
            
            start = time.time()
            try:
                res = requests.post(OLLAMA_API, json=payload)
                end = time.time()
                data = res.json()
                
                latency = (end - start) * 1000 # ms
                latencies.append(latency)
                
                content = data['message']['content']
                eval_tokens = data.get('eval_count', 0)
                total_tokens += eval_tokens
                
                # Check accuracy
                expected = "CHAT" if i < 10 else "WORK"
                detected = "UNKNOWN"
                if '"intent": "CHAT"' in content or '"intent": "chat"' in content: detected = "CHAT"
                elif '"intent": "WORK"' in content or '"intent": "work"' in content: detected = "WORK"
                
                is_correct = (expected == detected)
                if is_correct: correct_intents += 1
                
                print(f"    [{i+1}/{len(TEST_CASES)}] '{prompt}' -> {detected} ({latency:.0f}ms)")
                
            except Exception as e:
                print(f"    Error: {e}")

        # Unload model to be fair to the next one
        requests.post(OLLAMA_API, json={"model": model, "keep_alive": 0})
        
        # Stats
        avg_lat = statistics.mean(latencies) if latencies else 0
        accuracy = (correct_intents / len(TEST_CASES)) * 100
        tps = (total_tokens / (sum(latencies)/1000)) if latencies else 0
        
        results.append({
            "Model": model,
            "Avg Latency (ms)": round(avg_lat, 2),
            "Accuracy (%)": round(accuracy, 2),
            "Tokens/Sec": round(tps, 2)
        })

    # Display Table
    print("\n" + "="*60)
    print("FINAL BENCHMARK RESULTS")
    print("="*60)
    df = pd.DataFrame(results)
    print(df.to_string(index=False))
    
    # Save CSV
    csv_path = "llm_benchmark_receptionist.csv"
    mode = 'a' if os.path.exists(csv_path) else 'w'
    header = not os.path.exists(csv_path)
    df['Timestamp'] = time.strftime("%Y-%m-%d %H:%M:%S")
    df.to_csv(csv_path, mode=mode, header=header, index=False)
    print(f"\nSaved to {csv_path}")

if __name__ == "__main__":
    run_benchmark()
