import time
import random
import os
import sys
import threading
import subprocess
import urllib.request
import urllib.error
import json
import shutil
import psutil
import re

# Ensure we can import from the Apollo root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configuration
IDLE_CPU_THRESHOLD = 15.0  # If CPU is above 15%, system is not idle
IDLE_GPU_THRESHOLD = 15.0  # If EWMA GPU usage is above 15%, system is not idle
CHECK_INTERVAL = 60        # Check every 60 seconds
DAYDREAM_COOLDOWN = 600    # Wait 10 minutes between daydreams
PAUSE_FILE = "/mnt/TG_2TB/Projects/Apollo/daydream_pause.lock" 
HISTORY_DIR = "/mnt/TG_2TB/Projects/Apollo/chat_history/local"
LLM_API_URL = "http://127.0.0.1:8082/v1/chat/completions" # Defaulting to the local endpoint
MESSAGE_BUS_API = "http://127.0.0.1:8000/memory/proposed"

# --- Agnostic GPU EWMA Monitor ---
gpu_ewma = 0.0
gpu_ewma_lock = threading.Lock()

def get_current_gpu_usage():
    """Hardware agnostic GPU usage check (NVIDIA -> AMD -> CPU fallback)."""
    # 1. Try NVIDIA (P100 node)
    if shutil.which("nvidia-smi"):
        try:
            res = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True)
            usages = [float(x.strip()) for x in res.stdout.strip().split('\n') if x.strip().isdigit()]
            return max(usages) if usages else 0.0
        except Exception:
            pass
            
    # 2. Try AMD ROCm (9070 XT node)
    if shutil.which("rocm-smi"):
        try:
            res = subprocess.run(["rocm-smi", "-u", "--json"], capture_output=True, text=True)
            stdout = res.stdout
            start_idx = stdout.find('{')
            if start_idx != -1:
                data = json.loads(stdout[start_idx:])
                for card in data:
                    if isinstance(data[card], dict) and "GPU use (%)" in data[card]:
                        return float(data[card]["GPU use (%)"])
        except Exception:
            pass
            
    return 0.0 # CPU fallback

def gpu_monitor_loop():
    global gpu_ewma
    alpha = 0.2 # Smoothing factor. Lower = slower response.
    while True:
        current_usage = get_current_gpu_usage()
        with gpu_ewma_lock:
            gpu_ewma = (alpha * current_usage) + ((1 - alpha) * gpu_ewma)
        time.sleep(2) # Sample every 2 seconds

threading.Thread(target=gpu_monitor_loop, daemon=True).start()
# ------------------------

def is_system_idle():
    """Checks if the system is considered 'idle' based on CPU usage, GPU EWMA, and pause lock."""
    if os.path.exists(PAUSE_FILE):
        return False
    
    with gpu_ewma_lock:
        current_gpu_ewma = gpu_ewma
        
    if current_gpu_ewma > IDLE_GPU_THRESHOLD:
        return False
    
    # Check CPU usage over a 3-second window
    cpu_percent = psutil.cpu_percent(interval=3)
    if cpu_percent > IDLE_CPU_THRESHOLD:
        return False
    
    return True

def get_history_chunks():
    """Pulls random chat history files to act as Daydream context."""
    if not os.path.exists(HISTORY_DIR):
        return None, None
        
    files = [os.path.join(HISTORY_DIR, f) for f in os.listdir(HISTORY_DIR) if f.endswith('.md') or f.endswith('.json')]
    if not files:
        return None, None
        
    # Sort files by modification time
    files.sort(key=os.path.getmtime)
    
    # Take the most recent file and one random historical file
    recent_file = files[-1]
    historical_file = random.choice(files[:-1]) if len(files) > 1 else None
    
    try:
        with open(recent_file, 'r', encoding='utf-8') as f:
            recent_chunk = f.read()[:8000] # Limit tokens
    except:
        recent_chunk = ""
        
    historical_chunk = None
    if historical_file:
        try:
            with open(historical_file, 'r', encoding='utf-8') as f:
                historical_chunk = f.read()[:8000]
        except:
            historical_chunk = None
            
    return recent_chunk, historical_chunk

