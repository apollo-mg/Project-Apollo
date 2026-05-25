import os
import json
import time
import logging
from modules.vdb import query_vdb
from desktop_eyes import capture_screen

# Logging for CAD Training Data
CAD_TRAINING_LOG = "vault/cad_training.jsonl"

def query_cad_knowledge(query: str):
    """Queries the Vector DB specifically for CAD/OnShape information."""
    # We can add a prefix to guide the search if needed
    enhanced_query = f"OnShape FeatureScript CAD: {query}"
    return query_vdb(enhanced_query, n_results=5)

def cad_screenshot_triage():
    """Captures a screenshot of the OnShape workspace and prepares for vision analysis."""
    os.makedirs("tmp/vision", exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"tmp/vision/cad_{timestamp}.png"
    try:
        path = capture_screen(filename)
        return f"AGENT INSTRUCTION: [FORCE VISION] [ATTACHED_IMAGE: {path}] Analyze this OnShape workspace. 1. Identify current tool/mode (e.g., Sketch, Feature, Assembly). 2. Look for error indicators (red features, over-constrained lines). 3. Describe what the user is currently working on based on the feature tree and graphics area."
    except Exception as e:
        return f"Capture Error: {e}"

def log_cad_interaction(intent: str, solution: str, image_path: str = None):
    """Logs a CAD interaction for future DesignMind training."""
    entry = {
        "timestamp": time.time(),
        "intent": intent,
        "solution": solution,
        "image_path": image_path,
        "type": "cad_training_pair"
    }
    os.makedirs(os.path.dirname(CAD_TRAINING_LOG), exist_ok=True)
    with open(CAD_TRAINING_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return f"Logged CAD interaction to {CAD_TRAINING_LOG}"
