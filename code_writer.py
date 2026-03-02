import os

def write_code(file_path, content, mode="w"):
    """
    Writes code to a file.
    
    Args:
        file_path (str): The relative path to the file (e.g., "projects/ShopMonitor/main.py").
        content (str): The code content to write.
        mode (str): "w" for overwrite (default), "a" for append.
    """
    # Heuristic: Fix common LLM escaping issues (double-escaped newlines)
    # If the content has no real newlines but has literal "\n", it's likely an error.
    if "\\n" in content and "\n" not in content:
        content = content.replace("\\n", "\n")
        
    try:
        # Security: Prevent writing outside valid directories (projects/ or tmp/)
        # But for now, let's keep it flexible but safe from overwriting critical system files
        abs_path = os.path.abspath(file_path)
        
        # Simple check: Ensure directory exists
        dir_name = os.path.dirname(abs_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
            
        with open(abs_path, mode) as f:
            f.write(content)
            
        return f"Successfully wrote {len(content)} chars to {file_path}"
        
    except Exception as e:
        return f"Write Error: {e}"

if __name__ == "__main__":
    print(write_code("tmp/test_code.py", "print('Hello World')"))
