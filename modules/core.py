import json
import os
import vram_management
import llm_interface
import threading
import re
import shop_bridge as local_agent
import functools
import warnings

# Common Paths
DOSSIER_PATH = "shop_dossier.json"
PERSONA_PATH = "buddy_persona.md"
SOUL_PATH = "SOUL.md"
MEMORY_PATH = "MEMORY.md"
ROADMAP_PATH = "ROADMAP.md"
HISTORY_PATH = "tmp/buddy_history.json"

class CitizenDossier:
    """
    Manages the persistent profile of the Sovereign User.
    Organizes disparate claims into meaningful categories for brainstorming.
    """
    DEFAULT_STRUCTURE = {
        "identity": {"name": "Mark", "role": "Sovereign User / Lead Engineer"},
        "projects": [],      # Active technical endeavors
        "preferences": [],   # Coding style, communication style, etc.
        "philosophy": [],    # Moral/Ethical stances (e.g., Sovereign AI)
        "history": [],       # Past achievements or discovered system truths
        "brainstorming_seeds": [] # Ideas waiting for development
    }

    @staticmethod
    def load():
        data = load_json(DOSSIER_PATH)
        if not data or "identity" not in data:
            return CitizenDossier.DEFAULT_STRUCTURE
        return data

    @staticmethod
    def save(data):
        save_json(DOSSIER_PATH, data)

    @staticmethod
    def add_insight(category, claim):
        dossier = CitizenDossier.load()
        if category not in dossier:
            dossier[category] = []
        
        # Avoid duplicates
        if claim not in dossier[category]:
            dossier[category].append(claim)
            CitizenDossier.save(dossier)
            return f"Insight added to {category}: {claim}"
        return "Insight already exists."

def load_text(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f: return f.read()
    return ""

def load_json(path):
    if os.path.exists(path):
        if os.path.getsize(path) > 0:
            with open(path, 'r', encoding='utf-8') as f: return json.load(f)
    return {}

def save_json(path, data):
    dir_name = os.path.dirname(path)
    if dir_name: os.makedirs(dir_name, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4)

def clean_json_string(s):
    s = re.sub(r'```json\s*(.*?)\s*```', r'\1', s, flags=re.DOTALL)
    s = "".join(ch for ch in s if ch.isprintable() or ch in ["\n", "\t", "\r"])
    return s.strip()

def require_human_approval(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # We prefer the asynchronous queue over blocking terminal input
        # This allows for future GUI/Discord/Phone-based approvals
        from modules.approvals.handler import request_approval
        
        params = kwargs if kwargs else (args if args else "No parameters")
        print(f"\n[⚠️ SECURITY ALERT]: Apollo requested: {func.__name__}")
        
        # If we are in a TTY, we can still use input() as a fallback, 
        # but let's prioritize the queue-based approach for robustness.
        if request_approval(func.__name__, str(params)):
            print(f"[✅ APPROVED]: Executing {func.__name__}...")
            return func(*args, **kwargs)
        else:
            print(f"[🛑 DENIED/TIMEOUT]: Action blocked.")
            return "ERROR: User denied or timed out permission for this action."
    return wrapper
