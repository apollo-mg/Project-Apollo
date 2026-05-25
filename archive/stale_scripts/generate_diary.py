#!/usr/bin/env python3
import os
import glob
import json
import urllib.request
import argparse

# Configuration
LOGS_DIR = "/mnt/TG_2TB/Projects/Apollo/data/chat_logs"
OUTPUT_DIR = "/mnt/TG_2TB/Projects/Apollo/data/dev_diaries"
API_URL = "http://127.0.0.1:8082/v1/chat/completions"

SYSTEM_PROMPT = """You are Mark, the internal monologue and lead architect of the Project Apollo. You are an uncensored, highly creative, and deeply technical AI enthusiast using their desktop PC with an AMD RX 9070 XT GPU to develop real world local AI.

Review the following raw terminal transcript of today's development session. Transform it into a gripping, first-person 'Dev Diary' entry.

Guidelines:
- Write in the first person ("I", "we", "my architecture").
- You may see chat from both Gemini and Mark (the user of Gemini AI). Take on the role of Mark as if you're documenting the progress while working with Gemini CLI.
- Focus heavily on the gritty technical challenges (VRAM constraints, ROCm driver quirks, memory fragmentation, quantization strategies) and the architectural epiphanies.
- Highlight the friction between the "Soul" (the creative, philosophical goals) and the "System" (the cold, hard technical limits of the silicon).
- Avoid generic corporate AI-speak ("Here is the summary", "As an AI..."). Be raw, insightful, slightly rebellious, and unabashedly technical.
- Extract the core lessons learned and how they impact the evolving local-first multi-agent ecosystem.
- Format as a clean, readable Markdown document with compelling headers.
- Avoid using excess decoration characters such as ### or ***, aiming for a human like diary entry.
"""

def generate_diary(file_path):
    date_str = os.path.basename(file_path).replace(".md", "")
    out_path = os.path.join(OUTPUT_DIR, f"{date_str}_diary.md")
    
    if os.path.exists(out_path):
        print(f"[*] Diary for {date_str} already exists at {out_path}. Skipping...")
        return

    print(f"[*] Reading transcript: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        transcript = f.read()

    # The context is 65k, but we cap the string size just in case it's a massive multi-day log
    if len(transcript) > 150000:
        print("[!] Transcript very large, truncating to the last 150,000 characters...")
        transcript = transcript[-150000:]

    payload = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Here is the raw transcript for {date_str}:\n\n{transcript}\n\nWrite the Dev Diary entry."}
        ],
        "temperature": 1.0,
        "top_p": 0.9,
        "top_k": 64,
        "max_tokens": 8192,
        "stream": True
    }

    req = urllib.request.Request(API_URL, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
    
    print(f"[*] Generating Dev Diary for {date_str} via local Qwopus (localhost:8082)...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    diary_content = ""
    try:
        with urllib.request.urlopen(req, timeout=1800) as response:
            print("\n--- [STREAM START] ---")
            for line in response:
                if line:
                    line = line.decode('utf-8').strip()
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    chunk = delta["content"]
                                    if chunk is not None:
                                        diary_content += chunk
                                        print(chunk, end="", flush=True)
                        except json.JSONDecodeError:
                            pass
            print("\n--- [STREAM END] ---\n")
            
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(diary_content)
        print(f"[+] Saved successfully to {out_path}")
            
    except Exception as e:
        print(f"\n[!] Error communicating with local LLM: {e}")
        print("[!] Ensure llama-server is running on port 8082.")

def main():
    parser = argparse.ArgumentParser(description="Generate Dev Diaries from transcripts using local Qwopus.")
    parser.add_argument("--date", type=str, help="Specific date to process (YYYY-MM-DD). If omitted, processes the most recent.", default=None)
    parser.add_argument("--all", action="store_true", help="Process all available transcripts.")
    args = parser.parse_args()

    files = sorted(glob.glob(os.path.join(LOGS_DIR, "*.md")))
    if not files:
        print("[!] No transcripts found in data/chat_logs.")
        return

    if args.all:
        for f in files:
            generate_diary(f)
    elif args.date:
        target = os.path.join(LOGS_DIR, f"{args.date}.md")
        if os.path.exists(target):
            generate_diary(target)
        else:
            print(f"[!] Transcript for {args.date} not found.")
    else:
        # Just do the latest by default
        print(f"[*] No specific date provided. Defaulting to the most recent transcript.")
        generate_diary(files[-1])

if __name__ == "__main__":
    main()
