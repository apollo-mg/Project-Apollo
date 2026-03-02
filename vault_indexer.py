import os
import fitz  # PyMuPDF
import chromadb
from sentence_transformers import SentenceTransformer
import json

VAULT_DIR = "/media/mark/48B42D2CB42D1DC6/gemini_infrastructure/vault"
DB_DIR = "/media/mark/48B42D2CB42D1DC6/gemini_infrastructure/vault/chroma_db"

def extract_text(file_path):
    if file_path.endswith(".pdf"):
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    elif file_path.endswith(".md") or file_path.endswith(".txt"):
        with open(file_path, "r") as f:
            return f.read()
    return None

def chunk_text(text, chunk_size=1000, overlap=100):
    chunks = []
    for i in range(0, len(text), chunk_size - overlap):
        chunks.append(text[i:i + chunk_size])
    return chunks

def index_vault():
    client = chromadb.PersistentClient(path=DB_DIR)
    collection = client.get_or_create_collection(name="shop_vault")
    model = SentenceTransformer('all-MiniLM-L6-v2')

    for filename in os.listdir(VAULT_DIR):
        file_path = os.path.join(VAULT_DIR, filename)
        if os.path.isdir(file_path) or filename.startswith("."):
            continue
            
        print(f"Indexing: {filename}...")
        text = extract_text(file_path)
        if not text: continue
        
        chunks = chunk_text(text)
        ids = [f"{filename}_{i}" for i in range(len(chunks))]
        embeddings = model.encode(chunks).tolist()
        metadatas = [{"source": filename} for _ in range(len(chunks))]
        
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=chunks
        )
    print("Indexing Complete.")

if __name__ == "__main__":
    index_vault()
