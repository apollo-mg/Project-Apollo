import os
import subprocess
import datetime
from google import genai
from google.genai import types

def get_recent_files():
    # Get the 5 most recently modified files (excluding logs, images, and .git)
    cmd = "find /mnt/TG_2TB/Projects/Apollo -type f -not -path '*/\.git/*' -not -path '*/__pycache__/*' -not -name '*.log' -not -name '*.jpg' -not -name '*.png' -not -path '*/archive/*' -printf '%T@ %p\\n' | sort -n | tail -5 | cut -f2- -d\" \""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip()

def get_recent_commits():
    # If using git, this gets the last 3 commits. If not, it fails gracefully.
    try:
        cmd = "cd /mnt/TG_2TB/Projects/Apollo && git log -3 --oneline"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip()
    except:
        return "Git not initialized or no commits."

def generate_log():
    # Initialize the new Gemini SDK client
    client = genai.Client()
    
    date_str = datetime.datetime.now().strftime("%A, %B %d, %Y")
    recent_files = get_recent_files()
    
    # Read core context
    with open('/mnt/TG_2TB/Projects/Apollo/ROADMAP.md', 'r') as f:
        roadmap = f.read()[:2000] # Just the top section
        
    prompt = f"""
    You are an automated technical writer for the "Sovereign Engine" project.
    Your job is to write a concise, highly technical Dev Log entry for today ({date_str}).
    
    Context:
    Recently modified files:
    {recent_files}
    
    Current Project Roadmap Context (Top section):
    {roadmap}
    
    Based on the fact that we just did a massive clean-up of the root directory, archived over 40 old test files and legacy Windows scripts, and consolidated the 'Gemini/History/Vault' into 'legacy_vault/', write a dev log entry.
    
    Format requirements:
    1. Start with a Date Header (## {date_str})
    2. Add a '### 🛠️ Execution Summary' section detailing the cleanup.
    3. Add a '### 🔭 Strategic Impact' section explaining how this helps the LLM context window and prepares the project for automated workflows.
    4. Keep it professional, cyberpunk-themed (Sovereign Engine aesthetic), and no longer than 3 paragraphs.
    """

    print("Generating Dev Log with gemini-3-flash-preview...")
    
    response = client.models.generate_content(
        model='gemini-3-flash-preview',
        contents=prompt,
    )
    
    log_path = "/mnt/TG_2TB/Projects/Apollo/Dev_Log/SOVEREIGN_CHRONICLE.md"
    
    # Append to the chronicle
    with open(log_path, 'a') as f:
        f.write("\n\n" + response.text + "\n")
        
    print(f"Successfully appended to {log_path}!")

if __name__ == "__main__":
    generate_log()
