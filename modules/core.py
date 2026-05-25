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

def enforce_bounds(func):
    """
    Physical bounds checking to enforce hardware/system safety limits 
    PRIOR to DRADIS UI approval.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        func_name = func.__name__
        
        # Check run_shell bounds
        if func_name == "run_shell":
            command = kwargs.get('command') or (args[0] if args else "")
            dangerous_patterns = ["rm -rf /", "mkfs", "dd if=", ":(){ :|:& };:", "sudo rm"]
            for pat in dangerous_patterns:
                if pat in str(command):
                    print(f"🛑 [HARDWARE SAFETY LOCK]: Blocked dangerous shell command containing '{pat}'")
                    return f"ERROR: HARDWARE SAFETY LOCK TRIGGERED. Command violates physical bounds."
                    
        # Check write_code bounds
        elif func_name == "write_code":
            file_path = kwargs.get('file_path') or (args[0] if args else "")
            dangerous_paths = ["/etc", "/boot", "/bin", "/sbin", "/usr/bin", "/root", ".ssh"]
            abs_path = os.path.abspath(str(file_path))
            for pat in dangerous_paths:
                if abs_path.startswith(pat):
                    print(f"🛑 [HARDWARE SAFETY LOCK]: Blocked write access to protected path '{pat}'")
                    return f"ERROR: HARDWARE SAFETY LOCK TRIGGERED. Path '{file_path}' is protected."

        # Pass through if safe
        return func(*args, **kwargs)
    return wrapper

def require_human_approval(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        from modules.approvals.handler import request_approval
        
        # Capture the thought trace if available in a thread-local or passed through
        # For now, we'll try to find it in kwargs or default to empty
        thought_trace = kwargs.pop('thought_trace', "")
        
        params = kwargs if kwargs else (args if args else "No parameters")
        print(f"\n[⚠️ SECURITY ALERT]: Apollo requested: {func.__name__}")
        
        # request_approval now returns (is_approved, edited_params)
        is_approved, edited_params = request_approval(func.__name__, str(params), thought_trace)
        
        if is_approved:
            print(f"[✅ APPROVED]: Executing {func.__name__}...")
            # If the user edited the params in the GUI, we need to parse them back
            if edited_params != str(params):
                try:
                    # Very basic parser for the string representation of dict/args
                    # In a real system, we'd use a more robust serializer
                    if isinstance(params, dict):
                        new_kwargs = eval(edited_params)
                        return func(*args, **new_kwargs)
                    else:
                        # Fallback for positional args
                        return func(*args, **kwargs)
                except:
                    return func(*args, **kwargs)
            return func(*args, **kwargs)
        else:
            print(f"[🛑 DENIED/TIMEOUT]: Action blocked.")
            return "ERROR: User denied or timed out permission for this action."
    return wrapper
