import os
import json
import glob
from datetime import datetime
import sys

# Ensure we can import from the Apollo root
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from modules.vdb import get_vector_store, get_text_splitter, Document

SEARCH_DIRS = [
    "/home/mark/.gemini/tmp/apollo/chats",
    "/home/mark/.gemini/history",
    "/mnt/TG_2TB/Projects/Apollo/chat_history"
]

def get_json_files():
    files = []
    for d in SEARCH_DIRS:
        for root, _, filenames in os.walk(d):
            for filename in filenames:
                if filename.startswith("session-") or filename.startswith("gemini-conversation"):
                    if filename.endswith(".json"):
                        files.append(os.path.join(root, filename))
    return list(set(files))

def extract_chat_text(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if isinstance(data, list):
            messages = data
        else:
            messages = data.get("messages", [])
            
        if not messages:
            return None
            
        output = []
        for msg in messages:
            role = msg.get("role", "unknown")
            text = ""
            
            if "content" in msg and isinstance(msg["content"], str):
                text = msg["content"]
            elif "parts" in msg:
                for part in msg["parts"]:
                    if "text" in part:
                        text += part["text"] + "\n"
                        
            if text.strip():
                # Truncate extremely long code dumps to save vector space
                lines = text.strip().split("\n")
                if len(lines) > 100:
                    text = "\n".join(lines[:30]) + "\n\n... [truncated long code block] ...\n\n" + "\n".join(lines[-30:])
                
                output.append(f"[{role.upper()}]: {text.strip()}")
                
        return "\n\n".join(output)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None

def ingest_chats():
    print("Gathering chat history files...")
    files = get_json_files()
    print(f"Found {len(files)} chat log files.")
    
    vector_store = get_vector_store()
    text_splitter = get_text_splitter()
    
    docs_to_add = []
    processed = 0
    
    for f in files:
        content = extract_chat_text(f)
        if content:
            mod_time = os.path.getmtime(f)
            date_str = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
            filename = os.path.basename(f)
            
            # Create a Document for the whole chat
            doc = Document(
                page_content=f"CHAT LOG FROM {date_str}\n\n{content}",
                metadata={
                    "source": f"chat_log_{filename}",
                    "type": "chat_history",
                    "date": date_str,
                    "timestamp": mod_time
                }
            )
            
            # Split it up if it's too long
            chunks = text_splitter.split_documents([doc])
            docs_to_add.extend(chunks)
            processed += 1
            
    if docs_to_add:
        print(f"Embedding {len(docs_to_add)} chunks from {processed} chat files...")
        batch_size = 5000
        for i in range(0, len(docs_to_add), batch_size):
            batch = docs_to_add[i:i + batch_size]
            print(f"Processing batch {i // batch_size + 1}/{(len(docs_to_add) + batch_size - 1) // batch_size}...")
            vector_store.add_documents(documents=batch)
        print("✅ Ingestion Complete.")
    else:
        print("⚠️ No valid chat documents found to ingest.")

if __name__ == "__main__":
    ingest_chats()