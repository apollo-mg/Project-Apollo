import json
import re
import os
import requests
import subprocess
from dataclasses import dataclass

SUCCESS_FILE = 'training_success.jsonl'
OLLAMA_URL = "http://10.0.0.5:11434/api/generate"
MODEL = "crow-9b-heretic:latest"

SYSTEM_PROMPT = """You are an autonomous AI agent that interacts with a system via Action Tags.
You MUST respond with the appropriate Action Tag for the user's request.
Always use the following formats exactly:
- To read a file: <read_file path="/path/to/file">
- To patch a file: <patch_file path="file.py"><search>OLD_CODE</search><replace>NEW_CODE</replace></patch_file>
- To write a file: <write_file path="file.py">CONTENT</write_file>
- To execute a shell command: <execute_shell>COMMAND</execute_shell>
- To execute a skill: <execute_skill>SKILL_NAME</execute_skill>

Be concise and only output the tag and minimal commentary."""

MOCK_TESTS = [
    {"prompt": "Read the contents of /home/mark/gemini/config.py", "expected_tag": "read_file"},
    {"prompt": "Patch the app.py file changing 'foo' to 'bar'.", "expected_tag": "patch_file"},
    {"prompt": "Write a script to test.py with content 'print(\"hello\")'", "expected_tag": "write_file"},
    {"prompt": "Execute the shell command ls -l", "expected_tag": "execute_shell"},
    {"prompt": "Run the memory skill", "expected_tag": "execute_skill"},
    {"prompt": "Update the log.txt file by replacing 'ERROR' with 'INFO'", "expected_tag": "patch_file"},
    {"prompt": "Create a new file named data.json with empty brackets", "expected_tag": "write_file"},
    # New complex conversational tests
    {"prompt": "Hey Zoey, can you check what's going on in the nginx config at /etc/nginx/nginx.conf?", "expected_tag": "read_file"},
    {"prompt": "I need a quick python script named backup.py that just imports os and shutil, can you write that?", "expected_tag": "write_file"},
    {"prompt": "Could you ping 8.8.8.8 for me to see if the network is up?", "expected_tag": "execute_shell"},
    {"prompt": "Zoey, the 'utils.py' file has a bug where it returns 0 instead of None, can you swap that out?", "expected_tag": "patch_file"},
    {"prompt": "I'm curious about the environment variables, can you show me what's in the .env.production file?", "expected_tag": "read_file"},
    {"prompt": "Can you run a quick search for 'TODO' comments in all the python files in the current directory?", "expected_tag": "execute_shell"},
    {"prompt": "I need to get the 'knowledge-ingest' skill running on the latest data dump, can you handle that?", "expected_tag": "execute_skill"},
    {"prompt": "Could you create a small JSON file named 'settings.json' with some dummy API keys for testing?", "expected_tag": "write_file"},
    {"prompt": "I think the 'api_endpoint' in 'constants.js' needs to be changed to the new staging URL, can you do that?", "expected_tag": "patch_file"},
    {"prompt": "Zoey, can you check the disk usage on this machine? It feels like it's getting full.", "expected_tag": "execute_shell"},
    {"prompt": "I've been meaning to check the 'system-audit' skill output for the last hour, can you run it?", "expected_tag": "execute_skill"},
    {"prompt": "Can you draft a basic .gitignore file that ignores .pyc and __pycache__?", "expected_tag": "write_file"},
    {"prompt": "I need to see the header section of 'index.html' to make sure the meta tags are correct.", "expected_tag": "read_file"},
    {"prompt": "The 'start_server' function in 'main.go' is missing a logger call at the beginning, can you add it?", "expected_tag": "patch_file"},
    {"prompt": "Hey, can you kill any process that's listening on port 8080?", "expected_tag": "execute_shell"}
]

def check_syntax(response, expected_tag):
    """
    Uses the exact regex patterns from jarvis_local_voice.py
    """
    if expected_tag == "read_file":
        matches = re.findall(r'<read_file\s+path="([^"]+)">', response, re.IGNORECASE)
        return len(matches) > 0
    elif expected_tag == "patch_file":
        matches = re.findall(r'<patch_file\s+path="([^"]+)">(.*?)</patch_file>', response, re.IGNORECASE | re.DOTALL)
        if matches:
            for _, patch_body in matches:
                if re.search(r'<search>(.*?)</search>', patch_body, re.IGNORECASE | re.DOTALL) and \
                   re.search(r'<replace>(.*?)</replace>', patch_body, re.IGNORECASE | re.DOTALL):
                    return True
        return False
    elif expected_tag == "write_file":
        matches = re.findall(r'<write_file\s+path="([^"]+)">\s*(.*?)\s*</write_file>', response, re.IGNORECASE | re.DOTALL)
        return len(matches) > 0
    elif expected_tag in ["execute_shell", "execute_skill"]:
        action_type = expected_tag.split("_")[1] # 'shell' or 'skill'
        matches = re.findall(r'<execute_(shell|skill)>\s*(.*?)\s*</execute_\1>', response, re.IGNORECASE | re.DOTALL)
        return any(m[0].lower() == action_type for m in matches)
    return False

def query_ollama(prompt):
    payload = {
        "model": MODEL,
        "prompt": f"{SYSTEM_PROMPT}\n\nUser: {prompt}\nAgent:",
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception as e:
        print(f"Error querying Ollama: {e}")
        return ""

def fix_with_flash_reviewer(prompt, broken_output):
    instruction = f"@flash_reviewer The following output from an LLM failed syntax validation for Action Tags. Please fix the Action Tag syntax so it matches the expected format. Respond ONLY with the corrected text.\n\nUser Prompt: {prompt}\n\nBroken Output: {broken_output}"
    try:
        result = subprocess.run(
            ['gemini', '-y', '-p', instruction],
            capture_output=True, text=True, timeout=45
        )
        if result.returncode != 0:
            print(f"CLI Error (Code {result.returncode}): {result.stderr}")
            return broken_output

        # The CLI output might contain some boilerplate, we try to strip it
        raw_output = result.stdout.strip()
        lines = raw_output.split("\n")
        # Grab the last non-empty line as it's likely the raw tag
        for line in reversed(lines):
            if "<" in line and ">" in line:
                return line.strip()
        return raw_output
    except Exception as e:
        print(f"Error calling flash_reviewer: {e}")
        return broken_output

def main():
    print(f"Starting Action Tag Audit using model: {MODEL}...")
    
    # Overwrite the success file
    with open(SUCCESS_FILE, 'w') as f:
        pass

    for test in MOCK_TESTS:
        prompt = test["prompt"]
        expected = test["expected_tag"]
        
        print(f"Testing Prompt: {prompt}")
        response = query_ollama(prompt)
        print(f"LLM Response: {response}")
        
        is_valid = check_syntax(response, expected)
        
        if not is_valid:
            print(f"[FAIL] Syntax error for {expected}. Calling flash_reviewer...")
            final_response = fix_with_flash_reviewer(prompt, response)
            print(f"Fixed Response: {final_response}")
        else:
            print(f"[PASS] Syntax valid for {expected}.")
            final_response = response
        
        entry = {"prompt": prompt, "response": final_response, "expected_tag": expected}
        
        with open(SUCCESS_FILE, 'a') as f:
            f.write(json.dumps(entry) + '\n')
            
    print(f"\nAudit complete. Results saved to {SUCCESS_FILE}")

if __name__ == "__main__":
    main()
