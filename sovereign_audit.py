import os
import ast
import sys

# Core system entrypoints
ROOTS = [
    "apollo.py",
    "discord_bridge.py",
    "dynamic_canvas.py",
    "apollo_heartbeat.py",
    "buddy_agent.py"  # The main agent loop
]

IGNORE_DIRS = {
    "__pycache__", "venv", "venv_cachyos", "node_modules", "archive", "temp", 
    "llama.cpp", "whisper.cpp", "legacy_vault", "legacy_docs", ".git", ".gemini"
}

def get_all_python_files(base_dir="."):
    py_files = set()
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]
        for file in files:
            if file.endswith(".py"):
                # Normalize path to relative from base_dir without leading ./
                full_path = os.path.normpath(os.path.join(root, file))
                py_files.add(full_path)
    return py_files

def resolve_import_to_path(module_name, base_dir="."):
    # e.g. "modules.toolbox" -> "modules/toolbox.py"
    parts = module_name.split('.')
    path_as_file = os.path.join(base_dir, *parts) + ".py"
    path_as_dir_init = os.path.join(base_dir, *parts, "__init__.py")
    
    if os.path.exists(path_as_file):
        return os.path.normpath(path_as_file)
    elif os.path.exists(path_as_dir_init):
        return os.path.normpath(path_as_dir_init)
    return None

def get_imports_from_file(file_path):
    imports = set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except Exception as e:
        print(f"Warning: Could not parse {file_path}: {e}")
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
                # Also capture direct submodule imports (e.g., from modules import toolbox)
                for alias in node.names:
                    imports.add(f"{node.module}.{alias.name}")
    return imports

def build_dependency_graph():
    all_files = get_all_python_files()
    visited = set()
    queue = []
    
    # Initialize queue with roots that actually exist
    for root in ROOTS:
        if os.path.exists(root):
            queue.append(root)
            visited.add(root)
        else:
            print(f"Warning: Root entrypoint {root} not found.")

    while queue:
        current_file = queue.pop(0)
        imports = get_imports_from_file(current_file)
        
        for imp in imports:
            local_path = resolve_import_to_path(imp)
            if local_path and local_path in all_files and local_path not in visited:
                visited.add(local_path)
                queue.append(local_path)
                
    orphans = all_files - visited
    return all_files, visited, orphans

def main():
    print("=== Sovereign Audit: Architectural Drift Analysis ===")
    print(f"Roots: {', '.join(ROOTS)}\n")
    
    all_files, visited, orphans = build_dependency_graph()
    
    print(f"Total Python Files Scanned: {len(all_files)}")
    print(f"Active Files in Dependency Tree: {len(visited)}")
    print(f"Orphaned/Ghost Files: {len(orphans)}\n")
    
    print("--- ACTIVE DEPENDENCIES ---")
    for f in sorted(visited):
        print(f" [+] {f}")
        
    print("\n--- ORPHANED FILES (Standalone Scripts or Ghost Code) ---")
    for f in sorted(orphans):
        print(f" [?] {f}")

if __name__ == "__main__":
    main()