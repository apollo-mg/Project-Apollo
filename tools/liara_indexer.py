import os
import json
import time
import requests
from modules.vdb import query_vdb, get_vector_store, get_text_splitter
from langchain_core.documents import Document

# Configuration
LOGS_PATH = "/home/mark/.gemini/tmp/apollo/logs.json"
STATE_FILE = "/mnt/TG_2TB/Projects/Apollo/data/liara_state.json"
DB_COLLECTION = "apollo_memory"

def get_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f: return json.load(f)
    return {"last_processed_idx": 0}

def save_state(state):
    with open(STATE_FILE, 'w') as f: json.dump(state, f)

def process_logs(state):
    if not os.path.exists(LOGS_PATH): return state
    
    with open(LOGS_PATH, 'r') as f:
        try:
            logs = json.load(f)
        except: return state

    if not isinstance(logs, list): return state
    
    new_idx = state["last_processed_idx"]
    if new_idx >= len(logs): return state
    
    vdb = get_vector_store()
    splitter = get_text_splitter()
    
    print(f"[*] Liara: Processing {len(logs) - new_idx} new log entries...")
    
    for i in range(new_idx, len(logs)):
        entry = logs[i]
        text = f"User: {entry.get('message', '')}\nTimestamp: {entry.get('timestamp', '')}"
        
        # Index the raw turn for retrieval
        doc = Document(page_content=text, metadata={"type": "memory", "index": i, "timestamp": entry.get('timestamp', '')})
        vdb.add_documents([doc])
        new_idx = i + 1
        
    state["last_processed_idx"] = new_idx
    return state

if __name__ == "__main__":
    print("◈ [LIBRARIAN] Liara initialized. Monitoring logs for long-term memory...")
    state = get_state()
    while True:
        state = process_logs(state)
        save_state(state)
        time.sleep(60) # Sync every minute
