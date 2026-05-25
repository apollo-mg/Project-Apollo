import os
import re
import subprocess
import time

def parse_and_execute_project_tags(text, base_dir="/home/mark/gemini/projects"):
    """
    Parses <execute_shell> and <write_file> tags to allow the agent to build complex projects.
    """
    results = []
    
    # 1. Parse Shell Commands
    shell_actions = re.findall(r'<execute_shell>\s*(.*?)\s*</execute_shell>', text, re.IGNORECASE | re.DOTALL)
    for cmd in shell_actions:
        print(f"[Scaffolder] Executing Shell: {cmd}")
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=base_dir)
            out = res.stdout.strip() or res.stderr.strip()
            results.append(f"[SHELL RESULT: {cmd}] -> {out}")
        except Exception as e:
            results.append(f"[SHELL ERROR: {cmd}] -> {e}")

    # 2. Parse File Writing
    # Format: <write_file path="relative/path/to/file.py">...content...</write_file>
    file_actions = re.findall(r'<write_file\s+path="([^"]+)">\s*(.*?)\s*</write_file>', text, re.IGNORECASE | re.DOTALL)
    for file_path, content in file_actions:
        full_path = os.path.join(base_dir, file_path)
        print(f"[Scaffolder] Writing File: {full_path}")
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            results.append(f"[FILE WRITTEN: {file_path}] -> Success")
        except Exception as e:
            results.append(f"[FILE ERROR: {file_path}] -> {e}")

    return results

if __name__ == "__main__":
    # Test Payload
    test_payload = """
    I am setting up the backend API. First, I will create the directory structure.
    <execute_shell>mkdir -p api/routes api/models</execute_shell>
    
    Now I will write the main entry point.
    <write_file path="api/main.py">
from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "ok"}
    </write_file>
    """
    
    os.makedirs("/data/data/com.termux/files/home/tmp_test_projects", exist_ok=True)
    res = parse_and_execute_project_tags(test_payload, base_dir="/data/data/com.termux/files/home/tmp_test_projects")
    print("\nResults:")
    for r in res:
        print(r)
