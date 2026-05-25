import os
import json
from datetime import datetime, timedelta

def format_content(content):
    if isinstance(content, str):
        return content.strip()
    elif isinstance(content, list):
        out = []
        for part in content:
            if "text" in part:
                out.append(part["text"].strip())
            elif "functionCall" in part:
                fc = part["functionCall"]
                out.append(f"**[Tool Call: {fc.get('name', 'unknown')}]**: {json.dumps(fc.get('args', {}))}")
            elif "functionResponse" in part:
                fr = part["functionResponse"]
                out.append(f"**[Tool Response: {fr.get('name', 'unknown')}]**\n```json\n{json.dumps(fr.get('response', {}), indent=2)[:1000]}...\n```")
            else:
                out.append(f"[Unknown Part: {json.dumps(part)[:100]}]")
        return "\n".join(out)
    return str(content)

def main():
    chat_dir = "/home/mark/.gemini/tmp/apollo/chats/"
    output_file = "/mnt/TG_2TB/Projects/Apollo/gemini_48h_transcript.md"
    
    now = datetime(2026, 4, 2, 23, 59, 59)
    cutoff = now - timedelta(hours=72)
    
    sessions = []
    
    for filename in os.listdir(chat_dir):
        if filename.endswith(".json") and filename.startswith("session-"):
            filepath = os.path.join(chat_dir, filename)
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    start_time = data.get("startTime", "")
                    if not start_time:
                        continue
                    dt = datetime.fromisoformat(start_time.replace("Z", "+00:00")).replace(tzinfo=None)
                    
                    if dt >= cutoff:
                        sessions.append((dt, data))
            except Exception as e:
                print(f"Failed to read {filename}: {e}")
                
    sessions.sort(key=lambda x: x[0])
    
    with open(output_file, "w") as out_f:
        out_f.write("# Gemini CLI 48-Hour Transcript\n\n")
        
        for dt, data in sessions:
            out_f.write(f"## Session ID: {data.get('sessionId', 'Unknown')} - Start Time: {dt.isoformat()}\n\n")
            messages = data.get("messages", [])
            for msg in messages:
                role = msg.get("type", "unknown").capitalize()
                raw_content = msg.get("content", "")
                content_str = format_content(raw_content)
                out_f.write(f"### {role}:\n{content_str}\n\n")
            out_f.write("---\n\n")
            
    print(f"Exported {len(sessions)} sessions to {output_file}")

if __name__ == "__main__":
    main()
