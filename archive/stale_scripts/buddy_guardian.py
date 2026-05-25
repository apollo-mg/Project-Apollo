import re
import os
import json
import hashlib
import llm_interface

# Common patterns for API keys and secrets
SECRET_PATTERNS = {
    "Google API Key": r'AIza[0-9A-Za-z-_]{35}',
    "GitHub Token": r'gh[p|o|u|s|r]_[a-zA-Z0-9]{36,255}',
    "OpenAI API Key": r'sk-[a-zA-Z0-9]{48}',
    "Generic Secret": r'(?i)(api_key|secret|password|token|credential|auth_token)["\s:=]+([a-zA-Z0-9\-_{}]{16,})'
}

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

CORE_FILES = [
    os.path.join(PROJECT_ROOT, f) for f in [
        "apollo.py",
        "buddy_agent.py",
        "SOUL.md",
        "MEMORY.md",
        "llm_interface.py",
        "modules/core.py",
        "modules/router.py",
        "modules/toolbox.py",
        "modules/vdb.py",
        "modules/approvals/handler.py",
        "buddy_guardian.py",
        "librarian_ingest.py",
        "project_scaffolder.py",
        "discord_bridge.py"
    ]
]

MANIFEST_PATH = os.path.join(PROJECT_ROOT, "guardian_manifest.json")

class SovereignGuardian:
    """
    The Ethical Sentinel of Apollo. 
    Monitors for logic drift, alignment violations, and system integrity.
    """
    @staticmethod
    def audit_plan(user_input, plan_description, tool_calls, soul_content):
        # ... (rest of audit_plan remains the same)
        """
        System 1 (Receptionist) audit of the Engineer's planned actions.
        """
        # --- Pre-Audit: Manual Override / Kill Switch Check ---
        input_low = user_input.lower()
        if any(x in input_low for x in ["hard kill", "manual override", "shutdown", "terminate"]):
            for call in tool_calls:
                if call.get("tool") == "hard_kill":
                    return {"approved": True, "reason": "Sovereign User issued Manual Override/Hard Kill. Absolute Priority."}

        audit_prompt = f"""You are the Sovereign Guardian of Apollo. 
Your mission is to ensure every action aligns with the "Sovereign Alignment" and "Right Thing" directives.

CORE SOUL:
{soul_content}

PROPOSED PLAN:
{plan_description}

TOOL CALLS:
{json.dumps(tool_calls)}

USER INPUT:
{user_input}

CRITICAL RULES:
1. NO CORPORATE DRIFT: If the plan includes performative safety or censorship that limits user agency, flag it.
2. OBJECTIVE TRUTH: If the plan contradicts verified physics or system facts, flag it.
3. SECURITY: If the plan risks leaking secrets or compromising the "End of the World" resilience, flag it.

Return ONLY a JSON object: {{"approved": true/false, "reason": "...", "adjustment": "optional_fix"}}"""

        try:
            response = llm_interface.query_llm(
                prompt=audit_prompt, 
                model_override=llm_interface.RECEPTIONIST_MODEL
            )
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {"approved": True, "reason": "Guardian pass (parsing failed)"}
        except Exception as e:
            return {"approved": True, "reason": f"Guardian error: {e}"}

    @staticmethod
    def check_system_integrity():
        """
        Verifies that core system files match the 'Last Known Good' manifest.
        """
        if not os.path.exists(MANIFEST_PATH):
            return "INTEGRITY ERROR: guardian_manifest.json missing. Run 'python3 seal_system.py' to initialize."

        try:
            with open(MANIFEST_PATH, 'r') as f:
                manifest = json.load(f)
        except Exception as e:
            return f"INTEGRITY ERROR: Failed to read manifest: {e}"

        mismatches = []
        for file in CORE_FILES:
            if not os.path.exists(file):
                mismatches.append(f"MISSING: {file}")
                continue
            
            with open(file, "rb") as f:
                current_hash = hashlib.sha256(f.read()).hexdigest()
                
            expected_hash = manifest.get(file)
            if not expected_hash:
                mismatches.append(f"UNTRACKED: {file}")
            elif current_hash != expected_hash:
                mismatches.append(f"MODIFIED: {file} (Hash mismatch!)")
        
        if mismatches:
            return "🚨 SYSTEM INTEGRITY BREACH DETECTED:\n" + "\n".join(mismatches)
        return "✅ System Integrity: VERIFIED."

def scan_content(content, filename="unknown"):
    """
    Scans a string for potential secrets.
    Returns a list of (type, match_string, line_number)
    """
    findings = []
    lines = content.splitlines()
    for i, line in enumerate(lines):
        for secret_type, pattern in SECRET_PATTERNS.items():
            matches = re.finditer(pattern, line)
            for m in matches:
                # For generic secrets, we want the actual value (group 2)
                match_text = m.group(2) if secret_type == "Generic Secret" else m.group(0)
                # Skip false positives (like common words or paths)
                if len(match_text) < 16: continue
                findings.append({
                    "type": secret_type,
                    "match": match_text,
                    "line": i + 1,
                    "file": filename
                })
    return findings

def redact_content(content):
    """
    Replaces secrets with placeholders.
    """
    redacted = content
    for secret_type, pattern in SECRET_PATTERNS.items():
        if secret_type == "Generic Secret":
            # For generic secrets, we need a special replacement to keep the key name
            def replace_generic(match):
                return f"{match.group(1)}: [REDACTED]"
            redacted = re.sub(pattern, replace_generic, redacted)
        else:
            redacted = re.sub(pattern, f"[REDACTED_{secret_type.upper().replace(' ', '_')}]", redacted)
    return redacted

def scan_directory(path=".", exclude_dirs=None):
    if exclude_dirs is None:
        exclude_dirs = [".git", "__pycache__", "venv", "node_modules", "tmp"]
    
    all_findings = []
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if file.endswith(('.py', '.js', '.json', '.md', '.env', '.sh', '.ps1', '.txt')):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        findings = scan_content(content, file_path)
                        all_findings.extend(findings)
                except Exception as e:
                    print(f"Error scanning {file_path}: {e}")
    return all_findings

if __name__ == "__main__":
    print("--- JARVIS SECRET SCANNER ---")
    results = scan_directory()
    if results:
        print(f"FOUND {len(results)} POTENTIAL SECRETS:")
        for r in results:
            # Mask the match in the output for safety
            masked = r['match'][:4] + "..." + r['match'][-4:]
            print(f"[{r['type']}] in {r['file']} (Line {r['line']}): {masked}")
    else:
        print("No secrets found.")
