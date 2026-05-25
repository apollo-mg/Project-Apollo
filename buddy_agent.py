import warnings
import logging

# Suppress annoying Pydantic/Langchain warnings and verbose HTTP logs
warnings.filterwarnings("ignore", message=".*Pydantic V1.*")
warnings.filterwarnings("ignore", category=UserWarning, module="langchain_core")
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

import sys
import argparse
import re
from modules.theme import stylized_print, CLR_CYAN, CLR_GOLD
from modules.toolbox import Toolbox
from buddy_guardian import SovereignGuardian
from modules.agent_session import ApolloAgentSession

class Orchestrator:
    @staticmethod
    def fast_path(user_input):
        low = user_input.lower()
        if "inventory mode" in low:
            return "Acknowledged. Inventory mode. What do you want to do? (Options: List by category, Add an item, Report damage, Add to wishlist)"
        if "gpu" in low or "vram" in low: return Toolbox.check_gpu()
        if any(x in low for x in ["cpu", "ram", "disk", "memory"]): return Toolbox.check_system()
        if "task" in low or "todo" in low:
            if any(v in low for v in ["list", "show", "status"]): return Toolbox.list_tasks()
        if "list vault" in low: return Toolbox.list_vault_content()
        if "notes" in low and any(v in low for v in ["list", "show"]): return Toolbox.list_notes()
        if "inventory" in low and any(v in low for v in ["list", "show", "detail"]): return Toolbox.get_inventory_detail()
        if "forge" in low and any(v in low for v in ["list", "show"]):
            status = "refined" if "refined" in low else "raw"
            return Toolbox.list_forge(status)
        if "refine forge" in low: return Toolbox.refine_forge()
        return None

def chat_with_buddy(user_input):
    # Topic Model: Initial Analysis
    print(f"Topic: <Research> : Analyzing request and system state")
    
    # 1. Fast Path
    fp_res = Orchestrator.fast_path(user_input)
    if fp_res:
        stylized_print("integrity", "System: VERIFIED.", color=CLR_GOLD)
        return fp_res

    # Integrity
    if "VERIFIED" in SovereignGuardian.check_system_integrity():
        stylized_print("integrity", "System: VERIFIED.", color=CLR_GOLD)
    else:
        stylized_print("alert", "INTEGRITY BREACH!", color=CLR_GOLD)

    # 2. Vision Shortcut Extraction
    image_path = None
    m = re.search(r'\[ATTACHED_IMAGE:\s*(.*?)\s*\]', user_input)
    if m:
        image_path = m.group(1).strip()
        user_input = user_input.replace(m.group(0), "").strip()
    
    # 3. Start High-Fidelity Session
    session = ApolloAgentSession(user_input, image_path=image_path)
    return session.run()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", nargs="*", help="User prompt")
    parser.add_argument("--queue", action="store_true", help="Consume a task from the heartbeat queue")
    args = parser.parse_args()
    
    if args.queue:
        import os
        import json
        queue_file = "data/heartbeat_queue.json"
        if os.path.exists(queue_file):
            try:
                with open(queue_file, 'r', encoding='utf-8') as f:
                    tasks = json.load(f)
                
                pending = [t for t in tasks if t.get("status") == "pending"]
                if pending:
                    task = pending[0]
                    # Mark as processing
                    task["status"] = "processing"
                    with open(queue_file, 'w', encoding='utf-8') as f:
                        json.dump(tasks, f, indent=2)
                        
                    print(f"🔄 Processing queue task [{task['source']}]: {task['description']}")
                    
                    # Convert task to a prompt Zoey can understand
                    agent_prompt = f"[SYSTEM TASK from {task['source']} (Urgency: {task['urgency']})]\n{task['description']}\nContext: {json.dumps(task['context'])}"
                    chat_with_buddy(agent_prompt)
                    
                    # Mark as completed
                    task["status"] = "completed"
                    with open(queue_file, 'w', encoding='utf-8') as f:
                        json.dump(tasks, f, indent=2)
                else:
                    print("No pending tasks in queue.")
            except Exception as e:
                print(f"Error reading queue: {e}")
        else:
            print("Queue file not found.")
        sys.exit(0)
        
    user_prompt = ""
    if not sys.stdin.isatty():
        with sys.stdin as f: user_prompt = f.read().strip()
    if args.prompt: user_prompt += ("\n" + " ".join(args.prompt)).strip()
    
    if user_prompt:
        chat_with_buddy(user_prompt)
