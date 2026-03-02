import os
import json
from datetime import datetime
from modules.core import load_json, save_json, CitizenDossier
from modules.vdb import get_vector_store, get_text_splitter
from langchain_core.documents import Document

from llm_interface import query_llm, ARCHITECT_MODEL

# --- Configuration ---
FORGE_RAW_PATH = "vault/forge_raw.jsonl"
FORGE_REFINED_PATH = "vault/forge_refined.jsonl"

def capture_idea(raw_thought: str, source: str = "manual"):
    """
    Captures a raw thought into the Forge.
    """
    entry = {
        "timestamp": datetime.now().isoformat(),
        "source": source,
        "thought": raw_thought,
        "status": "raw"
    }
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(FORGE_RAW_PATH), exist_ok=True)
    
    with open(FORGE_RAW_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry) + "\n")
    
    # Also add as a seed to the CitizenDossier for immediate context
    CitizenDossier.add_insight("brainstorming_seeds", f"{entry['timestamp']}: {raw_thought}")
    
    return f"Successfully forged raw thought: '{raw_thought[:50]}...'"

def refine_ideas():
    """
    Uses the Architect (Qwen3-Coder:30B) to process raw thoughts into refined project proposals.
    """
    if not os.path.exists(FORGE_RAW_PATH):
        return "No raw thoughts to refine."
    
    raw_entries = []
    with open(FORGE_RAW_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                raw_entries.append(json.loads(line))
            
    if not raw_entries:
        return "Forge is empty."

    refined_count = 0
    vector_store = get_vector_store()
    
    # Keep track of updated entries
    updated_raw_entries = []
    
    for entry in raw_entries:
        if entry.get("status") == "raw":
            print(f"Refining: {entry['thought'][:50]}...")
            
            # 1. Expand the thought using Qwen3-Coder:30B (The Architect)
            prompt = f"""You are 'The Architect', the structural engine of Project Apollo. 
Take the following raw engineering vision and expand it into a high-fidelity, sovereign project architecture.
Include:
- System Architecture & Data Flow
- Component Breakdown (Modules, APIs, VDB integration)
- Hardware Strategy (Optimized for RDNA 4 / ROCm)
- Deployment Strategy (Local, Offline-First)
- Future Expansion Paths

RAW THOUGHT: {entry['thought']}
"""
            refined_content = query_llm(prompt, model_override=ARCHITECT_MODEL)
            
            if "Error" in refined_content:
                print(f"Skipping due to error: {refined_content}")
                updated_raw_entries.append(entry)
                continue

            # 2. Save to refined log
            refined_entry = entry.copy()
            refined_entry["status"] = "refined"
            refined_entry["refined_content"] = refined_content
            refined_entry["refined_at"] = datetime.now().isoformat()
            refined_entry["posted_to_discord"] = False
            
            os.makedirs(os.path.dirname(FORGE_REFINED_PATH), exist_ok=True)
            with open(FORGE_REFINED_PATH, 'a', encoding='utf-8') as f:
                f.write(json.dumps(refined_entry) + "\n")
            
            # 3. Index into VDB
            doc = Document(
                page_content=refined_content,
                metadata={
                    "source": "the_forge",
                    "type": "idea_refinement",
                    "original_thought": entry["thought"],
                    "original_timestamp": entry["timestamp"]
                }
            )
            vector_store.add_documents([doc])
            
            # Mark as refined in memory
            entry["status"] = "refined"
            refined_count += 1
        
        updated_raw_entries.append(entry)
            
    # Update the raw file with the 'refined' status
    with open(FORGE_RAW_PATH, 'w', encoding='utf-8') as f:
        for entry in updated_raw_entries:
            f.write(json.dumps(entry) + "\n")
            
    return f"Successfully refined {refined_count} ideas using The Architect (Qwen3-Coder:30B) and indexed them into the VDB."



def list_ideas(status="raw"):
    """Lists ideas from the forge."""
    path = FORGE_RAW_PATH if status == "raw" else FORGE_REFINED_PATH
    if not os.path.exists(path):
        return []
    
    ideas = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            ideas.append(json.loads(line))
    return ideas
