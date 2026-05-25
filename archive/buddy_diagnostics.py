import os
import json
import requests
import vram_management
import time
import re

class Diagnostician:
    def __init__(self, roadmap_path="SHOP_BUDDY_ROADMAP.md"):
        self.roadmap_path = roadmap_path
        self.report = []
        self.status = "HEALTHY"

    def _log(self, component, status, details):
        icon = "✅" if status == "OK" else "❌" if status == "FAIL" else "⚠️"
        self.report.append(f"{icon} **{component}**: {status} - {details}")
        if status == "FAIL": self.status = "DEGRADED"

    def check_llm(self):
        try:
            # Check Ollama
            res = requests.get("http://localhost:11434/api/tags", timeout=2)
            if res.status_code == 200:
                models = [m['name'] for m in res.json()['models']]
                # Updated Architecture: Hermes 3 (Receptionist) + DeepSeek R1 (Engineer) + Qwen2.5-VL (Vision)
                required = ['deepseek-r1:14b', 'hermes3:8b', 'qwen2.5vl:latest']
                missing = [r for r in required if not any(r in m for m in models)]
                
                if missing:
                    self._log("LLM Brain", "WARN", f"Ollama online, but missing models: {missing}")
                else:
                    self._log("LLM Brain", "OK", f"Ollama online. Active Minds: {len(models)}")
            else:
                self._log("LLM Brain", "FAIL", f"Ollama returned {res.status_code}")
        except Exception as e:
            self._log("LLM Brain", "FAIL", f"Connection refused: {e}")

    def check_internet(self):
        try:
            requests.get("https://www.google.com", timeout=2)
            self._log("Connectivity", "OK", "Internet accessible")
        except:
            self._log("Connectivity", "FAIL", "No internet connection")

    def check_gpu(self):
        try:
            stats = vram_management.get_gpu_stats()
            vram_used = stats.get("vram_used_mb", 0)
            vram_total = stats.get("vram_total_mb", 0)
            if vram_total > 0:
                self._log("Hardware (GPU)", "OK", f"RDNA 4 detected. VRAM: {vram_used}/{vram_total} MB")
            else:
                self._log("Hardware (GPU)", "FAIL", "No AMD GPU detected via rocm-smi")
        except Exception as e:
            self._log("Hardware (GPU)", "FAIL", str(e))

    def check_vault(self):
        if os.path.exists("vault") and os.path.exists("vault/chroma_db"):
            # Check for actual content
            count = 0
            for root, dirs, files in os.walk("vault/pdfs"):
                count += len([f for f in files if f.endswith(".pdf")])
            self._log("Knowledge Vault", "OK", f"Vault Active. {count} PDFs indexed.")
        else:
            self._log("Knowledge Vault", "WARN", "Vault directory or ChromaDB missing.")

    def check_vision(self):
        # Check for video devices in /dev
        try:
            devices = [f for f in os.listdir("/dev") if f.startswith("video")]
            if devices:
                self._log("Vision System", "OK", f"Cameras detected: {', '.join(devices)}")
            else:
                self._log("Vision System", "WARN", "No /dev/video* devices found.")
        except Exception as e:
            self._log("Vision System", "WARN", f"Vision check failed: {e}")

    def parse_roadmap(self):
        if not os.path.exists(self.roadmap_path):
            self._log("Roadmap", "FAIL", "Roadmap file missing!")
            return {}

        with open(self.roadmap_path, 'r') as f:
            content = f.read()

        # Find completed phases (flexible whitespace)
        completed_features = re.findall(r'[\*\-]\s+\*\*([^\*]+)\*\*.*', content)
        # Filter for strictly checked items
        checked_items = re.findall(r'[\*\-]\s+\[x\]\s+\*\*([^\*]+)\*\*', content)
        
        return set(completed_features + checked_items)

    def check_searxng(self):
        try:
            # Check searxng local instance
            res = requests.get("http://localhost:8080/healthz", timeout=1)
            if res.status_code == 200:
                 self._log("Search Engine", "OK", "SearXNG (Local) is active.")
            else:
                 self._log("Search Engine", "WARN", f"SearXNG returned {res.status_code}")
        except:
            self._log("Search Engine", "WARN", "SearXNG not reachable at localhost:8080")

    def run(self):
        start_time = time.time()
        
        self.check_llm()
        self.check_internet()
        self.check_searxng()
        self.check_gpu()
        self.check_vault()
        self.check_vision()
        
        # Generate Full Report
        report_text = "\n".join(self.report)
        report_text += f"\n\n## Roadmap Verification\n"
        
        # Cross reference known roadmap items
        roadmap_items = self.parse_roadmap()
        # Simple string matching
        verified_count = 0
        total_count = len(roadmap_items)
        
        for item in roadmap_items:
            status = "UNKNOWN"
            # Hardcoded logic map
            if "Brain" in item or "LLM" in item: status = "OK" if "LLM Brain" in report_text and "OK" in report_text else "FAIL"
            elif "VRAM" in item or "Orchestration" in item: status = "OK" if "Hardware (GPU)" in report_text and "OK" in report_text else "FAIL"
            elif "Web Search" in item: status = "OK" if "Connectivity" in report_text and "OK" in report_text else "FAIL"
            elif "Vision" in item or "Desktop Eyes" in item: status = "OK" if "Vision System" in report_text and "OK" in report_text else "FAIL"
            elif "Vault" in item or "RAG" in item: status = "OK" if "Knowledge Vault" in report_text and "OK" in report_text else "FAIL"
            
            if status == "OK": verified_count += 1
            
        report_text += f"Verified {verified_count}/{total_count} core features from Roadmap.\n"
        report_text += f"Diagnostic Time: {time.time() - start_time:.2f}s"
        
        return report_text

if __name__ == "__main__":
    diag = Diagnostician()
    print(diag.run())
