#!/usr/bin/env python3
"""
Deep Sleep Triage
The final reconciliation phase of the Sovereign Engine.
Reads the daily 'Tick Spool', performs Simple Self-Distillation (SSD) via the LLM,
archives the findings to the training dataset, and wipes the short-term memory spool.
"""

import os
import glob
import json
import time
import datetime
from llm_interface import query_llm

SPOOL_DIR = "/mnt/TG_2TB/Projects/Apollo/data/daydream_spool"
TRAINING_DATASET = "/mnt/TG_2TB/Projects/Apollo/v8_memory_dataset.jsonl"
ARCHIVE_LOG = "/mnt/TG_2TB/Projects/Apollo/BACKGROUND_TASKS.md"

def gather_spool_data():
    files = glob.glob(os.path.join(SPOOL_DIR, "*.md"))
    if not files:
        return None
    
    raw_data = ""
    for f in files:
        try:
            with open(f, "r") as file:
                raw_data += f"\n\n--- [Spool Entry: {os.path.basename(f)}] ---\n"
                raw_data += file.read()
        except Exception as e:
            print(f"Failed to read {f}: {e}")
    return raw_data, files

def synthesize_memory(raw_spool_data):
    system_prompt = """You are the Sovereign Engine in 'Deep Sleep' (REM) reconciliation mode.
You have been provided with the raw 'Tick Spool'—a collection of independent tasks, audits, and code fixes you performed throughout the day.
Your objective is to perform Simple Self-Distillation (SSD).
1. Review the independent tasks.
2. Identify the 3 most critical architectural lessons or successfully executed code/bash solutions.
3. Synthesize them into a highly concise JSON object. Do not include markdown formatting like ```json.

Output Format:
{
  "daily_synthesis": "A 2-3 sentence overview of the day's progress.",
  "core_lessons": [
    "Lesson 1",
    "Lesson 2",
    "Lesson 3"
  ],
  "training_pairs": [
    {"instruction": "Example task that was successfully completed today", "output": "The exact successful bash or python code you used"}
  ]
}
"""
    
    print("[*] Initiating Deep Sleep LLM Synthesis...")
    response = query_llm(prompt=raw_spool_data, system_message=system_prompt, max_tokens=1024)
    
    clean_resp = response.replace("```json", "").replace("```", "").strip()
    
    try:
        return json.loads(clean_resp)
    except json.JSONDecodeError:
        print("[!] LLM failed to return valid JSON during Deep Sleep.")
        print(f"Raw Output: {clean_resp[:200]}...")
        return None

def execute_deep_sleep():
    print("💤 Entering Deep Sleep Reconciliation...")
    
    raw_data, spool_files = gather_spool_data()
    
    if not raw_data:
        print("[*] No tick spools found today. Resuming operations.")
        return
        
    print(f"[*] Found {len(spool_files)} tick(s) in spool. Synthesizing...")
    
    synthesis = synthesize_memory(raw_data)
    
    if synthesis:
        # 1. Append to Training Dataset
        print("[*] Writing successful training pairs to v8_memory_dataset.jsonl")
        with open(TRAINING_DATASET, "a") as f:
            for pair in synthesis.get("training_pairs", []):
                # Ensure it matches the chatml or instruction format needed for training
                json_line = json.dumps({"messages": [
                    {"role": "user", "content": pair.get("instruction", "")},
                    {"role": "assistant", "content": pair.get("output", "")}
                ]})
                f.write(json_line + "\n")
                
        # 2. Append the high-level summary to the daily log
        print("[*] Appending daily synthesis to BACKGROUND_TASKS.md")
        with open(ARCHIVE_LOG, "a") as f:
            f.write(f"\n\n## 💤 Deep Sleep Cycle: {datetime.datetime.now().strftime('%Y-%m-%d')}\n")
            f.write(f"**Synthesis:** {synthesis.get('daily_synthesis', '')}\n")
            for lesson in synthesis.get("core_lessons", []):
                f.write(f"- {lesson}\n")
                
        # 3. Wipe the Spool (The Wake Up)
        print("[*] Wiping Tick Spool...")
        for f in spool_files:
            os.remove(f)
            
        print("🌅 Deep Sleep complete. Spool cleared.")
    else:
        print("[!] Synthesis failed. Spool preserved for manual review.")

if __name__ == "__main__":
    execute_deep_sleep()
