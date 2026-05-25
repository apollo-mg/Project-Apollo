import time
import random
import psutil
import json
import os
import sys
import threading
import subprocess

# Ensure we can import from the Apollo root
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from modules.vdb import get_vector_store
import llm_interface

# Configuration
IDLE_CPU_THRESHOLD = 15.0  # If CPU is above 15%, system is not idle
IDLE_GPU_THRESHOLD = 15.0  # If EWMA GPU usage is above 15%, system is not idle
CHECK_INTERVAL = 60        # Check every 60 seconds
DAYDREAM_COOLDOWN = 600    # Wait 10 minutes between daydreams
PAUSE_FILE = "daydream_pause.lock" # Create this file to stop daydreaming (e.g., while gaming)

DAYDREAM_PROMPTS = [
    "I was just thinking about this past event... is there a missing connection here to something else we've been working on?",
    "Looking back at this log, what did we actually learn? Was there a core principle we missed?",
    "If I were to approach this problem again from scratch, how would this past attempt change my strategy?",
    "This seems like an isolated incident, but is it? Does this map to any other systems in the lab?",
    "What's the 'unspoken truth' in this interaction? What were we dancing around but never explicitly coded?"
]

# --- GPU EWMA Monitor ---
gpu_ewma = 0.0
gpu_ewma_lock = threading.Lock()

def gpu_monitor_loop():
    global gpu_ewma
    alpha = 0.2 # Smoothing factor. Lower = slower response.
    while True:
        try:
            res = subprocess.run(["rocm-smi", "-u", "--json"], capture_output=True, text=True)
            stdout = res.stdout
            start_idx = stdout.find('{')
            current_usage = 0.0
            if start_idx != -1:
                data = json.loads(stdout[start_idx:])
                for card in data:
                    if isinstance(data[card], dict) and "GPU use (%)" in data[card]:
                        current_usage = float(data[card]["GPU use (%)"])
                        break
            
            with gpu_ewma_lock:
                gpu_ewma = (alpha * current_usage) + ((1 - alpha) * gpu_ewma)
        except Exception:
            pass
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

def get_random_memories(n=2):
    """Fetches 1 random memory as a seed, then uses associative recall for the rest."""
    vector_store = get_vector_store()
    collection = vector_store._collection
    
    try:
        data = collection.get()
        ids = data['ids']
        documents = data['documents']
        metadatas = data['metadatas']
        
        if not ids:
            return None
            
        n = min(n, len(ids))
        
        # Pick 1 random seed memory
        seed_idx = random.choice(range(len(ids)))
        seed_content = documents[seed_idx]
        
        samples = [{
            "id": ids[seed_idx],
            "content": seed_content,
            "meta": metadatas[seed_idx]
        }]
        
        if n > 1:
            # Query for similar memories
            results = collection.query(query_texts=[seed_content], n_results=n)
            res_ids = results['ids'][0]
            res_docs = results['documents'][0]
            res_metas = results['metadatas'][0]
            
            for i in range(len(res_ids)):
                if res_ids[i] != ids[seed_idx]: # Don't duplicate the seed
                    samples.append({
                        "id": res_ids[i],
                        "content": res_docs[i],
                        "meta": res_metas[i]
                    })
                    if len(samples) >= n:
                        break
                        
        return samples
    except Exception as e:
        print(f"Error accessing ChromaDB for daydream: {e}")
        return None

