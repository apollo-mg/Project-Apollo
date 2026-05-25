import os
import hashlib
import logging
import shutil
import trafilatura
from typing import List, Optional
from modules.vdb import get_vector_store, get_text_splitter, Document

# --- Configuration ---
# Tier 2: Cold Vault (Source PDFs)
COLD_VAULT_DIR = "vault/cold"

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("librarian_ingest.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Librarian")

# --- Dependency Check ---
try:
    from langchain_community.document_loaders import PyPDFLoader
except ImportError as e:
    logger.error(f"Missing dependencies: {e}")
    print("Please install required packages: pip install langchain-community pypdf")
    exit(1)

def compute_sha256(file_path: str) -> str:
    """Computes the SHA-256 hash of a file for WORM integrity verification."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def ingest_pdf(file_path: str):
    """Ingests a single PDF into the Vector DB."""
    vector_store = get_vector_store()
    text_splitter = get_text_splitter()
    
    filename = os.path.basename(file_path)
    file_hash = compute_sha256(file_path)
    
    # Try to check if hash exists
    try:
        existing_docs = vector_store.get(where={"file_hash": file_hash}, limit=1)
        if existing_docs['ids']:
            return f"Skipped: {filename} already indexed."
    except: pass # Chroma get might fail if collection is empty or metadata filter is not indexable yet

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

    if chunks:
        vector_store.add_documents(documents=chunks)
        return f"Indexed {len(chunks)} chunks from {filename}"
    return f"No text extracted from {filename}"

def ingest_url(url: str):
    """Downloads and extracts content from a URL, then ingests into the Vector DB."""
    vector_store = get_vector_store()
    text_splitter = get_text_splitter()

    logger.info(f"Ingesting URL: {url}")
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return f"Error: Failed to fetch URL {url}"
    
    content = trafilatura.extract(downloaded)
    if not content:
        return f"Error: Failed to extract content from {url}"

    # Use URL as hash/identifier
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
    if chunks:
        vector_store.add_documents(documents=chunks)
        return f"Indexed {len(chunks)} chunks from {url}"
    return f"No chunks created from {url}"

def ingest_makers_stack():
    """Batch ingestion from the Cold Vault."""
    if not os.path.exists(COLD_VAULT_DIR):
        os.makedirs(COLD_VAULT_DIR, exist_ok=True)
        logger.info(f"Created {COLD_VAULT_DIR}")
        return

    for root, dirs, files in os.walk(COLD_VAULT_DIR):
        for filename in files:
            if filename.lower().endswith(".pdf"):
                print(ingest_pdf(os.path.join(root, filename)))

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg.startswith("http"):
            print(ingest_url(arg))
        elif os.path.isfile(arg) and arg.endswith(".pdf"):
            print(ingest_pdf(arg))
    else:
        ingest_makers_stack()

def ingest_makers_stack():
    """Batch ingestion from the Cold Vault."""
    if not os.path.exists(COLD_VAULT_DIR):
        os.makedirs(COLD_VAULT_DIR, exist_ok=True)
        logger.info(f"Created {COLD_VAULT_DIR}")
        return

    for root, dirs, files in os.walk(COLD_VAULT_DIR):
        for filename in files:
            if filename.lower().endswith(".pdf"):
                print(ingest_pdf(os.path.join(root, filename)))

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg.startswith("http"):
            print(ingest_url(arg))
        elif os.path.isfile(arg) and arg.endswith(".pdf"):
            print(ingest_pdf(arg))
    else:
        ingest_makers_stack()
