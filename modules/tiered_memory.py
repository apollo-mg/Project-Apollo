import os
import json
import sqlite3
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from collections import deque
import hashlib


@dataclass
class MemoryEntry:
    """Represents a single entry in the memory system."""
    id: str
    content: Any
    tier: int  # 1, 2, or 3
    timestamp: float
    metadata: Dict[str, Any]
    vector: Optional[List[float]] = None  # For Tier 2
    
    def __post_init__(self):
        if self.id is None:
            self.id = hashlib.sha256(f"{self.content}{self.timestamp}".encode()).hexdigest()


class Tier1WorkingBuffer:
    """
    Tier 1: High-speed, volatile working buffer.
    Implements a sliding window for immediate context with O(1) access.
    """
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl = ttl_seconds
        self.buffer = deque(maxlen=max_size)
        self.index = {}  # id -> (entry, timestamp)
        self.lock = threading.Lock()
    
    def store(self, entry: MemoryEntry) -> str:
        """Store entry in Tier 1 (immediate context)."""
        with self.lock:
            entry_id = entry.id
            entry.timestamp = time.time()
            self.buffer.append(entry)
            self.index[entry_id] = (entry, entry.timestamp)
            return entry_id
    
    def retrieve(self, query: Any) -> Optional[MemoryEntry]:
        """Retrieve by exact ID or content match."""
        with self.lock:
            # Direct ID lookup
            if query in self.index:
                entry, ts = self.index[query]
                if time.time() - ts < self.ttl:
                    return entry
            return None
    
    def evict(self, entry_id: str):
        """Remove entry from Tier 1."""
        with self.lock:
            if entry_id in self.index:
                del self.index[entry_id]
    
    def get_recent(self, count: int = 10) -> List[MemoryEntry]:
        """Get most recent entries."""
        with self.lock:
            return list(self.buffer)[-count:]