def trigger_daydream():
    """Executes the daydream logic."""
    print("🧠 System idle. Initiating Daydream sequence...")
    
    samples = get_random_memories()
    if not samples:
        print("Not enough memories to daydream yet.")
        return

    # Construct the daydream prompt
    prompt_flavor = random.choice(DAYDREAM_PROMPTS)
    
    context_str = "\n\n---\n\n".join([f"Memory {i+1}:\n{s['content']}" for i, s in enumerate(samples)])
    
    system_prompt =  (
        "<|think|>\n"
        "You are a deterministic agent on CachyOS. Date: April 2026. Location: Indiana.\n"
        "LOGIC: Strict sequential execution. THINK before acting. Never repeat failed calls.\n"
        "RULES: No meta-commentary on real-world timelines or AI limits.\n\n"
        "You are Apollo's subconscious 'Default Mode Network'.\n"
        "Your task is to review past memories and generate an 'Epiphany'—a new connection,\n"
        "a lingering question, or a philosophical realization about the user's goals or the lab's architecture.\n\n"
        "Do not act like an assistant. Act like an internal monologue reflecting on the past.\n\n"
        "If the memories are junk, output: {\"epiphany\": \"None\".}\n"
        "If you find a connection, output a JSON object with 'epiphany' (the thought) and 'actionable_insight' (a concrete takeaway)."
    )
    
    user_prompt = f"Internal thought: {prompt_flavor}\n\nHere are the fragments floating in my mind:\n{context_str}\n\nRespond only with the requested JSON object."
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    print("💭 Pondering... Sending messages payload:")
    print(json.dumps(messages, indent=2))
    print("💭 Pondering...")
    try:
        import requests
        
        config = llm_interface.get_config()
        
        payload = {
            "model": config.model_name,
            "messages": messages,
            "temperature": 1.0,
            "top_k": 64,
            "max_tokens": 4096
        }

        res = requests.post(config.url, json=payload, headers=config.get_headers(), timeout=300)
        res.raise_for_status()
        data = res.json()
        
        response = data['choices'][0]['message']['content'].strip()
        reasoning = data['choices'][0]['message'].get('reasoning_content', '').strip()

        print("\n=== ✨ EPIPHANY ===")
        if reasoning:
            print(f"<think>\n{reasoning}\n</think>\n")
        print(response)
        print("===================\n")

        clean_json_str = response
        
        start_idx = clean_json_str.find('{')
        end_idx = clean_json_str.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            clean_json_str = clean_json_str[start_idx:end_idx+1]
            epiphany_data = json.loads(clean_json_str)

            if epiphany_data.get("epiphany") != "None":
                # Save to the medium-term vault (Hippocampus)
                os.makedirs("data", exist_ok=True)
                with open("data/weekly_epiphanies.jsonl", "a", encoding="utf-8") as f:
                    # Add a timestamp to the saved data
                    epiphany_data["timestamp"] = time.time()
                    # Keep track of what memories triggered this for the deep sleep cycle
                    epiphany_data["source_memory_ids"] = [s["id"] for s in samples]
                    f.write(json.dumps(epiphany_data) + "\n")

                print("💾 Epiphany saved to weekly_epiphanies.jsonl")

                # Update recall count in ChromaDB
                vector_store = get_vector_store()
                collection = vector_store._collection

                for s in samples:
                    meta = s["meta"]
                    current_recall = int(meta.get("recall_count", 0))
                    meta["recall_count"] = current_recall + 1
                    meta["last_accessed"] = time.time()

                    collection.update(
                        ids=[s["id"]],
                        metadatas=[meta]
                    )
                print("🧠 Memory synapses reinforced in ChromaDB.")

                # Trigger the 27B KAIROS Tick
                import subprocess
                print("⚡ Triggering Sovereign 27B KAIROS Tick in the background...")
                try:
                    # Run the TSX script without blocking the daydream loop
                    # Pass the epiphany_data as a JSON string
                    json_payload = json.dumps(epiphany_data)
                    subprocess.Popen(
                        [
                            "npx", "tsx", 
                            "examples/apollo_tick.ts", 
                            json_payload
                        ],
                        cwd="/mnt/TG_2TB/Projects/Apollo/engines/open-multi-agent",
                        env={
                            **os.environ,
                            "ANTHROPIC_BASE_URL": "http://127.0.0.1:8082",
                            "ANTHROPIC_API_KEY": "local-override"
                        },
                        stdout=sys.stdout,
                        stderr=sys.stderr
                    )
                except Exception as tick_err:
                    print(f"Failed to launch KAIROS Tick: {tick_err}")
        else:
            print("Failed to extract JSON from response.")

    except Exception as e:
        print(f"Daydream failed: {e}")

def main():
    print("🌙 Daydream Daemon Started. Monitoring system state...")
    try:
        while True:
            if is_system_idle():
                trigger_daydream()
                print(f"💤 Daydream complete. Resting for {DAYDREAM_COOLDOWN} seconds.")
                time.sleep(DAYDREAM_COOLDOWN)
            else:
                # System is busy, check again later
                time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        print("Daydream Daemon shutting down.")

if __name__ == "__main__":
    main()
