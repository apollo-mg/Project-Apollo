---
name: implement-regex-knowledge-graph-cascade
description: Implement a deterministic Regex-based inference cascade to extract knowledge graph edges from logs and markdown without LLM overhead. Use when processing high-volume session data or background "Daydream" logs where cost and VRAM usage of an LLM would be prohibitive.
---

# Implement Regex Knowledge Graph Cascade

Inspired by the "GBrain" architecture, this skill provides a procedure for extracting structured relationship edges (Knowledge Graph) from unstructured text logs using fast, deterministic regex patterns.

## Procedure

### 1. Define the Edge Schema
Identify the relationship types you want to extract.
- `Agent -> MODIFIED -> File`
- `Agent -> DELEGATED_TO -> SubAgent`
- `Task -> FAILED_WITH -> ErrorString`

### 2. Implement the Regex Cascade
Create a series of regex patterns that match specific tool or agent behaviors in the logs.

**Python Implementation Pattern:**
```python
import re

patterns = {
    "MODIFIED": re.compile(r"Successfully (?:modified|overwrote) file: (?P<path>[\w\-/.]+)"),
    "DELEGATED": re.compile(r"Spawning sub-agent to handle task: (?P<task>.*)"),
    "ERROR": re.compile(r"ERROR: (?P<msg>.*)")
}

def extract_edges(log_text):
    edges = []
    for line in log_text.splitlines():
        for edge_type, pattern in patterns.items():
            match = pattern.search(line)
            if match:
                edges.append({"type": edge_type, "data": match.groupdict()})
    return edges
```

### 3. Wire to the Graph Database
Pipe the extracted edges into a local database (e.g., SQLite or PGLite).

**Action:** Use a dedicated module like `modules/graph_memory.py` to handle the `INSERT` logic.

### 4. Continuous Ingestion (Daydream Loop)
Integrate the cascade into a background daemon (like `daydream_v2.py`). 
- **Pass 0**: Deterministic Regex extraction (instant).
- **Pass 1**: High-level LLM abstraction (VRAM-heavy, run only on high-signal data).

## Verification

### Accuracy Check
Run the regex against a known "Gold Standard" log and verify the edge count matches expected results.

### Performance
The cascade should process thousands of log lines in milliseconds, whereas an LLM would take seconds per turn.
