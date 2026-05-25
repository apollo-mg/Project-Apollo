import os
import json
import requests
import datetime

# Configuration
API_URL = "http://10.0.0.5:11435/v1/chat/completions"
DATA_DIR = "/home/gemini/Project-Apollo/data"
DOSSIER_FILE = "/home/gemini/Project-Apollo/Dossier.md"
FACTS_FILE = os.path.join(DATA_DIR, "apollo_facts.jsonl")
QUESTIONS_FILE = os.path.join(DATA_DIR, "PENDING_QUESTIONS.md")

def read_dossier():
    if os.path.exists(DOSSIER_FILE):
        with open(DOSSIER_FILE, 'r', encoding='utf-8') as f:
            return f.read()
    return "# Project Apollo: Sovereign Engine Dossier\n\n## Core Identity\n\n## Hardware\n\n## Project Roadmaps\n"

def read_facts():
    facts = []
    if os.path.exists(FACTS_FILE):
        with open(FACTS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        facts.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return facts

def clear_facts():
    if os.path.exists(FACTS_FILE):
        os.remove(FACTS_FILE)

def execute_dream_cycle():
    print(f"[{datetime.datetime.now()}] Initiating Sovereign Dream Cycle...")
    
    facts = read_facts()
    if not facts:
        print("[*] No new facts to consolidate. Sleeping.")
        return

    current_dossier = read_dossier()
    
    print(f"[*] Loaded {len(facts)} raw facts from Liara's harvest.")
    
    # Format facts for the prompt
    formatted_facts = ""
    for idx, f in enumerate(facts):
        formatted_facts += f"{idx+1}. [{f.get('category', 'unknown')}] {f.get('fact', '')}\n"

    system_prompt = """You are the Sovereign Architect (35B MoE), running the nightly 'Dream Cycle' memory consolidation. 
Your objective is to update the master Dossier based on a list of newly extracted daily facts.

RULES:
1. DEDUPLICATE: Ignore facts that are already present in the current Dossier.
2. SYNTHESIZE: Combine related facts into concise, high-level architectural bullet points. Do not keep raw conversational logs.
3. CONFLICT RESOLUTION: If a new fact supersedes an old one (e.g., a hardware upgrade or a pivot), overwrite the old data.
4. AMBIGUITY: If a fact is important but lacks context (e.g., "The integration failed" but doesn't say which one), DO NOT add it to the Dossier. Instead, write a question for Mark in the "PENDING QUESTIONS" section.

OUTPUT FORMAT:
You must output EXACTLY two sections separated by the marker "===END_DOSSIER===". 
The first section is the completely rewritten Markdown for Dossier.md.
The second section is a bulleted list of questions for PENDING_QUESTIONS.md (if none, write "No pending questions.").
"""

    user_prompt = f"""--- CURRENT DOSSIER ---
{current_dossier}

--- NEW DAILY FACTS ---
{formatted_facts}

Task: Rewrite the Dossier integrating these new facts, then output pending questions."""

    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2, # Low temp for factual consistency
        "max_tokens": 3000
    }

    print("[*] Sending data to Architect (10.0.0.5:11435) for consolidation...")
    
    try:
        res = requests.post(API_URL, json=payload, timeout=300) # 5 minute timeout for heavy reasoning
        if res.status_code == 200:
            content = res.json()['choices'][0]['message']['content']
            
            if "===END_DOSSIER===" in content:
                parts = content.split("===END_DOSSIER===")
                new_dossier = parts[0].strip()
                new_questions = parts[1].strip()
                
                # Sanity check: Don't overwrite if the model glitched and returned almost nothing
                if len(new_dossier) > 100:
                    with open(DOSSIER_FILE, 'w', encoding='utf-8') as f:
                        f.write(new_dossier)
                    print(f"[+] Dossier updated successfully. Length: {len(new_dossier)} chars.")
                    
                    if "No pending questions" not in new_questions and new_questions.strip():
                        # Append to pending questions
                        with open(QUESTIONS_FILE, 'a', encoding='utf-8') as f:
                            f.write(f"\n### Cycle: {datetime.datetime.now().strftime('%Y-%m-%d')}\n")
                            f.write(new_questions + "\n")
                        print("[+] Pending questions logged.")
                    
                    clear_facts()
                    print("[+] Ephemeral facts cleared. Dream Cycle complete.")
                else:
                    print("[-] Error: Architect returned a malformed or empty Dossier. Aborting overwrite.")
            else:
                print("[-] Error: Architect failed to use the ===END_DOSSIER=== separator.")
        else:
            print(f"[-] API Error: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"[-] Exception during Dream Cycle: {e}")

if __name__ == "__main__":
    execute_dream_cycle()
