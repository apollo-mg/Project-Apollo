import sqlite3
import json
import logging
from contextlib import closing
from typing import Dict, List, Optional
from datetime import datetime

"""
SOVEREIGN ENGINE: DISTRIBUTED MESSAGE BUS
=========================================
Architectural Intent:
This module replaces fragile JSON file-passing with a robust, ACID-compliant SQLite `TaskQueue`. 
It allows the main Architect model (RX 9070) to asynchronously dispatch sub-tasks to Edge Nodes 
(Raspberry Pi, Galaxy S21) without blocking the main event loop or risking race conditions.

LLM Agent Instructions (CRITICAL):
1. Concurrency: Do NOT attempt to read/write raw files for inter-agent communication. Always use this bus.
2. WAL Mode: This database uses `PRAGMA journal_mode=WAL`, meaning readers are not blocked by writers.
3. Locking: The `claim_task()` method uses `BEGIN EXCLUSIVE TRANSACTION`. This mathematically guarantees 
   that if the Pi 5 and S21 wake up simultaneously, they cannot accidentally claim the same pending task.
"""

class SovereignMessageBus:
    """
    SQLite-backed asynchronous queue for the Sovereign cluster.
    Follows the 'Coordinator -> Worker' topology seen in high-end agentic architectures.
    """
    def __init__(self, db_path: str = "data/message_bus.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initializes the SQLite schema with strict ACID compliance."""
        with closing(sqlite3.connect(self.db_path, timeout=30.0)) as conn:
            # Enforce WAL mode for much better concurrent read/write performance
            conn.execute("PRAGMA journal_mode=WAL;")
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS task_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending', -- pending, claimed, completed, failed
                    assigned_node TEXT,
                    requirements_json TEXT NOT NULL,
                    input_payload TEXT,
                    output_payload TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS scratchpad (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def publish_task(self, task_name: str, requirements: Dict, payload: str) -> int:
        """The Architect publishes a new task to the queue."""
        with closing(sqlite3.connect(self.db_path, timeout=30.0)) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO task_queue (task_name, requirements_json, input_payload)
                VALUES (?, ?, ?)
            ''', (task_name, json.dumps(requirements), payload))
            conn.commit()
            logging.info(f"[MessageBus] Task '{task_name}' published. ID: {cursor.lastrowid}")
            return cursor.lastrowid

    def claim_task(self, node_name: str, node_capabilities: Dict) -> Optional[Dict]:
        """
        A worker node (like BonPi) attempts to claim the oldest pending task 
        that matches its capabilities. This uses a transaction to prevent race conditions.
        """
        with closing(sqlite3.connect(self.db_path, timeout=30.0)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Use an exclusive transaction to lock the queue briefly
            cursor.execute("BEGIN EXCLUSIVE TRANSACTION")
            
            # Find all pending tasks
            cursor.execute("SELECT * FROM task_queue WHERE status = 'pending' ORDER BY created_at ASC")
            pending_tasks = cursor.fetchall()

            for task in pending_tasks:
                reqs = json.loads(task['requirements_json'])
                
                # Check target role routing
                target_node = reqs.get('target_node', 'any')
                node_role = node_capabilities.get('node_role', 'any')
                
                if target_node != 'any':
                    if target_node != node_name and target_node != node_role:
                        continue # Fails explicit routing constraint
                
                # Check Capability Physics (The Logic from CapabilityRouter)
                if node_capabilities['context_window'] >= reqs.get('min_context', 0) and \
                   node_capabilities['precision_bits'] >= reqs.get('min_precision', 1.0):
                   
                    if reqs.get('requires_internet', False) and not node_capabilities.get('internet_access', False):
                        continue # Fails internet physics
                    
                    # We found a match! Claim it instantly before another node does.
                    cursor.execute('''
                        UPDATE task_queue 
                        SET status = 'claimed', assigned_node = ?, updated_at = CURRENT_TIMESTAMP 
                        WHERE id = ? AND status = 'pending'
                    ''', (node_name, task['id']))
                    
                    if cursor.rowcount == 1:
                        conn.commit()
                        logging.info(f"[MessageBus] Node '{node_name}' claimed Task #{task['id']}")
                        return dict(task)

            # If we get here, no tasks matched the node's capabilities
            conn.commit()
            return None

    def complete_task(self, task_id: int, result_payload: str, success: bool = True):
        """A worker node submits the final output payload back to the bus."""
        status = 'completed' if success else 'failed'
        with closing(sqlite3.connect(self.db_path, timeout=30.0)) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE task_queue 
                SET status = ?, output_payload = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (status, result_payload, task_id))
            conn.commit()
            logging.info(f"[MessageBus] Task #{task_id} marked as {status}.")

    def check_task_status(self, task_id: int) -> Optional[Dict]:
        """Allows the Architect to poll the status of a previously dispatched task."""
        with closing(sqlite3.connect(self.db_path, timeout=30.0)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM task_queue WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def reset_stalled_tasks(self, timeout_minutes: int = 15):
        """Identifies 'claimed' tasks older than timeout_minutes and resets them to 'pending'."""
        with closing(sqlite3.connect(self.db_path, timeout=30.0)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Find stalled tasks
            cursor.execute('''
                SELECT id, task_name, assigned_node FROM task_queue 
                WHERE status = 'claimed' AND 
                (julianday(CURRENT_TIMESTAMP) - julianday(updated_at)) * 1440 > ?
            ''', (timeout_minutes,))
            
            stalled_tasks = cursor.fetchall()
            
            if not stalled_tasks:
                return

            try:
                # Import dynamically to avoid circular dependencies or path issues
                import sys
                import os
                sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                from telemetry_layer import ImmutableTelemetryLayer
                telemetry = ImmutableTelemetryLayer()
            except Exception as e:
                logging.error(f"[MessageBus] Failed to initialize TelemetryLayer: {e}")
                telemetry = None

            for task in stalled_tasks:
                task_id = task['id']
                node = task['assigned_node']
                
                # Reset to pending
                cursor.execute('''
                    UPDATE task_queue 
                    SET status = 'pending', assigned_node = NULL, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                ''', (task_id,))
                
                logging.warning(f"[MessageBus] Node Timeout! Task #{task_id} (claimed by {node}) was stalled. Resetting to 'pending'.")
                
                if telemetry:
                    telemetry.record_event(
                        event_type="Node Timeout", 
                        description=f"Task #{task_id} ({task['task_name']}) stalled on node '{node}' and was reset.", 
                        severity="ERROR",
                        metadata={"task_id": task_id, "node": node}
                    )
            
            conn.commit()

    def write_scratchpad(self, key: str, value: str) -> None:
        """Writes or updates a value in the cluster-wide scratchpad."""
        with closing(sqlite3.connect(self.db_path, timeout=30.0)) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO scratchpad (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    updated_at=CURRENT_TIMESTAMP
            ''', (key, value))
            conn.commit()

    def read_scratchpad(self, key: str) -> Optional[str]:
        """Reads a value from the cluster-wide scratchpad."""
        with closing(sqlite3.connect(self.db_path, timeout=30.0)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM scratchpad WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                return row[0]
            return None

class RemoteMessageBus:
    """
    HTTP client wrapper for SovereignMessageBus.
    Used by remote worker nodes to interact with the central SQLite database over the network,
    avoiding network filesystem locking issues while maintaining WAL mode concurrency on the host.
    """
    def __init__(self, api_url: str):
        self.api_url = api_url.rstrip("/")

    def publish_task(self, task_name: str, requirements: Dict, payload: str) -> int:
        import urllib.request
        import json
        req = urllib.request.Request(
            f"{self.api_url}/tasks/publish",
            data=json.dumps({
                "task_name": task_name,
                "requirements": requirements,
                "payload": payload
            }).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req) as res:
            data = json.loads(res.read().decode())
            return data["task_id"]

    def claim_task(self, node_name: str, node_capabilities: Dict) -> Optional[Dict]:
        import urllib.request
        import json
        req = urllib.request.Request(
            f"{self.api_url}/tasks/claim",
            data=json.dumps({
                "node_name": node_name,
                "node_capabilities": node_capabilities
            }).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        try:
            with urllib.request.urlopen(req) as res:
                data = json.loads(res.read().decode())
                return data.get("task")
        except urllib.error.URLError:
            # Handle connection refused if server is not reachable
            return None

    def complete_task(self, task_id: int, result_payload: str, success: bool = True):
        import urllib.request
        import json
        req = urllib.request.Request(
            f"{self.api_url}/tasks/complete",
            data=json.dumps({
                "task_id": task_id,
                "result_payload": result_payload,
                "success": success
            }).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req) as res:
            pass

    def check_task_status(self, task_id: int) -> Optional[Dict]:
        import urllib.request
        import json
        req = urllib.request.Request(f"{self.api_url}/tasks/{task_id}")
        with urllib.request.urlopen(req) as res:
            data = json.loads(res.read().decode())
            return data.get("task")

if __name__ == "__main__":
    import os
    if not os.path.exists("data"):
        os.makedirs("data")
        
    bus = SovereignMessageBus()
    
    # 1. The Architect (RX 9070) breaks down a goal and publishes a sub-task.
    task_id = bus.publish_task(
        task_name="scrape_anthropic_docs",
        requirements={"min_context": 8000, "requires_internet": True, "min_precision": 4.0},
        payload="https://docs.anthropic.com/claude/reference"
    )
    
    # 2. BonPi wakes up and tries to claim a task.
    bonpi_caps = {"context_window": 65536, "internet_access": False, "precision_bits": 1.0}
    claimed = bus.claim_task("BonPi_Edge", bonpi_caps)
    # Result: None (BonPi doesn't have internet access, so it ignores the task).
    
    # 3. The Pocket Assistant (S21) wakes up.
    s21_caps = {"context_window": 8192, "internet_access": True, "precision_bits": 4.0}
    claimed = bus.claim_task("PocketAssistant_S21", s21_caps)
    # Result: Claimed! The S21 fits the physics.
    
    if claimed:
        # S21 does the work...
        bus.complete_task(claimed['id'], result_payload="Extracted API Reference Data...", success=True)
