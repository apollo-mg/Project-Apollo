import json
import requests
import subprocess
import os

# Configuration
OLLAMA_URL = "http://10.0.0.5:11434/api/generate"
SMALL_MODEL = "deepscaler:1.5b"
OUTPUT_FILE = "training_memory.jsonl"

MOCK_CONVERSATIONS = [
    [
        {"role": "user", "content": "I'm seeing a performance bottleneck in our Raft implementation during log compaction."},
        {"role": "assistant", "content": "Are you using incremental snapshots? Log compaction can spike disk I/O if you try to serialize the whole state machine at once."},
        {"role": "user", "content": "No, it's a full state dump. I should switch to a copy-on-write snapshotting mechanism to avoid blocking the main thread."}
    ],
    [
        {"role": "user", "content": "The C++ service is leaking memory. Valgrind points to the BufferManager class."},
        {"role": "assistant", "content": "Check if your std::shared_ptr references are forming a cycle between the BufferManager and the CacheEntry objects."},
        {"role": "user", "content": "Found it. CacheEntry had a shared_ptr back to the manager. I'll change that to a std::weak_ptr to break the cycle."}
    ],
    [
        {"role": "user", "content": "We need to ensure eventual consistency across our Order and Inventory services using Kafka."},
        {"role": "assistant", "content": "I recommend the Transactional Outbox pattern. Write the event to a local DB table in the same transaction as the business logic, then a relay moves it to Kafka."},
        {"role": "user", "content": "That makes sense. It prevents 'ghost' orders where the DB transaction fails but the Kafka message was already sent."}
    ],
    [
        {"role": "user", "content": "This SQL join on 'users' and 'transactions' is taking 5 seconds. I have an index on user_id."},
        {"role": "assistant", "content": "Check EXPLAIN ANALYZE. It might be doing a sequential scan because of a type mismatch or because the statistics are stale."},
        {"role": "user", "content": "The statistics were old. After running ANALYZE, the planner switched to a nested loop join with the index, and now it's sub-millisecond."}
    ],
    [
        {"role": "user", "content": "I'm implementing a custom attention layer in PyTorch but the gradients aren't flowing correctly through the mask."},
        {"role": "assistant", "content": "Ensure you are using -1e9 for masked values before the softmax. If you use a hard zero, the gradient will be zeroed out."},
        {"role": "user", "content": "Right, I was using 0. Replacing it with a very large negative value before softmax fixed the backpropagation."}
    ]
]

def query_ollama(prompt):
    payload = {
        "model": SMALL_MODEL,
        "prompt": f"Summarize this conversation into a single factual sentence: {prompt}",
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception as e:
        return f"Error querying Ollama: {e}"

def refine_with_janitor(summary, conversation):
    # Construct a prompt for flash_janitor to fix the summary
    full_convo_text = "\n".join([f"{m['role']}: {m['content']}" for m in conversation])
    prompt = f"@flash_janitor Original Conversation:\n{full_convo_text}\n\nDraft Summary: {summary}\n\nRefine this draft summary into a PERFECT, single-sentence factual statement that captures the core technical resolution without fluff. Output ONLY the refined sentence."
    
    try:
        result = subprocess.run(
            ["gemini", "-y", "-p", prompt],
            capture_output=True,
            text=True,
            check=True
        )
        raw_output = result.stdout.strip()
        lines = [line for line in raw_output.split("\n") if line.strip()]
        if lines:
            return lines[-1]
        return raw_output
    except subprocess.CalledProcessError as e:
        return f"Error calling flash_janitor: {e.stderr}"

def main():
    print(f"Starting audit with {SMALL_MODEL} and flash_janitor...")
    
    with open(OUTPUT_FILE, "a") as f:
        for convo in MOCK_CONVERSATIONS:
            convo_text = json.dumps(convo)
            print(f"\nProcessing conversation...")
            
            # Step 1: Get initial summary from small model
            raw_summary = query_ollama(convo_text)
            print(f"DeepScaler Summary: {raw_summary}")
            
            # Step 2: Refine with flash_janitor
            refined_summary = refine_with_janitor(raw_summary, convo)
            print(f"Janitor Refinement: {refined_summary}")
            
            # Step 3: Save to JSONL
            entry = {
                "conversation": convo,
                "small_model_output": raw_summary,
                "refined_summary": refined_summary
            }
            f.write(json.dumps(entry) + "\n")
            print(f"Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
