import os
import subprocess

PROJECTS_ROOT = "projects"

TEMPLATES = {
    "python": {
        "gitignore": """__pycache__/
*.pyc
.env
venv/
.DS_Store""",
        "entry_point": "main.py",
        "entry_content": """def main():
    print('Hello from {name}!')

if __name__ == '__main__':
    main()"""
    },
    "web": {
        "gitignore": """node_modules/
.env
dist/
.DS_Store""",
        "entry_point": "index.html",
        "entry_content": """<!DOCTYPE html>
<html>
<head>
    <title>{name}</title>
</head>
<body>
    <h1>{name}</h1>
    <p>Project initialized.</p>
</body>
</html>"""
    },
    "arduino": {
        "gitignore": """build/
.DS_Store""",
        "entry_point": "{name}.ino",
        "entry_content": """void setup() {{
  // Put your setup code here, to run once:
  Serial.begin(9600);
  Serial.println("{name} initialized");
}}

void loop() {{
  // Put your main code here, to run repeatedly:
}}"""
    },
    "rust": {
        "gitignore": """target/
Cargo.lock
**/*.rs.bk
.DS_Store""",
        "entry_point": "Cargo.toml",
        "entry_content": """[package]
name = "{safe_name}"
version = "0.1.0"
edition = "2021"

[dependencies]
"""
    },
    "node": {
        "gitignore": """node_modules/
.env
npm-debug.log
.DS_Store""",
        "entry_point": "package.json",
        "entry_content": """{{
  "name": "{safe_name}",
  "version": "1.0.0",
  "description": "",
  "main": "index.js",
  "scripts": {{
    "test": "echo \\"Error: no test specified\\" && exit 1"
  }},
  "author": "",
  "license": "ISC"
}}"""
    }
}

def scaffold_project(name, project_type="python"):
    """
    Creates a new project directory with basic boilerplate and initializes a Git repo.
    """
    # Sanitize name
    safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_').lower()
    project_dir = os.path.join(PROJECTS_ROOT, safe_name)
    
    if os.path.exists(project_dir):
        return f"Error: Project directory '{project_dir}' already exists."
    
    try:
        os.makedirs(project_dir)
        
        # Get template or default to python
        template = TEMPLATES.get(project_type.lower(), TEMPLATES["python"])
        
        # 1. Create README.md
        with open(os.path.join(project_dir, "README.md"), "w") as f:
            f.write(f"# {name}\n\nInitialized: {project_type}\n\n## Description\nTODO: Add description.")
            
        # 2. Create .gitignore
        with open(os.path.join(project_dir, ".gitignore"), "w") as f:
            f.write(template["gitignore"])
            
        # 3. Create Entry Point
        entry_file = template["entry_point"].format(name=safe_name)
        
        # For Rust, we need src/main.rs too
        if project_type.lower() == "rust":
            os.makedirs(os.path.join(project_dir, "src"), exist_ok=True)
            with open(os.path.join(project_dir, "src", "main.rs"), "w") as f:
                f.write("fn main() {\n    println!(\"Hello from " + name + "!\");\n}")
        
        # For Node, we might want an index.js
        if project_type.lower() == "node":
            with open(os.path.join(project_dir, "index.js"), "w") as f:
                f.write(f"console.log('Hello from {name}!');")

        entry_content = template["entry_content"].format(name=name, safe_name=safe_name)
        
        with open(os.path.join(project_dir, entry_file), "w") as f:
            f.write(entry_content)
            
        # 4. Initialize Git
        try:
            subprocess.run(["git", "init"], cwd=project_dir, capture_output=True, check=True)
            subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit from Apollo Scaffolder"], cwd=project_dir, capture_output=True, check=True)
            git_status = "and initialized Git repository."
        except Exception as ge:
            git_status = f"but Git initialization failed: {ge}"
            
        return f"Project '{name}' created at {project_dir} (Type: {project_type}) {git_status}"
        
    except Exception as e:
        return f"Scaffold Error: {e}"

if __name__ == "__main__":
    # Test
    print(scaffold_project("Rust Test", "rust"))
