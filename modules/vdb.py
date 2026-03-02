import os
import hashlib
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

# --- Configuration ---
HOT_STORAGE_DB_DIR = "vault/chroma_db"
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

def get_vector_store():
    """Initializes and returns the Chroma Vector Store."""
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={'device': 'cpu'}, 
        encode_kwargs={'normalize_embeddings': False}
    )
    # Ensure directory exists
    os.makedirs(HOT_STORAGE_DB_DIR, exist_ok=True)
    
    return Chroma(
        persist_directory=HOT_STORAGE_DB_DIR,
        embedding_function=embeddings,
        collection_name="shop_vault"
    )

def query_vdb(query: str, n_results: int = 5, filter_dict: dict = None):
    """Queries the Vector DB and returns relevant chunks. By default excludes email types to prevent context collapse."""
    try:
        vector_store = get_vector_store()
        
        # Default behavior: exclude noisy emails if no specific filter is provided
        # We achieve this by filtering out documents where "type" == "email"
        # However, Chroma's filtering is exact match. If we want everything EXCEPT emails,
        # we can use the $ne (not equal) operator in Chroma.
        search_filter = filter_dict
        if search_filter is None:
            search_filter = {"type": {"$ne": "email"}}
            
        results = vector_store.similarity_search(query, k=n_results, filter=search_filter)
        
        output = []
        for doc in results:
            source = doc.metadata.get("source", "Unknown")
            # Use escaped \n for proper line breaks in output
            output.append(f"--- Source: {source} ---\n{doc.page_content}\n")
        
        return "\n".join(output) if output else "No relevant documents found in the vault."
    except Exception as e:
        return f"VDB Query Error: {e}"

def get_text_splitter():
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        is_separator_regex=False
    )
