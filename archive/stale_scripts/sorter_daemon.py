import json
import os
import chromadb
from chromadb.utils import embedding_functions

INPUT_FILE = "actionable_epiphanies.jsonl"
OUTPUT_FILE = "deduplicated_epiphanies.jsonl"
CHROMA_DB_DIR = "./chroma_db_sorter"
COLLECTION_NAME = "epiphanies"
SIMILARITY_THRESHOLD = 0.15 # Using cosine distance; smaller means more similar (0 is identical)

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: Input file '{INPUT_FILE}' not found.")
        return

    # Initialize ChromaDB persistent client
    print(f"Initializing ChromaDB at {CHROMA_DB_DIR}...")
    client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    
    # Use the default sentence transformer embedding function
    # Note: Requires 'sentence-transformers' package to be installed
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    
    # We clear the collection for testing to ensure a clean run.
    # In production, you might not want to delete it if you append continuously.
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
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    epiphany = json.loads(line)
                    doc_id = str(epiphany['id'])
                    content = epiphany['content']
                    
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
                    
                    distances = results['distances'][0]
                    closest_id = results['ids'][0][0] if results['ids'] and results['ids'][0] else None
                    
                    # Distances < threshold are duplicates
                    if not distances or distances[0] >= SIMILARITY_THRESHOLD:
                        print(f"[{doc_id}] Novel idea found (Closest distance: {distances[0] if distances else 'N/A'}). Added as new cluster head.")
                        collection.add(
                            documents=[content],
                            metadatas=[epiphany],
                            ids=[doc_id]
                        )
                        unique_epiphanies.append(epiphany)
                    else:
                        print(f"[{doc_id}] Duplicate idea detected. Grouping with cluster head [{closest_id}] (Distance: {distances[0]:.4f}).")
                        
                except json.JSONDecodeError:
                    print(f"Warning: Invalid JSON line skipped: {line}")
                except KeyError as e:
                    print(f"Warning: Missing required key in JSON {line}: {e}")
                    
    except Exception as e:
        print(f"Error reading or processing input file: {e}")
        return

    # Write unique cluster heads to the output file
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            for epiphany in unique_epiphanies:
                f.write(json.dumps(epiphany) + '\n')
        print(f"\nSuccessfully wrote {len(unique_epiphanies)} unique epiphanies to '{OUTPUT_FILE}'.")
    except Exception as e:
        print(f"Error writing to output file: {e}")

if __name__ == "__main__":
    main()
