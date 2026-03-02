import os
import json
import subprocess
import vram_management
import system_monitor
import task_manager
import project_scaffolder
import librarian_ingest
import modules.inventory as inventory
import modules.procurement as procurement
import webcam_capture
from modules.core import require_human_approval, load_json, CitizenDossier
from modules.vdb import query_vdb
from modules.dashboard import get_dashboard

import modules.design_mind as design_mind
import modules.chronicler as chronicler
import modules.forge as forge

class Toolbox:
    @staticmethod
    def forge_idea(thought):
        """Captures a raw engineering vision into the Forge for later refinement."""
        return forge.capture_idea(thought)

    @staticmethod
    def refine_forge():
        """Triggers the expansion of raw ideas into structured proposals using DeepSeek-R1."""
        return forge.refine_ideas()

    @staticmethod
    def list_forge(status="raw"):
        """Lists raw or refined ideas from the Forge."""
        ideas = forge.list_ideas(status)
        if not ideas: return "Forge is empty for status: " + status
        output = [f"--- THE FORGE ({status.upper()}) ---"]
        for i, entry in enumerate(ideas):
            text = entry.get('thought', 'No thought')
            output.append(f"{i+1}. [{entry['timestamp'][:10]}] {text[:100]}...")
        return "\n".join(output)

    @staticmethod
    def sync_mail(limit=50):
        """Ingests recent emails from the local Maildir into the Vector DB."""
        return chronicler.ingest_emails(limit)

    @staticmethod
    def search_emails(query, n_results=5):
        """Searches the user's ingested emails for a specific query."""
        return chronicler.search_emails(query, n_results)

    @staticmethod
    def query_cad_knowledge(query):
        """Queries the Vector DB specifically for OnShape and FeatureScript documentation."""
        return design_mind.query_cad_knowledge(query)

    @staticmethod
    def cad_triage():
        """Captures the screen and uses vision to analyze the OnShape workspace."""
        return design_mind.cad_screenshot_triage()

    @staticmethod
    def log_cad_learning(intent, solution, image_path=None):
        """Saves a CAD interaction to the training log for future DesignMind fine-tuning."""
        return design_mind.log_cad_interaction(intent, solution, image_path)

    @staticmethod
    def analyze_flyer(text_content):
        return procurement.analyze_flyer(text_content)

    @staticmethod
    def update_price(item_name, new_price, store_name="Unknown"):
        return procurement.update_price(item_name, new_price, store_name)

    @staticmethod
    def capture_vision():
        """Captures a frame from the primary webcam and returns the local path."""
        if webcam_capture.capture_webcam(1):
            return webcam_capture.SAVE_PATH
        return "Error: Webcam capture failed."

    @staticmethod
    def show_dashboard(): return get_dashboard()

    @staticmethod
    def harvest_insight(category, insight):
        """Manually adds a personal detail to the Citizen Dossier for brainstorming context."""
        return CitizenDossier.add_insight(category, insight)

    @staticmethod
    def check_gpu(): return json.dumps(vram_management.get_gpu_stats())
    
    @staticmethod
    def check_system(): return json.dumps(system_monitor.get_system_stats())
    
    @staticmethod
    def add_task(description, priority="P1"): return task_manager.add_task(description, priority)
    
    @staticmethod
    def list_tasks(status="open"): return task_manager.list_tasks(status)
    
    @staticmethod
    def complete_task(task_id): return task_manager.complete_task(task_id)

    @staticmethod
    def save_note(title, content):
        """Saves a technical note or list to the vault."""
        notes_dir = "vault/notes"
        os.makedirs(notes_dir, exist_ok=True)
        safe_title = title.lower().replace(" ", "_")
        file_path = os.path.join(notes_dir, f"{safe_title}.md")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"# {title}\n\n{content}")
            return f"Note saved: {file_path}"
        except Exception as e: return f"Note Error: {e}"

    @staticmethod
    def list_notes():
        """Lists all notes in the vault."""
        notes_dir = "vault/notes"
        if not os.path.exists(notes_dir): return "No notes found."
        notes = [f.replace(".md", "") for f in os.listdir(notes_dir) if f.endswith(".md")]
        return "Notes: " + ", ".join(notes) if notes else "No notes found."

    @staticmethod
    def add_hardware(name, category, specs=None, quantity=1, force=False): 
        return inventory.add_hardware(name, category, specs, quantity, force=force)

    @staticmethod
    def list_inventory(): 
        return inventory.get_inventory_summary()

    @staticmethod
    def get_inventory_detail():
        """Returns the full raw inventory for deep inspection."""
        data = inventory.load_inventory()
        output = ["--- FULL INVENTORY DETAIL ---"]
        for item in data.get("items", []):
            specs = json.dumps(item.get("specs", {}))
            output.append(f"- {item['name']} | Qty: {item['quantity']} | Cat: {item['category']} | Specs: {specs}")
        return "\n".join(output)

    @staticmethod
    def diff_inventory(items_to_check):
        """
        Pass a list of strings (e.g. ["screwdrivers", "drill bits"]) 
        to see which are present or missing in the DB.
        """
        return inventory.diff_inventory(items_to_check)

    @staticmethod
    def search_inventory(query):
        return inventory.search_inventory(query)

    @staticmethod
    def update_item_status(name, status):
        return inventory.update_item_status(name, status)

    @staticmethod
    def add_to_wishlist(name, category, notes=""):
        return inventory.add_to_wishlist(name, category, notes)

    @staticmethod
    def visual_inventory_audit(image_path=None):
        """Uses Vision to identify hardware and automatically add it to inventory."""
        target = image_path or webcam_capture.SAVE_PATH
        return f"AGENT INSTRUCTION: [FORCE VISION] [ATTACHED_IMAGE: {target}] Identify every computer component or tool in this photo. Provide Name, Category, and Specs. Then call add_hardware for each."
    
    @staticmethod
    def crop_image(image_path, box):
        """
        Crops an image to focus on a specific area. 
        'box' is a list of [left, top, right, bottom] percentages (0-100).
        Example: [40, 70, 60, 90] to focus on a sticker at the bottom center.
        """
        from PIL import Image
        try:
            with Image.open(image_path) as img:
                w, h = img.size
                left = (box[0] / 100) * w
                top = (box[1] / 100) * h
                right = (box[2] / 100) * w
                bottom = (box[3] / 100) * h
                cropped = img.crop((left, top, right, bottom))
                out_path = image_path.replace(".jpg", "_crop.jpg")
                cropped.save(out_path)
                return f"SUCCESS: Cropped image saved to {out_path}. Re-examine this new image for better detail."
        except Exception as e:
            return f"CROP ERROR: {e}"

    @staticmethod
    def identify_hardware(image_path=None):
        """Specifically used for deep identification of a hardware component (GPU, CPU, etc.) to find its exact model/specs."""
        target = image_path or webcam_capture.SAVE_PATH
        return f"AGENT INSTRUCTION: [FORCE VISION] [ATTACHED_IMAGE: {target}] STOP. Do not guess based on the shroud or cooler. Look for 'Anchor Points': 1. The Model/SKU sticker (Barcode). 2. The PCB ID (e.g., MS-VXXX for MSI, PG132 for NVIDIA). 3. Any silk-screened text near the PCIe pins. List only the strings you are 100% sure of. If no strings are visible, state 'NO_ID_STRINGS_VISIBLE' and suggest a specific angle (e.g., 'show the backplate sticker')."
    
    @staticmethod
    def scaffold_project(name, project_type="python"): return project_scaffolder.scaffold_project(name, project_type)
    
    @staticmethod
    def ingest_url(url): return librarian_ingest. ingest_url(url)
    
    @staticmethod
    def ingest_pdf(file_path): return librarian_ingest.ingest_pdf(file_path)

    @staticmethod
    def write_code(file_path, content):
        try:
            # Force absolute path to project root if relative
            if not os.path.isabs(file_path):
                file_path = os.path.join(os.getcwd(), file_path)
            
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully wrote {len(content)} chars to {file_path}"
        except Exception as e: return f"File Error: {e}"

    @staticmethod
    @require_human_approval
    def run_shell(command):
        print(f"--- [RUNNING SHELL: {command}] ---")
        try:
            res = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=300)
            return f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}\nEXIT_CODE: {res.returncode}"
        except Exception as e: return str(e)

    @staticmethod
    def list_vault_content():
        vault_path = "vault"
        if not os.path.exists(vault_path): return "Vault directory not found."
        # Recursively list vault/cold and vault/chroma_db info
        output = ["Vault Status:"]
        if os.path.exists("vault/cold"):
            pdfs = [f for f in os.listdir("vault/cold") if f.endswith(".pdf")]
            output.append(f"Cold Storage: {len(pdfs)} PDFs found.")
        if os.path.exists("vault/chroma_db"):
            output.append("Hot Storage (Vector DB): Online.")
        return "\n".join(output)

    @staticmethod
    def web_search(query):
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=5)]
            return json.dumps(results)

    @staticmethod
    def query_vault(query, filter_dict=None):
        """Searches the local knowledge base. Defaults to excluding noisy emails."""
        return query_vdb(query, filter_dict=filter_dict)

    @staticmethod
    def hard_kill():
        """Immediate system exit for manual override."""
        print("\n[🚨 HARD KILL COMMAND RECEIVED]: TERMINATING ALL PROCESSES...")
        import sys
        sys.exit(0)
