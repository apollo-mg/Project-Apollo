import os
import sys
import shutil
import subprocess
import platform

class SubstrateAudit:
    def __init__(self):
        self.status = True
        self.report = []

    def log(self, message):
        self.report.append(message)

    def check_disk_space(self, threshold_gb=10):
        """Checks if there is sufficient disk space."""
        usage = shutil.disk_usage(".")
        free_gb = usage.free / (1024**3)
        if free_gb < threshold_gb:
            self.log(f"[CRITICAL] Low disk space: {free_gb:.2f}GB remaining.")
            self.status = False
        else:
            self.log(f"[OK] Disk space: {free_gb:.2f}GB available.")

    def check_memory(self, threshold_percent=10):
        """Checks if system memory is critically low."""
        # Using free command via subprocess for simplicity in this environment
        try:
            output = subprocess.check_output(["free", "-m"]).decode()
            lines = output.splitlines()
            mem_line = lines[1].split()
            total = int(mem_line[1])
            used = int(mem_line[2])
            percent_used = (used / total) * 100
            if percent_used > (100 - threshold_percent):
                self.log(f"[WARNING] High memory usage: {percent_used:.1f}%")
            else:
                self.log(f"[OK] Memory usage: {percent_used:.1f}%")
        except Exception as e:
            self.log(f"[ERROR] Could not check memory: {e}")

    def check_syntax_integrity(self, directory="."):
        """Performs a basic syntax check on Python files in the directory."""
        self.log("[INFO] Starting syntax integrity check...")
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(".py"):
                    path = os.path.join(root, file)
                    try:
                        with open(path, 'r') as f:
                            source = f.read()
                        compile(source, path, 'exec')
                    except SyntaxError as e:
                        self.log(f"[CRITICAL] Syntax error in {path}: {e}")
                        self.status = False
                    except Exception as e:
                        self.log(f"[ERROR] Could not parse {path}: {e}")

    def run_audit(self):
        print("--- Substrate Audit Protocol Initiated ---")
        self.check_disk_space()
        self.check_memory()
        self.check_syntax_integrity()
        
        print("\nAudit Report:")
        for line in self.report:
            print(f"  {line}")
        
        if not self.status:
            print("\n[RESULT] SUBSTRATE UNSTABLE: High-level reasoning suspended.")
            sys.exit(1)
        else:
            print("\n[RESULT] SUBSTRATE STABLE: Foundation ready for vision.")
            sys.exit(0)

if __name__ == "__main__":
    audit = SubstrateAudit()
    audit.run_audit()
