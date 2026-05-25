import sqlite3
import os
import re

GRAPH_DB_PATH = "vault/graph_memory.db"

def get_graph_conn():
    os.makedirs(os.path.dirname(GRAPH_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(GRAPH_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_node TEXT,
            target_node TEXT,
            edge_type TEXT,
            context TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_node, target_node, edge_type)
        )
    """)
    conn.commit()
    return conn

# Regex cascade for software agent interactions
EDGE_PATTERNS = [
    ("Modified", re.compile(r"(?i)(?:modified|edited|wrote|updated|saved|created).*?`?([a-zA-Z0-9_/\.-]+\.[a-zA-Z0-9]+)`?")),
    ("Read", re.compile(r"(?i)(?:read|viewed|cat|grep|inspected|analyzed).*?`?([a-zA-Z0-9_/\.-]+\.[a-zA-Z0-9]+)`?")),
    ("Executed", re.compile(r"(?i)(?:ran|executed|started|invoked).*?`?([a-zA-Z0-9_/\.-]+)`?")),
]

def infer_link_type(context: str, target: str) -> str:
    """The deterministic regex cascade."""
    for edge_type, pattern in EDGE_PATTERNS:
        if pattern.search(context):
            return edge_type
    return "Mentioned"

def extract_and_store_edges(text: str, default_source: str = "Agent"):
    """Parses raw logs/text and deterministically extracts relationships via Regex."""
    conn = get_graph_conn()
    initial_count = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    
    # Simple line-by-line extraction
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
            
        for edge_type, pattern in EDGE_PATTERNS:
            matches = pattern.findall(line)
            for target in matches:
                # Ensure it's not a hallucination or empty
                if not target or len(target) < 3:
                    continue
                
                # Context window: grab up to 240 chars around the match
                idx = line.find(target)
                start = max(0, idx - 120)
                end = min(len(line), idx + len(target) + 120)
                context_window = line[start:end]
                
                final_type = infer_link_type(context_window, target)
                
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO edges (source_node, target_node, edge_type, context)
                        VALUES (?, ?, ?, ?)
                    """, (default_source, target, final_type, context_window))
                except Exception as e:
                    print(f"Graph DB Error: {e}")
                    
    conn.commit()
    final_count = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    conn.close()
    return final_count - initial_count

if __name__ == "__main__":
    sample_log = "The agent just modified the file `modules/memory_core.py` to fix the bug."
    added = extract_and_store_edges(sample_log)
    print(f"Added {added} edges from sample log.")