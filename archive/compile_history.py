import os
import json
import glob
from datetime import datetime

# Define directories to search
SEARCH_DIRS = [
    "/home/mark/.gemini/chats",
    "/home/mark/.gemini/history",
    "/home/mark/.gemini/tmp",
    "/mnt/TG_2TB/Projects/Apollo"
]

OUTPUT_FILE = "/mnt/TG_2TB/Projects/Apollo/Dev_Log/Apollo_Chat_History.txt"

def get_json_files():
    files = []
    for d in SEARCH_DIRS:
        # Search for session-*.json and anything matching gemini-conversation
        for root, _, filenames in os.walk(d):
            for filename in filenames:
                if (filename.startswith("session-") or filename.startswith("gemini-conversation")) and filename.endswith(".json"):
                    files.append(os.path.join(root, filename))
    return list(set(files)) # Unique files only

def extract_content(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        messages = data.get("messages", [])
        if not messages:
            return None
            
        output = []
        for msg in messages:
            role = msg.get("role", "unknown")
            text = ""
            
            # The structure of these JSONs can vary (v1 vs v2 schema)
            if "content" in msg and isinstance(msg["content"], str):
                text = msg["content"]
            elif "parts" in msg: # Gemini API schema
                for part in msg["parts"]:
                    if "text" in part:
                        text += part["text"] + "\n"
                        
            if text.strip():
                # Truncate extremely long code dumps
                lines = text.strip().split("\n")
                if len(lines) > 50:
                    text = "\n".join(lines[:20]) + "\n[... truncated long code/log block ...]\n" + "\n".join(lines[-10:])
                
                output.append(f"[{role.upper()}]: {text.strip()}")
                
        return "\n\n".join(output)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None

def main():
    print("Gathering chat history files...")
    files = get_json_files()
    print(f"Found {len(files)} chat log files.")
    
    # Sort files by modification time (oldest first)
    files.sort(key=os.path.getmtime)
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out_f:
        out_f.write("========================================================================\n")
        out_f.write("                    PROJECT APOLLO CHAT HISTORY TIMELINE\n")
        out_f.write("========================================================================\n\n")
        
        processed = 0
        for f in files:
            content = extract_content(f)
            if content:
                # Get the date from the file
                mod_time = os.path.getmtime(f)
                date_str = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
                
                out_f.write(f"\n\n================ DATE: {date_str} ====================\n")
                out_f.write(f"FILE: {os.path.basename(f)}\n")
                out_f.write("========================================================================\n")
                out_f.write(content)
                processed += 1
                
        print(f"Successfully processed {processed} valid chat sessions.")
        print(f"Combined history written to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
