import sqlite3
import os

DB_PATH = "vault/bm25_index.db"

def setup_fts_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            chunk_id UNINDEXED, 
            source UNINDEXED, 
            content
        );
    """)
    conn.commit()
    return conn

setup_fts_db()
print("Success")
