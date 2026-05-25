import os
import hashlib
import logging
import shutil
from typing import List, Optional

# --- Configuration ---
# Source Directory for Pilot (Micro-Pilot)
# Place your Ender 6 / Widowmaker PDFs here
SOURCE_DIR = "./vault"

# Target Vector DB (Hot Storage)
VECTOR_DB_DIR = "./vault/chroma_db"

# Embedding Model (Local, CPU/GPU optimized)
EMBEDDING_MODEL_NAME = "nomic-ai/nomic-embed-text-v1.5"

# Chunking Strategy for Technical Docs
CHUNK_SIZE = 2000 # Increased chunk size for Nomic (8192 context)
CHUNK_OVERLAP = 200

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("PilotLibrarian")

# --- Dependency Check ---
try:
    from langchain_community.document_loaders import PyPDFLoader, TextLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_chroma import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_core.documents import Document
except ImportError as e:
    logger.error(f"Missing dependencies: {e}")
    print("Please install required packages:")
    print("pip install langchain-community langchain-chroma langchain-huggingface pypdf sentence-transformers")
    exit(1)

def compute_sha256(file_path: str) -> str:
    """Computes the SHA-256 hash of a file for WORM integrity verification."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read in 64kb chunks to be memory efficient
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def ingest_pilot_pdfs():
    """
    Ingests PDFs from the Source Directory into the Vector DB.
    Enforces WORM integrity via SHA-256 hashing.
    """
    # Ensure source directory exists
    if not os.path.exists(SOURCE_DIR):
        os.makedirs(SOURCE_DIR, exist_ok=True)
        logger.warning(f"Created source directory at {SOURCE_DIR}. Please add documents there and run again.")
        return

    logger.info(f"Starting pilot ingestion from: {SOURCE_DIR}")
    logger.info(f"Target Vector DB: {VECTOR_DB_DIR}")

    # Initialize Embeddings (Runs locally on GPU/CPU)
    logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}...")
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={'device': 'cpu', 'trust_remote_code': True}, 
        encode_kwargs={'normalize_embeddings': True}
    )

    # Initialize Chroma Vector Store (Persistent)
    vector_store = Chroma(
        persist_directory=VECTOR_DB_DIR,
        embedding_function=embeddings,
        collection_name="shop_vault_v2"
    )

    # Initialize Text Splitter
    # Optimized for technical manuals: keeps paragraphs together, respects headers
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        is_separator_regex=False
    )

    processed_count = 0
    skipped_count = 0

    # Walk through the Source Directory
    for root, dirs, files in os.walk(SOURCE_DIR):
        # Skip internal directories like chroma_db
        if "chroma_db" in root: continue
        
        for filename in files:
            is_pdf = filename.lower().endswith(".pdf")
            is_md = filename.lower().endswith(".md")
            
            if not (is_pdf or is_md):
                continue

            file_path = os.path.join(root, filename)
            
            try:
                # 1. Cryptographic Hashing (The "Librarian" Check)
                file_hash = compute_sha256(file_path)
                
                # Check if this specific file version (hash) is already indexed
                existing_docs = vector_store.get(where={"file_hash": file_hash}, limit=1)
                if existing_docs['ids']:
                    logger.info(f"Skipping (Already Indexed): {filename} [Hash: {file_hash[:8]}...]")
                    skipped_count += 1
                    continue

                logger.info(f"Processing: {filename} [Hash: {file_hash[:8]}...]")

                # 2. Load Document
                raw_docs = []
                if is_pdf:
                    loader = PyPDFLoader(file_path)
                    raw_docs = loader.load()
                elif is_md:
                    loader = TextLoader(file_path, encoding='utf-8')
                    raw_docs = loader.load()

                # 3. Chunking
                chunks = text_splitter.split_documents(raw_docs)

                # 4. Inject Metadata (Integrity & Traceability)
                for chunk in chunks:
                    chunk.metadata["source"] = file_path
                    chunk.metadata["filename"] = filename
                    chunk.metadata["file_hash"] = file_hash  # CRITICAL: The Integrity Key
                    chunk.metadata["tier"] = "pilot_vault"
                    chunk.metadata["category"] = "knowledge_base" if is_md else "technical_manual"

                # 5. Embed & Store
                if chunks:
                    # We assume the embedding model handles the batching, or Chroma does.
                    vector_store.add_documents(documents=chunks)
                    processed_count += 1
                    logger.info(f"Indexed {len(chunks)} chunks from {filename}")
                else:
                    logger.warning(f"No text extracted from {filename}")

            except Exception as e:
                logger.error(f"Failed to ingest {filename}: {e}")

    logger.info(f"Ingestion Complete. Processed: {processed_count}, Skipped: {skipped_count}")

if __name__ == "__main__":
    ingest_pilot_pdfs()
