import os
import time
import json
import threading
from datetime import datetime, timezone

class ImmutableTelemetryLayer:
    """
    Implements the 'Resilient State-Persistence' layer.
    Records state transitions and system health independently of main logic.
    """
    def __init__(self, log_file="/mnt/TG_2TB/Projects/Apollo/telemetry_state_log.jsonl"):
        self.log_file = log_file
        self.lock = threading.Lock()
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w') as f:
                pass

    def record_transition(self, component, old_state, new_state, metadata=None):
        """
        Atomically records a state transition.
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": component,
            "transition": {
                "from": old_state,
                "to": new_state
            },
            "metadata": metadata or {}
        }
        self._append_to_log(entry)

    def record_event(self, event_type, description, severity="INFO", metadata=None):
        """
        Records a low-level system event.
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "description": description,
            "severity": severity,
            "metadata": metadata or {}
        }
        self._append_to_log(entry)

    def _append_to_log(self, entry):
        with self.lock:
            try:
                with open(self.log_file, 'a') as f:
                    f.write(json.dumps(entry) + "\n")
            except Exception as e:
                # Fallback to stderr if file writing fails
                print(f"[TELEMETRY_CRITICAL] Failed to write to {self.log_file}: {e}")

    def get_recent_history(self, limit=100):
        """
        Retrieves recent history for recovery/audit.
        """
        history = []
        try:
            with open(self.log_file, 'r') as f:
                for line in f:
                    if line.strip():
                        history.append(json.loads(line))
            return history[-limit:]
        except Exception as e:
            print(f"[TELEMETRY_ERROR] Failed to read log: {e}")
            return []

if __name__ == "__main__":
    # Test the layer
    telemetry = ImmutableTelemetryLayer()
    print("Testing Telemetry Layer...")
    
    # Test Transition
    telemetry.record_transition("CORE_ENGINE", "IDLE", "RUNNING", {"task_id": "12345"})
    
    # Test Event
    telemetry.record_event("SYSTEM_CHECK", "Disk space check completed", "INFO", {"free_gb": 45.2})
    
    # Test Critical Event
    telemetry.record_event("ENTROPY_DETECTED", "Unexpected directory deletion detected", "CRITICAL", {"path": "/tmp/lost_work"})

    # Verify
    history = telemetry.get_recent_history(5)
    print(f"Retrieved {len(history)} recent entries:")
    for h in history:
        print(f"  {h}")