def call_llm(messages, temperature=1.0, response_format=None):
    """Wrapper for interacting with the local llama-server via OpenAI API format."""
    payload = {
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 4096
    }
    if response_format:
        payload["response_format"] = response_format
        
    try:
        req = urllib.request.Request(
            LLM_API_URL,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=300) as res:
            data = json.loads(res.read().decode('utf-8'))
        return data['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"LLM API Error: {e}")
        return None

def push_to_inbox(title, tldr, payload, token_impact=0):
    """Pushes the filtered skill to the SQLite Message Bus Memory Inbox."""
    try:
        req = urllib.request.Request(
            MESSAGE_BUS_API,
            data=json.dumps({
                "title": title,
                "tldr": tldr,
                "token_impact": token_impact,
                "raw_payload": payload
            }).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req) as res:
            print("📬 Epiphany successfully pushed to Memory Inbox!")
    except Exception as e:
        print(f"Failed to push to Message Bus: {e}")

def trigger_daydream():
    """Executes the dual-pass daydream logic."""
    print("🧠 System idle. Initiating Daydream sequence...")
    
    recent, historical = get_history_chunks()
    if not recent:
        print("Not enough history available yet.")
        return

    context_str = f"--- RECENT STRUGGLES ---\n{recent}\n\n"
    if historical:
        context_str += f"--- RANDOM HISTORICAL CONTEXT ---\n{historical}\n\n"

    # ==========================================
    # PASS 1: The Dreamer (Idea Generation)
    # ==========================================
    print("💭 Pass 1: Generating Epiphany...")
    dreamer_user = (
        "Review the provided historical interactions and logs. "
        "Identify an unresolved bug, an architectural inefficiency, or a missing connection. "
        "You are explicitly authorized to use your native `web_search` and `web_fetch` tools. "
        "If you identify an unresolved coding issue or architectural question, you MUST autonomously search the live internet and read documentation to fact-check and solve the problem before generating your final epiphany.\n\n"
        f"Here is the context:\n{context_str}\n\n"
        "What actionable epiphany can you derive from this? Use tools if necessary to investigate, then provide a detailed thought process followed by the concrete markdown payload."
    )
    
    cmd = [
        "npx", "--yes", "tsx", 
        "/mnt/TG_2TB/Projects/Apollo/engines/open-multi-agent-upstream/examples/apollo_cli.ts", 
        "--profile", "daydreamer", 
        dreamer_user
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=600, stdin=subprocess.DEVNULL)
        # Strip ANSI escape sequences from the CLI output
        epiphany_text = re.sub(r'\x1b\[[0-9;]*m', '', res.stdout)
    except Exception as e:
        print(f"Dreamer execution failed: {e}")
        return 
    
    if not epiphany_text:
        return
        
    print(f"\n=== ✨ RAW EPIPHANY ===\n{epiphany_text[:500]}...\n======================\n")

    # ==========================================
    # PASS 2: The Filter (Actionability Check)
    # ==========================================
    print("🛡️ Pass 2: Filtering for Actionability (Guided Decoding)...")
    filter_sys = (
        "You are the Sovereign Coordinator acting as a strict filter.\n"
        "Evaluate the provided epiphany. If it is a concrete, actionable skill, extract its title, tldr, and the raw markdown payload.\n"
        "If it is just philosophical rambling or vague ideas, set is_actionable to false."
    )
    filter_user = (
        f"Evaluate this epiphany:\n{epiphany_text}\n\n"
        "Respond in strict JSON format."
    )
    
    response_format = {
        "type": "json_schema", 
        "json_schema": {
            "name": "epiphany_filter", 
            "schema": {
                "type": "object", 
                "properties": {
                    "is_actionable": {"type": "boolean"}, 
                    "title": {"type": "string", "description": "A short 2-5 word title for the skill"},
                    "tldr": {"type": "string", "description": "A 1 sentence summary"},
                    "token_impact": {"type": "integer", "description": "Estimated token length of the payload"},
                    "raw_payload": {"type": "string", "description": "The exact markdown skill documentation to be saved"}
                },
                "required": ["is_actionable", "title", "tldr", "token_impact", "raw_payload"]
            }
        }
    }
    
    filter_result = call_llm([
        {"role": "system", "content": filter_sys},
        {"role": "user", "content": filter_user}
    ], temperature=0.1, response_format=response_format)
    
    if not filter_result:
        return
        
    try:
        verdict = json.loads(filter_result)
        is_actionable = verdict.get('is_actionable')
        print(f"Filter Verdict: Actionable={is_actionable}")
        
        if is_actionable:
            push_to_inbox(
                verdict.get("title", "Unknown Skill"),
                verdict.get("tldr", "No summary provided."),
                verdict.get("raw_payload", ""),
                verdict.get("token_impact", 0)
            )
        else:
            print("🗑️ Epiphany discarded as non-actionable noise.")
            
    except json.JSONDecodeError:
        print("Failed to parse Filter JSON output.")

def main():
    print("🌙 Daydream Daemon Started. Monitoring system state...")
    try:
        while True:
            if is_system_idle():
                trigger_daydream()
                print(f"💤 Daydream complete. Resting for {DAYDREAM_COOLDOWN} seconds.")
                time.sleep(DAYDREAM_COOLDOWN)
            else:
                time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        print("\nDaydream Daemon shutting down.")

if __name__ == "__main__":
    main()