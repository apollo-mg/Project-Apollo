import os
import re

def generate_skill_index(skills_dir="/home/mark/gemini/skills"):
    """
    Scans the skills directory, extracts the top-level docstring from each file,
    and returns an OpenClaw-style index string to inject into the system context.
    """
    if not os.path.exists(skills_dir):
        return "[SKILL INDEX: Empty]"

    index_lines = ["[AVAILABLE SKILLS INDEX]"]
    
    for filename in os.listdir(skills_dir):
        if not filename.endswith(".py"):
            continue
            
        filepath = os.path.join(skills_dir, filename)
        description = "No description available."
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                
            # Look for the first block of """ or ''' docstring
            match = re.search(r'\"\"\"(.*?)\"\"\"|\'\'\'(.*?)\'\'\'', content, re.DOTALL)
            if match:
                # Group 1 is for """, Group 2 is for '''
                raw_desc = match.group(1) if match.group(1) else match.group(2)
                # Clean up whitespace and newlines for a compact index
                description = " ".join(raw_desc.strip().split())
        except Exception:
            pass
            
        index_lines.append(f"- <execute_skill>{filename}</execute_skill> : {description}")

    if len(index_lines) == 1:
        return "[SKILL INDEX: No skills forged yet.]"
        
    return "\n".join(index_lines)

if __name__ == "__main__":
    # Test it against the local mock
    os.makedirs("/data/data/com.termux/files/home/tmp_mock_skills", exist_ok=True)
    with open("/data/data/com.termux/files/home/tmp_mock_skills/skill_123.py", "w") as f:
        f.write('def foo():\n    """Checks network latency."""\n    pass')
    with open("/data/data/com.termux/files/home/tmp_mock_skills/skill_456.py", "w") as f:
        f.write('def bar():\n    """Reads GPU temperature via rocm-smi."""\n    pass')
        
    print(generate_skill_index("/data/data/com.termux/files/home/tmp_mock_skills"))
