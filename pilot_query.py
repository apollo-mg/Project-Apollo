import os
import argparse
import logging
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# --- Configuration ---
VECTOR_DB_DIR = "./vault/chroma_db"
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("PilotQuery")

def query_pilot_vault(query: str, k: int = 3):
    """
    Queries the Pilot Vault for relevant documents.
    """
    logger.info(f"Querying Pilot Vault for: '{query}'")

    if not os.path.exists(VECTOR_DB_DIR):
        logger.error(f"Vector DB not found at {VECTOR_DB_DIR}. Please run pilot_ingest.py first.")
        return

    # Initialize Embeddings
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': False}
    )

    # Initialize Vector Store
    vector_store = Chroma(
        persist_directory=VECTOR_DB_DIR,
        embedding_function=embeddings,
        collection_name="shop_vault"
    )

    # Perform Query
    results = vector_store.similarity_search_with_score(query, k=k)

    if not results:
        logger.warning("No results found.")
        return

    print("\n--- Pilot Vault Results ---")
    for i, (doc, score) in enumerate(results):
        print(f"\nResult {i+1} (Score: {score:.4f}):")
        print(f"Source: {doc.metadata.get('filename', 'Unknown')}")
        print(f"Content: {doc.page_content[:500]}...") # Show first 500 chars
        print("-" * 40)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query the Pilot Vault.")
    parser.add_argument("query", type=str, help="The query string.")
    parser.add_argument("--k", type=int, default=3, help="Number of results to return.")
    args = parser.parse_args()

    query_pilot_vault(args.query, args.k)
