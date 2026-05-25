import os
import chromadb
from sentence_transformers import SentenceTransformer
import uuid

VAULT_DIR = "vault"
DB_DIR = os.path.join(VAULT_DIR, "chroma_db")

def ingest_vault():
    print(f"--- INGESTING VAULT: {VAULT_DIR} ---")
    
    # 1. Setup DB
    client = chromadb.PersistentClient(path=DB_DIR)
    # Delete old collection to force refresh
    try: client.delete_collection("shop_vault")
    except: pass
    
    collection = client.get_or_create_collection(name="shop_vault")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # 2. Walk Files
    docs = []
    ids = []
    metadatas = []
    
    for root, _, files in os.walk(VAULT_DIR):
        for file in files:
            if file.endswith((".md", ".txt", ".cfg")):
                path = os.path.join(root, file)
                print(f"Processing: {file}")
                with open(path, 'r', errors='ignore') as f:
                    text = f.read()
                    # Simple chunking by paragraphs or 500 chars
                    chunks = [text[i:i+500] for i in range(0, len(text), 450)]
                    
                    for i, chunk in enumerate(chunks):
                        docs.append(chunk)
                        ids.append(f"{file}_{i}")
                        metadatas.append({"source": file})

    # 3. Add to Chroma
    if docs:
        print(f"Embedding {len(docs)} chunks...")
        embeddings = model.encode(docs).tolist()
        collection.add(
            documents=docs,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
        print("✅ Ingestion Complete.")
        
        # TEST QUERY
        print("\n--- TEST QUERY: 'EBB36 Pinout' ---")
        res = collection.query(
            query_embeddings=model.encode(["EBB36 Pinout"]).tolist(),
            n_results=1
        )
        print(f"Top Result: {res['documents'][0][0][:200]}...")
    else:
        print("⚠️ No documents found to ingest.")

if __name__ == "__main__":
    ingest_vault()
