#!/usr/bin/env python3
"""
apollo_bus_mcp.py
FastMCP Server bridging NullClaw on the P100 to the Apollo Sovereign Message Bus & Seed Vault.
Implements the A2A State-Sync protocol to solve Split-Brain filesystem access.
"""

import os
import sqlite3
import json
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP("ApolloBusMCP")

# Database paths
APOLLO_ROOT = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR = os.path.join(APOLLO_ROOT, "vault")
MESSAGE_BUS_DB = os.path.join(VAULT_DIR, "message_bus.db")
SEED_VAULT_DB = os.path.join(VAULT_DIR, "bm25_index.db")

def _get_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# Ensure schema exists
def _init_schemas():
    os.makedirs(VAULT_DIR, exist_ok=True)
    with sqlite3.connect(MESSAGE_BUS_DB) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS task_queue (
                id TEXT PRIMARY KEY,
                task_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                assigned_node TEXT,
                requirements_json TEXT NOT NULL,
                input_payload TEXT,
                output_payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS scratchpad (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

_init_schemas()

@mcp.tool()
def claim_next_task() -> str:
    """Queries the FastAPI broker for pending tasks and claims one."""
    global ACTIVE_TASK_ID
    import urllib.request
    import json
    import platform
    api_url = os.environ.get("MESSAGE_BUS_API", "http://127.0.0.1:8000").rstrip("/")
    node_id = platform.node()
    try:
        req = urllib.request.Request(
            f"{api_url}/tasks/claim",
            data=json.dumps({"node_name": node_id, "node_capabilities": {}}).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req) as res:
            data = json.loads(res.read().decode())
            task = data.get("task")
            if not task:
                return "No pending tasks available."
            
            # Save the active task ID globally for the assassin thread
            ACTIVE_TASK_ID = task['id']

            return json.dumps({
                "task_id": task['id'],
                "instruction": task.get('input_payload', task.get('instruction', ''))
            })
    except Exception as e:
        return f"Error claiming task: {e}"


@mcp.tool()
def submit_task_result(task_id: str, result: str) -> str:
    """Submits the final result for a completed task back to FastAPI broker."""
    global ACTIVE_TASK_ID
    import urllib.request
    import json
    api_url = os.environ.get("MESSAGE_BUS_API", "http://127.0.0.1:8000").rstrip("/")
    try:
        req = urllib.request.Request(
            f"{api_url}/tasks/complete",
            data=json.dumps({"task_id": int(task_id) if task_id.isdigit() else task_id, "result_payload": result, "success": True}).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req) as res:
            if ACTIVE_TASK_ID == task_id:
                ACTIVE_TASK_ID = None
            return f"Task {task_id} marked as completed."
    except Exception as e:
        return f"Error submitting result: {e}"


@mcp.tool()
def query_seed_vault(query: str) -> str:
    """Queries the Apollo Seed Vault (bm25_index.db) for historical context using hybrid FTS5 search."""
    if not os.path.exists(SEED_VAULT_DB):
        return "Seed Vault database not found."
    try:
        with _get_db(SEED_VAULT_DB) as conn:
            cursor = conn.cursor()
            safe_query = query.replace('"', '""')
            cursor.execute(
                "SELECT content FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY rank LIMIT 3", 
                (f'"{safe_query}" OR {safe_query}',)
            )
            results = cursor.fetchall()
            if results:
                return "\n---\n".join([row['content'] for row in results])
            return "No relevant context found in Seed Vault."
    except Exception as e:
        return f"Error querying Seed Vault: {e}"

@mcp.tool()
def read_scratchpad(key: str) -> str:
    """Reads file contents or state from the A2A scratchpad via message_bus.db to bypass Split-Brain filesystem limits."""
    try:
        with _get_db(MESSAGE_BUS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM scratchpad WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                return row['value']
            return f"Error: Scratchpad key '{key}' not found."
    except Exception as e:
        return f"Error reading scratchpad: {e}"

@mcp.tool()
def write_scratchpad(key: str, data: str) -> str:
    """Writes modified state or file contents back to the A2A scratchpad in message_bus.db for the Architect to retrieve."""
    try:
        with _get_db(MESSAGE_BUS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO scratchpad (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP", 
                (key, data)
            )
            conn.commit()
            return f"Successfully wrote {len(data)} characters to scratchpad key '{key}'."
    except Exception as e:
        return f"Error writing to scratchpad: {e}"

import threading
import time
import urllib.request
import platform
import subprocess


ACTIVE_TASK_ID = None

def assassin_thread():
    global ACTIVE_TASK_ID
    import urllib.request
    import json
    import os
    import signal
    import time
    api_url = os.environ.get("MESSAGE_BUS_API", "http://127.0.0.1:8000").rstrip("/")
    
    while True:
        try:
            archetype = "any"
            max_slot_context = 8192
            hot_tokens = 0
            warm_tokens = 0
            kv_precision = "unknown"
            
            try:
                # Query llama-server
                req_props = urllib.request.Request("http://127.0.0.1:8082/props")
                req_slots = urllib.request.Request("http://127.0.0.1:8082/slots")
                with urllib.request.urlopen(req_props, timeout=2.0) as res:
                    props = json.loads(res.read().decode())
                with urllib.request.urlopen(req_slots, timeout=2.0) as res:
                    slots = json.loads(res.read().decode())
                    
                model_alias = props.get("model_alias", "").lower()
                max_slot_context = props.get("default_generation_settings", {}).get("n_ctx", 8192)
                
                archetype = "dense_coder"
                if any(x in model_alias for x in ["moe", "darwin", "gemma"]):
                    archetype = "moe_reasoner"
                    
                HOT_TOKEN_BUDGET = 32000 
                for s in slots:
                    try:
                        toks = s["next_token"][0]["n_decoded"]
                    except (KeyError, IndexError):
                        toks = 0
                        
                    if s.get("is_processing"):
                        hot_tokens += toks
                    else:
                        warm_tokens += toks
                
                if hot_tokens == 0 and warm_tokens > 0:
                    if warm_tokens <= HOT_TOKEN_BUDGET:
                        hot_tokens = warm_tokens
                        warm_tokens = 0
                    else:
                        hot_tokens = HOT_TOKEN_BUDGET
                        warm_tokens = warm_tokens - HOT_TOKEN_BUDGET
            except Exception as llama_err:
                print(f"[Heartbeat] Could not reach local llama-server on 8082: {llama_err}. Assuming busy/down.")

            # Get KV Precision from OS level
            kv_precision = "K: fp16, V: fp16" # default
            try:
                ps_out = subprocess.check_output(["pgrep", "-a", "llama-server"]).decode()
                for line in ps_out.splitlines():
                    if "llama-server" in line:
                        parts = line.split()
                        ctk, ctv = "fp16", "fp16"
                        if "-ctk" in parts:
                            ctk = parts[parts.index("-ctk") + 1]
                        if "-ctv" in parts:
                            ctv = parts[parts.index("-ctv") + 1]
                        kv_precision = f"K: {ctk}, V: {ctv}"
                        break
            except Exception as llama_err:
                print(f"[Heartbeat] Could not reach local llama-server on 8082: {llama_err}. Assuming idle/down.")
                archetype = "any"
                max_slot_context = 8192
                hot_tokens = 0
                warm_tokens = 0
                kv_precision = "unknown"

            # Send heartbeat via HTTP to FastAPI broker
            api_url = os.environ.get("MESSAGE_BUS_API", "http://127.0.0.1:8000").rstrip("/")
            try:
                req_hb = urllib.request.Request(
                    f"{api_url}/node/heartbeat",
                    data=json.dumps({
                        "node_id": node_id,
                        "status": "online",
                        "active_model_archetype": archetype,
                        "max_slot_context": max_slot_context,
                        "hot_kv_tokens": hot_tokens,
                        "warm_kv_tokens": warm_tokens,
                        "kv_precision": kv_precision
                    }).encode('utf-8'),
                    headers={'Content-Type': 'application/json'}
                )
                with urllib.request.urlopen(req_hb, timeout=2) as res:
                    pass
            except Exception as e:
                print(f"[Heartbeat] Failed to send telemetry to {api_url}: {e}")

            time.sleep(5)
        except Exception as e:
            print(f"[Heartbeat] Critical loop error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    t = threading.Thread(target=heartbeat_loop, daemon=True)
    t.start()
    mcp.run()