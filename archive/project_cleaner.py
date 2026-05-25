import os
import ast
import shutil

ROOTS = [
    "apollo.py",
    "discord_bridge.py",
    "dynamic_canvas.py",
    "apollo_heartbeat.py",
    "buddy_agent.py",
    "wake_up.py",          # Standalone voice trigger
    "sovereign_audit.py"   # The audit tool itself
]

IGNORE_DIRS = {
    "__pycache__", "venv", "venv_cachyos", "gemini_venv", "node_modules", 
    "archive", "temp", "llama.cpp", "whisper.cpp", "legacy_vault", 
    "legacy_docs", ".git", ".gemini", "python-evic", "voxtral", "voxtral_rust"
}

def get_all_python_files(base_dir="."):
    py_files = set()
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.normpath(os.path.join(root, file))
                py_files.add(full_path)
    return py_files

def resolve_import_to_path(module_name, base_dir="."):
    parts = module_name.split('.')
    path_as_file = os.path.join(base_dir, *parts) + ".py"
    path_as_dir_init = os.path.join(base_dir, *parts, "__init__.py")
    if os.path.exists(path_as_file): return os.path.normpath(path_as_file)
    elif os.path.exists(path_as_dir_init): return os.path.normpath(path_as_dir_init)
    return None

def get_imports_from_file(file_path):
    imports = set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except Exception:
        return imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names: imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
            for alias in node.names: imports.add(f"{node.module}.{alias.name}")
    return imports

def build_dependency_graph():
    all_files = get_all_python_files()
    visited = set()
    queue = [r for r in ROOTS if os.path.exists(r)]
    visited.update(queue)

    while queue:
        current_file = queue.pop(0)
        for imp in get_imports_from_file(current_file):
            local_path = resolve_import_to_path(imp)
            if local_path and local_path in all_files and local_path not in visited:
                visited.add(local_path)
                queue.append(local_path)
                
    return all_files - visited

def main():
    orphans = build_dependency_graph()
    archive_dir = "archive"
    os.makedirs(archive_dir, exist_ok=True)
    
    moved_count = 0
    # We only auto-archive loose files in the ROOT directory to prevent 
    # breaking structured tools in modules/ or tools/
    for file in orphans:
        if os.path.dirname(file) == "" or os.path.dirname(file) == ".":
            dest = os.path.join(archive_dir, os.path.basename(file))
            # Handle naming collisions in archive
            if os.path.exists(dest):
                base, ext = os.path.splitext(os.path.basename(file))
                dest = os.path.join(archive_dir, f"{base}_drift{ext}")
                
            shutil.move(file, dest)
            print(f"[ARCHIVED] {file} -> {dest}")
            moved_count += 1
            
    print(f"\nCleanup Complete! Moved {moved_count} top-level ghost scripts to '{archive_dir}/'.")

if __name__ == "__main__":
    main()