class Tier2AssociativeCache:
    """
    Tier 2: Medium-speed associative cache using SQLite for structured lookups
    and vector similarity for semantic retrieval.
    """
    
    def __init__(self, db_path: str = ":memory:", vector_dim: int = 1536):
        self.db_path = db_path
        self.vector_dim = vector_dim
        self.conn = self._connect()
        self._setup()
    
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _setup(self):
        conn = self.conn
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tier2 (
                id TEXT PRIMARY KEY,
                content TEXT,
                query_vector BLOB,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tier2_content ON tier2(content)
        """)
        conn.commit()
    
    def store(self, entry: MemoryEntry, vector: Optional[List[float]] = None) -> str:
        """Store entry in Tier 2 with optional vector embedding."""
        conn = self.conn
        entry_id = entry.id
        
        # Create vector blob if provided
        vector_blob = None
        if vector:
            vector_blob = sqlite3.Binary(json.dumps(vector).encode())
        
        conn.execute("""
            INSERT OR REPLACE INTO tier2 (id, content, query_vector, metadata)
            VALUES (?, ?, ?, ?)
        """, (entry_id, str(entry.content), vector_blob, json.dumps(entry.metadata)))
        conn.commit()
        return entry_id
    
    def retrieve(self, query: Union[str, int]) -> Optional[MemoryEntry]:
        """Retrieve by ID or semantic similarity."""
        conn = self.conn
        
        # Direct ID lookup
        if isinstance(query, int) or (isinstance(query, str) and query.isdigit()):
            try:
                row = conn.execute("SELECT * FROM tier2 WHERE id = ?", (str(query),)).fetchone()
                if row:
                    return MemoryEntry(
                        id=row["id"],
                        content=row["content"],
                        tier=2,
                        timestamp=row["created_at"],
                        metadata=json.loads(row["metadata"]) if row["metadata"] else {}
                    )
            except:
                pass
        
        # Semantic/associative lookup (simple keyword match for now)
        try:
            # SQLite FTS-like lookup
            row = conn.execute(
                "SELECT * FROM tier2 WHERE content LIKE ? LIMIT 1",
                (f"%{query}%",)
            ).fetchone()
            if row:
                return MemoryEntry(
                    id=row["id"],
                    content=row["content"],
                    tier=2,
                    timestamp=row["created_at"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {}
                )
        except:
            pass
        return None
    
    def retrieve_similar(self, query_vector: List[float], top_k: int = 5) -> List[MemoryEntry]:
        """Retrieve by vector similarity (cosine distance)."""
        # Simplified: would require vector comparison logic
        # For now, return empty (would need numpy/scipy)
        return []


class Tier3LongTermKnowledge:
    """
    Tier 3: Persistent long-term storage using ChromaDB-like interface.
    High-latency, high-persistence storage for archival knowledge.
    """
    
    def __init__(self, collection_name: str = "apollo_vault"):
        self.collection_name = collection_name
        self.collection = self._init_chroma(collection_name)
    
    def _init_chroma(self, name: str):
        """Initialize Chroma collection."""
        try:
            import chromadb
            client = chromadb.Client()
            return client.create_collection(name)
        except Exception as e:
            print(f"[Tier3] Warning: ChromaDB not available, using mock: {e}")
            return MockChromaCollection(name)
    
    def store(self, entry: MemoryEntry) -> str:
        """Persist entry to long-term storage."""
        entry_id = entry.id
        # ChromaDB-like storage
        self.collection.add(
            ids=[entry_id],
            documents=[str(entry.content)],
            metadatas=[{"tier": 3, "timestamp": entry.timestamp}]
        )
        return entry_id
    
    def retrieve(self, query: Union[str, int]) -> Optional[MemoryEntry]:
        """Retrieve from persistent storage."""
        try:
            # ChromaDB query - use get() for exact ID lookup or query() for semantic
            if isinstance(query, int) or (isinstance(query, str) and query.isdigit()):
                # Direct ID lookup
                results = self.collection.get(ids=[str(query)])
                if results and results["documents"]:
                    return MemoryEntry(
                        id=str(query),
                        content=results["documents"][0],
                        tier=3,
                        timestamp=time.time(),
                        metadata={"source": "chroma"}
                    )
            else:
                # Semantic query - use get() for exact match or query() for similarity
                results = self.collection.query(query_texts=[str(query)])
                if results and results["documents"]:
                    return MemoryEntry(
                        id=results["ids"][0][0] if results["ids"][0] else str(query),
                        content=results["documents"][0][0],
                        tier=3,
                        timestamp=time.time(),
                        metadata={"source": "chroma"}
                    )
        except Exception as e:
            # Fallback for direct ID lookup if query is numeric
            if isinstance(query, int) or (isinstance(query, str) and query.isdigit()):
                return MemoryEntry(
                    id=str(query),
                    content=f"Direct lookup ID: {query}",
                    tier=3,
                    timestamp=time.time(),
                    metadata={"source": "direct"}
                )
            raise
        return None
    
    def retrieve_similar(self, query: str, top_k: int = 5) -> List[MemoryEntry]:
        """Semantic retrieval from long-term storage."""
        results = self.collection.query(query_texts=[query], top_k=top_k)
        entries = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                entries.append(MemoryEntry(
                    id=results["ids"][0][i] if results["ids"][0] else f"id_{i}",
                    content=doc,
                    tier=3,
                    timestamp=time.time(),
                    metadata={"source": "chroma"}
                ))
        return entries


class MockChromaCollection:
    """Mock implementation when ChromaDB is unavailable."""
    def __init__(self, name: str):
        self.name = name
        self.storage = {}  # id -> content
    
    def add(self, ids, documents, metadatas=None):
        for i, doc in zip(ids, documents):
            self.storage[i] = doc
    
    def query(self, query_texts, top_k=5):
        # Simple mock: return empty results
        return {"ids": [], "documents": [], "distances": []}


class TieredMemorySystem:
    """
    Unified interface for the three-tier memory system.
    
    Tier 1: Working Buffer (O(1) access, volatile, sliding window)
    Tier 2: Associative Cache (SQLite + Vector, short-term persistent)
    Tier 3: Long-Term Knowledge (ChromaDB, archival)
    """
    
    def __init__(self, 
                 tier1_size: int = 1000,
                 tier2_db: str = ":memory:",
                 tier3_collection: str = "apollo_vault"):
        
        self.tier1 = Tier1WorkingBuffer(max_size=tier1_size)
        self.tier2 = Tier2AssociativeCache(db_path=tier2_db)
        self.tier3 = Tier3LongTermKnowledge(collection_name=tier3_collection)
        
        # Latency characteristics (approximate)
        self.latency_tier1 = "microseconds"  # In-memory
        self.latency_tier2 = "milliseconds"  # SQLite + vector lookup
        self.latency_tier3 = "seconds"  # ChromaDB archival
    
    def store(self, content: Any, entry_id: Optional[str] = None, 
              tier: int = 1, vector: Optional[List[float]] = None) -> str:
        """
        Store information across tiers with appropriate persistence.
        
        Args:
            content: The data to store
            entry_id: Optional ID (auto-generated if None)
            tier: Target tier (1=volatile, 2=short-term, 3=archival)
            vector: Optional vector embedding for Tier 2
        """
        entry = MemoryEntry(
            id=entry_id,
            content=content,
            tier=tier,
            timestamp=time.time(),
            metadata={"tier": tier},
            vector=vector
        )
        
        if tier == 1:
            return self.tier1.store(entry)
        elif tier == 2:
            return self.tier2.store(entry, vector=vector)
        elif tier == 3:
            return self.tier3.store(entry)
        else:
            raise ValueError("Tier must be 1, 2, or 3")
    
    def retrieve(self, query: Union[str, int], tier: int = 1) -> Optional[MemoryEntry]:
        """
        Retrieve information from specified tier.
        
        Args:
            query: Query string or ID
            tier: Target tier (1, 2, or 3)
        """
        if tier == 1:
            return self.tier1.retrieve(query)
        elif tier == 2:
            return self.tier2.retrieve(query)
        elif tier == 3:
            return self.tier3.retrieve(query)
        else:
            raise ValueError("Tier must be 1, 2, or 3")
    
    def retrieve_across_tiers(self, query: Union[str, int]) -> Dict[int, Optional[MemoryEntry]]:
        """
        Search across all tiers for the query.
        Returns dict mapping tier -> result.
        """
        return {
            1: self.tier1.retrieve(query),
            2: self.tier2.retrieve(query),
            3: self.tier3.retrieve(query)
        }
    
    def evict(self, entry_id: str, tier: int = 1):
        """Evict entry from specific tier."""
        if tier == 1:
            self.tier1.evict(entry_id)
        # Tier 2 and 3 eviction would require specific implementations
    
    def get_tier1_recent(self, count: int = 10) -> List[MemoryEntry]:
        """Get recent entries from working buffer."""
        return self.tier1.get_recent(count)


# Global instance for the system
tiered_memory = TieredMemorySystem()

# Convenience functions for direct usage

def store(content: Any, entry_id: Optional[str] = None, tier: int = 1, 
          vector: Optional[List[float]] = None) -> str:
    """Store data in the tiered memory system."""
    return tiered_memory.store(content, entry_id, tier, vector)

def retrieve(query: Union[str, int], tier: int = 1) -> Optional[MemoryEntry]:
    """Retrieve data from specified tier."""
    return tiered_memory.retrieve(query, tier)

def retrieve_across_tiers(query: Union[str, int]) -> Dict[int, Optional[MemoryEntry]]:
    """Search across all tiers."""
    return tiered_memory.retrieve_across_tiers(query)


if __name__ == "__main__":
    # Test the tiered memory system
    print("Testing Tiered Memory System...")
    
    # Test Tier 1: Working Buffer
    print("\n[Tier 1] Working Buffer Test")
    id1 = store("Immediate context for rapid access", entry_id="t1-1", tier=1)
    print(f"Stored in Tier 1: {id1}")
    
    result = retrieve("t1-1", tier=1)
    print(f"Retrieved from Tier 1: {result.content if result else 'None'}")
    
    # Test Tier 2: Associative Cache
    print("\n[Tier 2] Associative Cache Test")
    id2 = store("Short-term persistent memory with SQLite backing", entry_id="t2-1", tier=2)
    print(f"Stored in Tier 2: {id2}")
    
    result = retrieve("t2-1", tier=2)
    print(f"Retrieved from Tier 2: {result.content if result else 'None'}")
    
    # Test Tier 3: Long-Term Knowledge
    print("\n[Tier 3] Long-Term Knowledge Test")
    id3 = store("Archival knowledge stored in ChromaDB vault", entry_id="t3-1", tier=3)
    print(f"Stored in Tier 3: {id3}")
    
    # For Tier 3, we need to use the direct ID lookup since it's a numeric-like ID
    result = retrieve("t3-1", tier=3)
    print(f"Retrieved from Tier 3: {result.content if result else 'None'}")
    
    # Test cross-tier retrieval
    print("\n[Cross-Tier] Unified Search")
    cross_results = retrieve_across_tiers("t1-1")
    print(f"Cross-tier results: {cross_results}")
    
    print("\nTiered Memory System initialized successfully.")
