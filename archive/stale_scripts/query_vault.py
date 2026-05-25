import sys
import json
import os

# Add Apollo root to path
sys.path.append('/mnt/TG_2TB/Projects/Apollo')
from modules.vdb import get_vector_store

def query(q, k):
    try:
        vector_store = get_vector_store()
        results = vector_store.similarity_search(q, k=k)
        
        memories = []
        for i, res in enumerate(results):
            memories.append({
                "content": res.page_content,
                "metadata": res.metadata
            })
            
        print(json.dumps({"status": "success", "memories": memories}))
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"status": "error", "message": "Missing arguments"}))
        sys.exit(1)
    
    q = sys.argv[1]
    try:
        k = int(sys.argv[2])
    except:
        k = 3
        
    query(q, k)
