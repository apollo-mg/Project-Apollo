import json
import time
from modules.vdb import get_vector_store, get_text_splitter, Document

SUMMARY_FILE = "data/summary_48h.md"
JSONL_FILE = "v8_memory_dataset.jsonl"

def ingest_to_vdb():
    print("[*] Ingesting summary into Biological Memory (ChromaDB)...")
    try:
        with open(SUMMARY_FILE, "r") as f:
            content = f.read()
            
        vector_store = get_vector_store()
        text_splitter = get_text_splitter()
        
        # Add Biological Memory specific metadata for prune_memories.py
        doc = Document(page_content=content, metadata={
            "source": SUMMARY_FILE,
            "type": "architect_summary",
            "importance": 1.0, # High importance for architectural milestones
            "timestamp": time.time()
        })
        
        chunks = text_splitter.split_documents([doc])
        if chunks:
            vector_store.add_documents(documents=chunks)
            print(f"[+] Successfully indexed {len(chunks)} biological memory chunks.")
        else:
            print("[-] No chunks created.")
            
        # Also append to the LoRA fine-tuning dataset
        print(f"[*] Appending to Sleep Cycle Training Data ({JSONL_FILE})...")
        training_entry = {
            "conversation": {
                "messages": [
                    {"role": "user", "content": "Provide a comprehensive architectural summary of the last 48 hours of Sovereign Engine development, including the hardware topology, resolved technical debt, and immediate strategic roadmap."},
                    {"role": "assistant", "content": content}
                ]
            },
            "summary": "The Sovereign Architect's final 48-hour synthesis detailing the transition to the TurboQuant-enabled Gemma 4 26B model on RDNA 4, resolving the MUL_MAT_ID MoE bugs, and establishing the 'Zero-Abstraction' strategy."
        }
        
        with open(JSONL_FILE, "a") as f:
            f.write(json.dumps(training_entry) + "\n")
        print("[+] Successfully appended to v8_memory_dataset.jsonl for nightly Sleep Cycle.")

    except Exception as e:
        print(f"[!] Ingestion Error: {e}")

if __name__ == "__main__":
    ingest_to_vdb()
