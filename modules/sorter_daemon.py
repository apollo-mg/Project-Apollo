import json
import os
import chromadb
from chromadb.utils import embedding_functions

# Configuration
INPUT_FILE = "actionable_epiphanies.jsonl"
OUTPUT_FILE = "deduplicated_epiphanies.jsonl"
CHROMA_DB_DIR = "./chroma_db_sorter"
COLLECTION_NAME = "epiphanies"

# Threshold for duplicates. 
# Chroma's 'cosine' space returns 1 - cosine_similarity. 
# A distance < 0.15 means similarity > 0.85 (highly similar ideas).
SIMILARITY_THRESHOLD = 0.55

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: Input file '{INPUT_FILE}' not found.")
        # Create a dummy file for testing if it doesn't exist
        dummy_data = [
            {"id": "doc_1", "timestamp": "2023-10-25T10:00:00Z", "content": "The agent should prioritize tool use over text generation when complex data is requested."},
            {"id": "doc_2", "timestamp": "2023-10-25T10:01:00Z", "content": "It is crucial for the system to favor API calls instead of generating plain text for complex data queries."}, # Duplicate of doc_1
            {"id": "doc_3", "timestamp": "2023-10-25T10:02:00Z", "content": "Memory decay is an effective strategy for managing large context windows."},
            {"id": "doc_4", "timestamp": "2023-10-25T10:03:00Z", "content": "Large context limits can be mitigated by gradually forgetting older information, a process akin to memory decay."}, # Duplicate of doc_3
            {"id": "doc_5", "timestamp": "2023-10-25T10:04:00Z", "content": "UI elements should be decoupled from the backend for hot-reloading."} # Novel
        ]
        with open(INPUT_FILE, 'w', encoding='utf-8') as f:
            for item in dummy_data:
                f.write(json.dumps(item) + '\n')
        print(f"Created dummy test file: '{INPUT_FILE}'\n")

    # Initialize ChromaDB persistent client
    print(f"Initializing ChromaDB at '{CHROMA_DB_DIR}'...")
    client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    
    # Use the default sentence transformer embedding function
    try:
        sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    except Exception as e:
        print(f"Error loading embedding function: {e}\nPlease ensure you ran 'pip install sentence-transformers'.")
        return

    # Clear previous collection for a clean deduplication run
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass # Collection might not exist yet
    
    # Create the collection, specifying cosine distance metric
    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=sentence_transformer_ef,
        metadata={"hnsw:space": "cosine"}
    )
    
    unique_epiphanies = []
    
    print(f"Processing '{INPUT_FILE}'...")
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            for line_idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    epiphany = json.loads(line)
                    if 'epiphany' not in epiphany:
                         print(f"Warning: Missing required 'epiphany' key at line {line_idx + 1}. Skipping.")
                         continue
                         
                    doc_id = str(epiphany.get('timestamp', f"line_{line_idx}"))
                    content = epiphany['epiphany']
                    
                    # If collection is empty, the first one is inherently a cluster head
                    if collection.count() == 0:
                        print(f"[{doc_id}] Added as first cluster head.")
                        collection.add(
                            documents=[content],
                            metadatas=[epiphany],
                            ids=[doc_id]
                        )
                        unique_epiphanies.append(epiphany)
                        continue
                        
                    # Query ChromaDB for the single most similar document
                    results = collection.query(
                        query_texts=[content],
                        n_results=1
                    )
                    
                    distances = results['distances'][0] if results['distances'] else []
                    closest_id = results['ids'][0][0] if results['ids'] and results['ids'][0] else None
                    
                    # Clustering Logic: Distances >= threshold are considered novel
                    if not distances or distances[0] >= SIMILARITY_THRESHOLD:
                        dist_str = f"{distances[0]:.4f}" if distances else "N/A"
                        print(f"[{doc_id}] Novel idea found (Closest distance: {dist_str}). Added as new cluster head.")
                        collection.add(
                            documents=[content],
                            metadatas=[epiphany],
                            ids=[doc_id]
                        )
                        unique_epiphanies.append(epiphany)
                    else:
                        print(f"[{doc_id}] Duplicate idea detected. Grouping with cluster head [{closest_id}] (Distance: {distances[0]:.4f}).")
                        
                except json.JSONDecodeError:
                    print(f"Warning: Invalid JSON at line {line_idx + 1} skipped: {line}")
                    
    except Exception as e:
        print(f"Error reading or processing input file: {e}")
        return

    # Output phase: Write unique cluster heads to the output file
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            for epiphany in unique_epiphanies:
                f.write(json.dumps(epiphany) + '\n')
        print(f"\nSuccessfully wrote {len(unique_epiphanies)} unique epiphanies to '{OUTPUT_FILE}'.")
    except Exception as e:
        print(f"Error writing to output file: {e}")

if __name__ == "__main__":
    main()
