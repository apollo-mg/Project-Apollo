import time
import math
from modules.vdb import get_vector_store

# --- Biological Decay Formula Constants ---
# Strength = importance * exp(-lambda_eff * days) * (1 + recall_count * 0.2)
DECAY_RATE_LAMBDA = 0.1 # Base decay rate (10% per day)
STRENGTH_THRESHOLD = 0.05 # Below this strength, the memory is deleted
DEFAULT_IMPORTANCE = 0.5

def calculate_strength(importance, days_old, recall_count):
    """Calculates the biological strength of a memory."""
    # Ebbinghaus Forgetting Curve component
    decay = math.exp(-DECAY_RATE_LAMBDA * days_old)
    # Neural reinforcement component
    reinforcement = 1 + (recall_count * 0.2)
    
    return importance * decay * reinforcement

def prune_memories():
    print("🧹 Initiating Biological Memory Pruning (Default Mode Network)...")
    
    vector_store = get_vector_store()
    collection = vector_store._collection
    
    try:
        # Fetch all memories
        data = collection.get()
        ids = data['ids']
        metadatas = data['metadatas']
        documents = data['documents']
        
        if not ids:
            print("📭 Hippocampus is empty. Nothing to prune.")
            return

        current_time = time.time()
        ids_to_delete = []
        
        print(f"🔍 Analyzing {len(ids)} memory synapses...")
        
        for i in range(len(ids)):
            mem_id = ids[i]
            meta = metadatas[i] or {}
            
            # Extract memory features
            importance = float(meta.get("importance", DEFAULT_IMPORTANCE))
            recall_count = int(meta.get("recall_count", 0))
            
            # Calculate age
            # If timestamp doesn't exist, we assume it's fresh (0 days old) for safety
            created_at = float(meta.get("timestamp", current_time))
            
            # 'days' is calculated from creation, though we could use last_accessed.
            # Using creation mimics structural decay, while last_accessed mimics short-term cache.
            # We'll use creation, but recall_count provides the reinforcement.
            age_seconds = current_time - created_at
            age_days = age_seconds / (24 * 3600)
            
            # If it's absurdly old or missing timestamp, let's cap it or just rely on decay
            if age_days < 0: age_days = 0
            
            # Calculate Neural Strength
            strength = calculate_strength(importance, age_days, recall_count)
            
            # Prune logic
            if strength < STRENGTH_THRESHOLD:
                # Protect certain types of permanent memories if needed
                if meta.get("type") == "core_belief":
                    continue
                    
                ids_to_delete.append(mem_id)
                
        if ids_to_delete:
            print(f"🗑️ Found {len(ids_to_delete)} decayed memories dropping below threshold ({STRENGTH_THRESHOLD}).")
            collection.delete(ids=ids_to_delete)
            print(f"✅ Biological Pruning Complete. Synapses severed.")
        else:
            print("🌿 All memory synapses remain above decay threshold. No pruning required.")
            
    except Exception as e:
        print(f"❌ Pruning failed: {e}")

if __name__ == "__main__":
    prune_memories()
