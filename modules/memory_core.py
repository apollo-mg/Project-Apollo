import os
import json
import time
import requests
import re
from datetime import datetime
from modules.vdb import get_vector_store, Document, get_text_splitter

# --- CONFIGURATION ---
MAX_CONTEXT_TOKENS = 32000
COMPACTION_THRESHOLD = int(MAX_CONTEXT_TOKENS * 0.8) # Flush at 80% capacity
OLLAMA_URL = "http://127.0.0.1:11434/v1/chat/completions"

class MemoryManager:
    def __init__(self):
        self.vector_store = get_vector_store()
        self.text_splitter = get_text_splitter()
        self.current_session_tokens = 0
        self.history = []

    def estimate_tokens(self, text):
        """Rough estimation of tokens (1 token ~= 4 chars)."""
        return len(text) // 4

    def add_message(self, role, content):
        """Adds a message to the active context and checks for compaction."""
        self.history.append({"role": role, "content": content})
        self.current_session_tokens += self.estimate_tokens(content)

        # --- CIRCUIT BREAKER / THROTTLE LOGIC ---
        # If the density of messages (high-velocity data) is too high, 
        # or if we are approaching the limit, trigger a compaction to prevent 
        # hardware-level memory errors (HIP kernel errors) and API quota exhaustion.
        if self.current_session_tokens >= COMPACTION_THRESHOLD:
            self.perform_compaction_flush()

    def retrieve_context(self, query, k=3):
        """RAG lookup for past memories relevant to the current query."""
        try:
            results = self.vector_store.similarity_search(query, k=k, filter={"type": "memory_flush"})
            if not results:
                return ""
            
            context_blocks = []
            for doc in results:
                context_blocks.append(f"- {doc.page_content.strip()}")
            
            if context_blocks:
                return "\n[RECALLED MEMORIES]\n" + "\n".join(context_blocks) + "\n"
            return ""
        except Exception as e:
            print(f"[VMM] Error retrieving context: {e}")
            return ""

    def perform_compaction_flush(self):
        """Triggers the OpenClaw-style 'Pre-Compaction Flush' and saves to Chroma DB & Scrapbook."""
        print("\n[VMM] Context threshold reached. Performing compaction flush...")
        
        summary_prompt = "Summarize the key decisions, architectural facts, and context from our conversation so far. Output only the factual summary."
        
        flush_payload = {
            "model": "surgeon-heretic:latest",
            "messages": self.history + [{"role": "user", "content": summary_prompt}],
            "temperature": 0.2,
            "max_tokens": 800
        }
        
        try:
            res = requests.post(OLLAMA_URL, json=flush_payload, timeout=120)
            if res.status_code == 200:
                summary = res.json()['choices'][0]['message']['content']
                summary = re.sub(r'<think>.*?</think>', '', summary, flags=re.DOTALL).strip()
                
                # 1. Ingest into Vector DB
                doc = Document(
                    page_content=summary, 
                    metadata={
                        "source": "vmm_compaction",
                        "type": "memory_flush",
                        "timestamp": datetime.now().isoformat()
                    }
                )
                
                chunks = self.text_splitter.split_documents([doc])
                if chunks:
                    self.vector_store.add_documents(documents=chunks)
                    print("[VMM] Memory compacted and successfully paged to Vector DB.")
                
                # 2. Save to human-readable 'scrapbook'
                scrapbook_path = "vault/memory_chronicle.md"
                os.makedirs(os.path.dirname(scrapbook_path), exist_ok=True)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(scrapbook_path, "a", encoding="utf-8") as f:
                    f.write(f"\n## Memory Flush: {timestamp}\n")
                    f.write(f"{summary}\n")
                    f.write("---\n")

                # 3. Reset history and prepend the summary
                self.history = [{"role": "assistant", "content": f"Previous context summary: {summary}"}]
                self.current_session_tokens = self.estimate_tokens(summary)
            else:
                print(f"[VMM] ERROR: Flush failed with status {res.status_code}")
        except Exception as e:
            print(f"[VMM] ERROR: Flush exception: {e}")

# Global instance
vmm = MemoryManager()
