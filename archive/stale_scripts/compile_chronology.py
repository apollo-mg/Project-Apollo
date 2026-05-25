#!/usr/bin/env python3
import os
import glob

# Configuration
DIARIES_DIR = "/mnt/TG_2TB/Projects/Apollo/data/dev_diaries"
OUTPUT_FILE = "/mnt/TG_2TB/Projects/Apollo/APOLLO_CHRONOLOGY.md"

def compile_chronology():
    print(f"[*] Scanning for Dev Diaries in {DIARIES_DIR}...")
    files = sorted(glob.glob(os.path.join(DIARIES_DIR, "*_diary.md")))
    
    if not files:
        print("[!] No dev diaries found. Run generate_diary.py first.")
        return
        
    print(f"[*] Found {len(files)} diaries. Compiling into Master Chronology...")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        out.write("# Sovereign Engine (Project Apollo) - Master Chronology\n\n")
        out.write("> This document is a chronological concatenation of all daily Dev Diaries. It serves as the master historical context file for the Sovereign Architecture.\n\n")
        out.write("---\n\n")
        
        for file_path in files:
            date_str = os.path.basename(file_path).replace("_diary.md", "")
            
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            
            out.write(f"## {date_str}\n\n")
            out.write(content)
            out.write("\n\n---\n\n")
            
    print(f"[+] Successfully compiled {len(files)} diaries into: {OUTPUT_FILE}")
    print("[*] This file is now ready to be ingested as a system prompt or RAG context!")

if __name__ == "__main__":
    compile_chronology()
