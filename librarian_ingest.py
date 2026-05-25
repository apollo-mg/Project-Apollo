import os
import hashlib
import logging
import sqlite3
import trafilatura
import uuid
from typing import List, Optional
from modules.vdb import get_vector_store, get_text_splitter, Document

# --- Configuration ---
COLD_VAULT_DIR = "vault/cold"
SQLITE_DB_PATH = "vault/bm25_index.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("librarian_ingest.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Librarian")

try:
    from langchain_community.document_loaders import PyPDFLoader, TextLoader
except ImportError as e:
    logger.error(f"Missing dependencies: {e}")
    print("Please install required packages: pip install langchain-community pypdf")
    exit(1)

def get_sqlite_conn():
    os.makedirs(os.path.dirname(SQLITE_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            chunk_id UNINDEXED, 
            source UNINDEXED, 
            content
        );
    """)
    conn.commit()
    return conn

def compute_sha256(file_path: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def ingest_chunks_to_dual_index(chunks, source_id, type_val):
    if not chunks:
        return 0

    vector_store = get_vector_store()
    sqlite_conn = get_sqlite_conn()
    
    # Generate deterministic UUIDs for each chunk to sync across Vector and FTS5
    ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source_id}_{i}")) for i in range(len(chunks))]
    
    # Ingest to ChromaDB (Vector)
    vector_store.add_documents(documents=chunks, ids=ids)
    
    # Ingest to SQLite (BM25)
    sqlite_data = [(chunk_id, chunk.metadata.get("source", "Unknown"), chunk.page_content) 
                   for chunk_id, chunk in zip(ids, chunks)]
    
    sqlite_conn.executemany("""
        INSERT INTO chunks_fts (chunk_id, source, content) VALUES (?, ?, ?)
    """, sqlite_data)
    sqlite_conn.commit()
    
    return len(chunks)

def ingest_text(file_path: str):
    vector_store = get_vector_store()
    text_splitter = get_text_splitter()
    
    filename = os.path.basename(file_path)
    file_hash = compute_sha256(file_path)
    
    try:
        existing_docs = vector_store.get(where={"file_hash": file_hash}, limit=1)
        if existing_docs['ids']:
            return f"Skipped: {filename} already indexed."
    except: pass

    logger.info(f"Processing Text/Markdown: {filename}")
    try:
        loader = TextLoader(file_path, encoding='utf-8')
        raw_docs = loader.load()
    except Exception as e:
        return f"Error loading {filename}: {e}"
        
    chunks = text_splitter.split_documents(raw_docs)

    for chunk in chunks:
        chunk.metadata.update({
            "source": file_path,
            "filename": filename,
            "file_hash": file_hash,
            "type": "text"
        })

    num_indexed = ingest_chunks_to_dual_index(chunks, file_hash, "text")
    return f"Indexed {num_indexed} chunks from {filename}" if num_indexed else f"No text extracted from {filename}"

def ingest_pdf(file_path: str):
    vector_store = get_vector_store()
    text_splitter = get_text_splitter()
    
    filename = os.path.basename(file_path)
    file_hash = compute_sha256(file_path)
    
    try:
        existing_docs = vector_store.get(where={"file_hash": file_hash}, limit=1)
        if existing_docs['ids']:
            return f"Skipped: {filename} already indexed."
    except: pass

    logger.info(f"Processing PDF: {filename}")
    loader = PyPDFLoader(file_path)
    raw_docs = loader.load()
    chunks = text_splitter.split_documents(raw_docs)

    for chunk in chunks:
        chunk.metadata.update({
            "source": file_path,
            "filename": filename,
            "file_hash": file_hash,
            "type": "pdf"
        })

    num_indexed = ingest_chunks_to_dual_index(chunks, file_hash, "pdf")
    return f"Indexed {num_indexed} chunks from {filename}" if num_indexed else f"No text extracted from {filename}"

def ingest_url(url: str):
    vector_store = get_vector_store()
    text_splitter = get_text_splitter()

    logger.info(f"Ingesting URL: {url}")
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return f"Error: Failed to fetch URL {url}"
    
    content = trafilatura.extract(downloaded)
    if not content:
        return f"Error: Failed to extract content from {url}"

    url_id = hashlib.sha256(url.encode()).hexdigest()
    
    try:
        existing_docs = vector_store.get(where={"url_id": url_id}, limit=1)
        if existing_docs['ids']:
            return f"Skipped: {url} already indexed."
    except: pass

    doc = Document(page_content=content, metadata={
        "source": url,
        "url_id": url_id,
        "type": "url"
    })
    
    chunks = text_splitter.split_documents([doc])
    num_indexed = ingest_chunks_to_dual_index(chunks, url_id, "url")
    return f"Indexed {num_indexed} chunks from {url}" if num_indexed else f"No chunks created from {url}"

def ingest_makers_stack():
    if not os.path.exists(COLD_VAULT_DIR):
        os.makedirs(COLD_VAULT_DIR, exist_ok=True)
        logger.info(f"Created {COLD_VAULT_DIR}")
        return

    for root, dirs, files in os.walk(COLD_VAULT_DIR):
        for filename in files:
            filepath = os.path.join(root, filename)
            if filename.lower().endswith(".pdf"):
                print(ingest_pdf(filepath))
            elif filename.lower().endswith((".md", ".txt")):
                print(ingest_text(filepath))

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg.startswith("http"):
                print(ingest_url(arg))
            elif os.path.isfile(arg):
                if arg.endswith(".pdf"):
                    print(ingest_pdf(arg))
                else:
                    print(ingest_text(arg))
            elif os.path.isdir(arg):
                for root, _, files in os.walk(arg):
                    for file in files:
                        path = os.path.join(root, file)
                        if file.lower().endswith(".pdf"):
                            print(ingest_pdf(path))
                        elif file.lower().endswith((".md", ".txt")):
                            print(ingest_text(path))
            else:
                print(f"File not found: {arg}")
    else:
        ingest_makers_stack()
