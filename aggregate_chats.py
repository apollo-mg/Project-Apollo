import os
import json
import glob
from datetime import datetime
from collections import defaultdict

# Source directories containing the raw JSON logs
CHAT_DIRS = [
    "/home/mark/.gemini/tmp/apollo/chats/**/*.json",
    "/mnt/TG_2TB/Projects/Apollo/Dev_Log/raw/**/*.json"
]

# Output directory for the daily markdown transcripts
OUTPUT_DIR = "/mnt/TG_2TB/Projects/Apollo/data/chat_logs"

def parse_message_content(content_obj):
    """Recursively extract text from the content object."""
    if not content_obj:
        return ""
    if isinstance(content_obj, str):
        return content_obj
    if isinstance(content_obj, list):
        return "\n".join(parse_message_content(item) for item in content_obj)
    if isinstance(content_obj, dict):
        if 'text' in content_obj:
            return content_obj['text']
        if 'functionCall' in content_obj:
            func = content_obj['functionCall']
            return f"\n> **Tool Call:** `{func.get('name')}`\n> **Arguments:** `{json.dumps(func.get('args', {}))}`\n"
        if 'functionResponse' in content_obj:
            return f"\n> **Tool Response:** (Hidden for brevity)\n"
    return str(content_obj)

def parse_thoughts(thoughts_arr):
    """Stitch the fragmented thought array back into a cohesive paragraph."""
    if not thoughts_arr:
        return ""
    # Filter out empty descriptions and join them
    thought_text = "".join(t.get("description", "") for t in thoughts_arr if t.get("description"))
    if not thought_text.strip():
        return ""
    return f"\n<think>\n{thought_text}\n</think>\n"

def main():
    print(f"Scanning for chat logs...")
    json_files = []
    for pattern in CHAT_DIRS:
        json_files.extend(glob.glob(pattern, recursive=True))
    
    print(f"Found {len(json_files)} raw session files. Processing...")
    
    # Dictionary to hold messages grouped by date: { "YYYY-MM-DD": [messages_list] }
    daily_logs = defaultdict(list)
    
    for file_path in json_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            # Legacy files might use different structures, but Gemini CLI standardizes on 'messages'
            messages = data.get("messages", [])
            
            for msg in messages:
                timestamp_str = msg.get("timestamp") or data.get("startTime")
                if not timestamp_str:
                    continue
                
                # Parse date
                try:
                    # '2026-04-14T21:16:27.465Z' -> '2026-04-14'
                    date_key = timestamp_str.split("T")[0]
                except Exception:
                    date_key = "UNKNOWN_DATE"
                
                role = msg.get("type", msg.get("role", "unknown")).upper()
                
                # Extract content
                content_text = parse_message_content(msg.get("content"))
                
                # Extract thoughts
                thought_text = parse_thoughts(msg.get("thoughts", []))
                
                # Format the message
                formatted_msg = f"### [{timestamp_str}] {role}\n"
                if thought_text:
                    formatted_msg += f"{thought_text}\n"
                if content_text:
                    formatted_msg += f"{content_text}\n"
                    
                formatted_msg += "\n---\n"
                
                # Append to the correct day, including original timestamp for sorting
                daily_logs[date_key].append((timestamp_str, formatted_msg))
                
        except Exception as e:
            # Skip non-chat JSONs or malformed files
            pass

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Write to Markdown
    MAX_CHARS_PER_FILE = 50000

    for date_key, msg_tuples in daily_logs.items():
        # Sort messages chronologically by timestamp
        msg_tuples.sort(key=lambda x: x[0])
        
        current_content = ""
        chunks = []
        
        for _, msg_text in msg_tuples:
            if len(current_content) + len(msg_text) > MAX_CHARS_PER_FILE and current_content:
                chunks.append(current_content)
                current_content = msg_text
            else:
                current_content += msg_text
        if current_content:
            chunks.append(current_content)
            
        for idx, chunk_text in enumerate(chunks):
            suffix = f"_part{idx+1}" if len(chunks) > 1 else ""
            out_path = os.path.join(OUTPUT_DIR, f"{date_key}{suffix}.md")
            
            with open(out_path, "w", encoding="utf-8", errors="replace") as f:
                header = f"# Apollo Dev Diary Transcript - {date_key}"
                if len(chunks) > 1:
                    header += f" (Part {idx+1} of {len(chunks)})"
                f.write(f"{header}\n\n")
                f.write(chunk_text)
                
    print(f"Aggregation complete. Processed transcripts into daily markdown chunks in {OUTPUT_DIR}.")

if __name__ == "__main__":
    main()
