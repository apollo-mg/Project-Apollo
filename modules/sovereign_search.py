import os
import sqlite3
import logging
from modules.vdb import get_vector_store

logger = logging.getLogger("SovereignSearch")

SQLITE_DB_PATH = "vault/bm25_index.db"
RRF_K = 60

def get_sqlite_conn():
    if not os.path.exists(SQLITE_DB_PATH):
        return None
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def search_bm25(query: str, n_results: int = 10):
    """Executes a BM25 exact keyword search using SQLite FTS5."""
    conn = get_sqlite_conn()
    if not conn:
        return []

    try:
        # We use ORDER BY bm25(chunks_fts) to get the best matches
        cursor = conn.execute("""
            SELECT chunk_id, source, content, bm25(chunks_fts) as bm25_score
            FROM chunks_fts
            WHERE chunks_fts MATCH ?
            ORDER BY bm25_score
            LIMIT ?
        """, (query, n_results))
        
        results = []
        for row in cursor:
            results.append({
                "chunk_id": row["chunk_id"],
                "source": row["source"],
                "content": row["content"],
                "score": row["bm25_score"] # FTS5 bm25 returns lower score for better matches (negative values)
            })
        return results
    except Exception as e:
        logger.error(f"BM25 Search Error: {e}")
        return []
    finally:
        conn.close()

def search_vector(query: str, n_results: int = 10):
    """Executes a semantic vector search using ChromaDB."""
    try:
        vector_store = get_vector_store()
        
        # We need the IDs. We can query the underlying collection directly.
        results = vector_store._collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        if not results or not results["ids"] or not results["ids"][0]:
            return []
            
        vector_results = []
        for i in range(len(results["ids"][0])):
            vector_results.append({
                "chunk_id": results["ids"][0][i],
                "source": results["metadatas"][0][i].get("source", "Unknown"),
                "content": results["documents"][0][i],
                "score": results["distances"][0][i] # Lower distance is better
            })
        return vector_results
    except Exception as e:
        logger.error(f"Vector Search Error: {e}")
        return []

def rrf_fusion_weighted(lists, k=60):
    """
    Reciprocal Rank Fusion algorithm ported from Garry Tan's GBrain architecture.
    Takes a list of result lists and fuses them.
    """
    scores = {}

    for result_list in lists:
        for rank, r in enumerate(result_list):
            chunk_id = r["chunk_id"]
            rrf_score = 1.0 / (k + rank)
            
            if chunk_id in scores:
                scores[chunk_id]["score"] += rrf_score
            else:
                scores[chunk_id] = {
                    "result": {
                        "chunk_id": chunk_id,
                        "source": r["source"],
                        "content": r["content"]
                    },
                    "score": rrf_score
                }
                
    fused = list(scores.values())
    fused.sort(key=lambda x: x["score"], reverse=True)
    return [item["result"] for item in fused]

def sovereign_search(query: str, n_results: int = 5):
    """
    The master Hybrid Search loop. 
    Fuses ChromaDB (Vector) and SQLite FTS5 (BM25 Keyword) via RRF (k=60).
    """
    print(f"\n[*] Executing Hybrid Search (Vector + BM25 + RRF): '{query}'")
    
    # 1. Fetch from Vector DB
    vector_results = search_vector(query, n_results=10)
    
    # 2. Fetch from BM25 FTS5
    # FTS5 matches can use simple quote escaping for robustness
    escaped_query = '"{}"'.format(query.replace('"', '""'))
    bm25_results = search_bm25(escaped_query, n_results=10)
    
    if not vector_results and not bm25_results:
        return "No results found in Sovereign memory."
        
    # 3. Apply Reciprocal Rank Fusion
    lists_to_fuse = []
    if vector_results:
        lists_to_fuse.append(vector_results)
    if bm25_results:
        lists_to_fuse.append(bm25_results)
        
    fused_results = rrf_fusion_weighted(lists_to_fuse, k=RRF_K)
    
    # Take top N
    top_results = fused_results[:n_results]
    
    # Format the return string to look exactly like the console output
    output = []
    output.append("========================================================")
    output.append("             SOVEREIGN HYBRID SEARCH RESULT")
    output.append("========================================================\n")
    
    for idx, r in enumerate(top_results):
        output.append(f"--- Source [{idx+1}]: {r['source']} ---")
        output.append(r['content'])
        output.append("")
        
    output.append("--------------------------------------------------------")
    output.append(f"Fused {len(vector_results)} Vector + {len(bm25_results)} BM25 results.")
    output.append("========================================================\n")
    
    result_str = "\n".join(output)
    return result_str

if __name__ == "__main__":
    import sys
    test_query = "What is Reciprocal Rank Fusion?"
    if len(sys.argv) > 1:
        test_query = sys.argv[1]
    print(sovereign_search(test_query))