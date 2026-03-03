import os
import sys
import subprocess
import json
import re
import datetime

# Setup paths
SOURCE_DIR = "/home/mark/gemini/"
DEST_DIR = "/home/mark/apollo_share_dist/"

# Add DEST_DIR to path so we can use its llm_interface natively
sys.path.append(DEST_DIR)
import llm_interface

def sync_files():
    print("--- [1/4] SYNCING FILES ---")
    # We use rsync to cleanly copy Python scripts and MD files to the repo, 
    # while ignoring transient files, logs, and venvs.
    rsync_cmd = [
        "rsync", "-av", "--update",
        "--exclude=gemini-conversation*.json",
        "--include=*.py", "--include=*.md", "--include=*.json",
        "--exclude=tmp/", "--exclude=venv_apollo/", "--exclude=__pycache__/", 
        "--exclude=*.log", "--exclude=.git/", "--exclude=.env", "--exclude=personal/",
        "--exclude=vault/", "--exclude=whisper.cpp/", "--exclude=*.deb", "--exclude=*.jpg",
        SOURCE_DIR, DEST_DIR
    ]
    subprocess.run(rsync_cmd, check=True)
    print("Sync complete.")

def analyze_and_commit():
    print("--- [2/4] STAGING CHANGES ---")
    os.chdir(DEST_DIR)
    subprocess.run(["git", "add", "."], check=True)
    
    # Get the diff of what is about to be committed
    diff_process = subprocess.run(["git", "diff", "--staged"], capture_output=True, text=True)
    diff_output = diff_process.stdout
    
    if not diff_output.strip():
        print("No changes to commit.")
        return

    print("--- [3/4] AI CODE REVIEW & COMMIT GENERATION ---")
    
    sys_prompt = (
        "You are the Apollo Architect (qwen3-coder:30b). You are reviewing a git diff before it is pushed to GitHub.\n"
        "TASK 1: Security Audit. Check for any exposed secrets, API keys, discord tokens, or severe syntax errors.\n"
        "TASK 2: Commit Message. Generate a concise, semantic commit message (e.g., 'feat: add multi-image support').\n"
        "TASK 3: Changelog. Generate a 1-2 sentence changelog entry explaining the core intent behind the change.\n"
        "OUTPUT FORMAT (Strict JSON):\n"
        "{\n"
        "  \"security_alert\": \"<Describe issue if any, otherwise output 'none'>\",\n"
        "  \"commit_message\": \"<message>\",\n"
        "  \"changelog_entry\": \"<entry>\"\n"
        "}"
    )
    
    # Truncate diff to ~10,000 chars to avoid blowing out the context window if it's a massive update
    prompt = f"Here is the staged git diff:\n```diff\n{diff_output[:10000]}\n```"
    
    print(f"Calling Architect Model ({llm_interface.ARCHITECT_MODEL})...")
    
    # Force loading of the 30B model for accurate coding logic
    response = llm_interface.query_llm(prompt, system_message=sys_prompt, model_override=llm_interface.ARCHITECT_MODEL)
    
    json_target = response.split("</think>")[-1] if "</think>" in response else response
    m = re.search(r'\{.*\}', json_target, re.DOTALL)
    
    if not m:
        print(f"Failed to parse AI response. Raw output:\n{response}")
        return
        
    try:
        data = json.loads(m.group(0))
        
        # 1. Check Security
        if data.get("security_alert") and data.get("security_alert").lower() != "none":
            print(f"\n[!] SECURITY OR SYNTAX ALERT [!]")
            print(f"Architect found an issue: {data['security_alert']}")
            print("\nAborting commit. Please fix the issues and try again.")
            subprocess.run(["git", "reset"], check=True) # unstage
            return
            
        commit_msg = data.get("commit_message", "Update Apollo systems")
        changelog_entry = data.get("changelog_entry", "- Routine system updates.")
        
        # 2. Update Changelog
        changelog_path = os.path.join(DEST_DIR, "CHANGELOG.md")
        if os.path.exists(changelog_path):
            with open(changelog_path, "r") as f:
                cl = f.read()
        else:
            cl = "# Project Apollo Changelog\n\n"
            
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # Insert right below the header
        if "## " in cl:
            # Add to existing log
            new_cl = cl.replace("# Project Apollo Changelog\n\n", f"# Project Apollo Changelog\n\n## {date_str}\n- {changelog_entry}\n\n")
        else:
            new_cl = f"# Project Apollo Changelog\n\n## {date_str}\n- {changelog_entry}\n\n{cl}"
            
        with open(changelog_path, "w") as f:
            f.write(new_cl)
            
        subprocess.run(["git", "add", "CHANGELOG.md"], check=True)
        
        # 3. Execute Commit
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        print(f"\n[+] Successfully Committed: {commit_msg}")
        print(f"[+] Changelog Updated: {changelog_entry}")
        
        # 4. Push
        print("\n--- [4/4] PUSHING TO GITHUB ---")
        subprocess.run(["git", "push"], check=True)
        print("\n[SUCCESS] Apollo core synchronized and secured in the Vault.")
        
    except Exception as e:
        print(f"Error processing commit: {e}")
        subprocess.run(["git", "reset"], check=True)

if __name__ == "__main__":
    sync_files()
    analyze_and_commit()