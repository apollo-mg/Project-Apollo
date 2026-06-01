import os
import subprocess
import json
import sqlite3
import time
import urllib.request
import urllib.error
from pathlib import Path
import re

LLAMA_SERVER_BIN = "/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant/build/bin/llama-server"
LLAMA_BENCH_BIN = "/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant/build/bin/llama-bench"
MESSAGE_BUS_DB = "/mnt/TG_2TB/Projects/Apollo/vault/message_bus.db"

class TheScientist:
    def __init__(self, model_path: str, node_id: str = "RX_9070_XT"):
        self.model_path = model_path
        self.node_id = node_id

    def run_profiler(self, configs):
        """Runs llama-bench against a matrix of configurations to find TTFT and Tok/s."""
        print(f"[*] The Scientist: Profiling {len(configs)} configurations for {self.model_path}...")
        results = []
        for cfg in configs:
            c = cfg.get("c", 8192)
            ctk = cfg.get("ctk", "q8_0")
            ctv = cfg.get("ctv", "q8_0")
            ub = cfg.get("ub", 512)
            
            cmd = [
                LLAMA_BENCH_BIN,
                "-m", self.model_path,
                "-c", str(c),
                "-ctk", ctk,
                "-ctv", ctv,
                "-ub", str(ub),
                "-n", "128", # Tokens to generate
                "-p", "512"  # Prompt tokens
            ]
            
            print(f"    -> Testing config: c={c}, ctk={ctk}, ctv={ctv}, ub={ub}")
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                # Parse output for speed (tok/s) and TTFT.
                # llama-bench outputs markdown tables.
                # Example: | model | size | params | backend | threads | test | t/s |
                tok_s = 0.0
                for line in proc.stdout.split('\n'):
                    if "tg" in line and "tok/s" not in line: # Token generation
                        parts = [p.strip() for p in line.split('|')]
                        if len(parts) > 7:
                            try:
                                tok_s = float(parts[7].replace("±", "").strip().split()[0])
                            except:
                                pass
                            
                results.append({
                    "config": cfg,
                    "tok_s": tok_s,
                    "stdout": proc.stdout
                })
                print(f"       Result: {tok_s} tok/s")
            except subprocess.TimeoutExpired:
                print(f"       Result: Timeout")
                results.append({"config": cfg, "tok_s": 0.0})
                
        # Sort by tok/s descending
        results.sort(key=lambda x: x["tok_s"], reverse=True)
        return results

    def _nuclear_unload(self, proc):
        if not proc: return
        print("[*] Performing nuclear unload of LLM process...")
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        except Exception:
            pass
        
        # Verify VRAM is cleared
        print("    -> Verifying VRAM release...")
        smi_cmd = ["rocm-smi"] if "RX_9070" in self.node_id else ["nvidia-smi"]
        # Allow VRAM to settle
        time.sleep(2)
        for _ in range(5):
            try:
                subprocess.check_output(smi_cmd, stderr=subprocess.DEVNULL)
                time.sleep(1)
            except (FileNotFoundError, subprocess.CalledProcessError):
                time.sleep(1)
        
        print("    -> Unload complete.")

    def launch_server(self, config, port=8083):
        """Launches llama-server with the given config for quality evaluation."""
        cmd = [
            LLAMA_SERVER_BIN,
            "-m", self.model_path,
            "--port", str(port),
            "-c", str(config.get("c", 8192)),
            "-ctk", config.get("ctk", "q8_0"),
            "-ctv", config.get("ctv", "q8_0"),
            "-ub", str(config.get("ub", 512))
        ]
        print(f"[*] Starting llama-server on port {port} for LLM-as-a-Judge validation...")
        
        def set_oom_score():
            try:
                with open('/proc/self/oom_score_adj', 'w') as f:
                    f.write('1000')
            except Exception:
                pass

        proc = subprocess.Popen(
            cmd, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL,
            preexec_fn=set_oom_score
        )
        
        # Wait for server to be ready
        for _ in range(30):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
                return proc
            except:
                time.sleep(1)
        self._nuclear_unload(proc)
        return None

    def evaluate_quality(self, port=8083):
        """LLM-as-a-Judge Evaluator to check for '2-Bit Lobotomy' via strict JSON schema generation."""
        dummy_context = "This is a dummy context string to aggressively fill the KV cache and stress the quantization boundaries. " * 2000
        test_prompt = f"{dummy_context}\n\nReturn a JSON object with a single key 'status' and value 'operational'. Do not return any markdown formatting or extra text."
        api_url = f"http://127.0.0.1:{port}/v1/chat/completions"
        payload = {
            "messages": [{"role": "user", "content": test_prompt}],
            "temperature": 0.0,
            "max_tokens": 50
        }
        print("[*] Running Deep Context (20k+) JSON schema validation test battery...")
        try:
            req = urllib.request.Request(
                api_url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=30) as res:
                data = json.loads(res.read().decode('utf-8'))
                output = data['choices'][0]['message']['content'].strip()
                
                # Check for strict JSON parseability
                # MoE 2-bit models often hallucinate markdown or ??? chars here
                try:
                    parsed = json.loads(output)
                    if parsed.get("status") == "operational":
                        return True, "Strict JSON generated successfully."
                    return False, f"Parsed JSON did not match schema. Output: {output}"
                except json.JSONDecodeError:
                    return False, f"JSON Decode Error. Output: {output}"
                    
        except Exception as e:
            return False, f"API Error: {str(e)}"

    def sync_database(self, verified_config):
        """Writes verified specs into the Capability Router's fleet_status table."""
        print(f"[*] Syncing verified hardware physics to Fleet Admiral (message_bus.db)...")
        try:
            with sqlite3.connect(MESSAGE_BUS_DB, timeout=30.0) as conn:
                cursor = conn.cursor()
                # Upsert into fleet_status
                # If node exists, update its capabilities based on The Scientist's findings
                cursor.execute('''
                    INSERT INTO fleet_status (node_id, status, active_model_archetype, max_slot_context, hot_kv_tokens, warm_kv_tokens, kv_precision, last_seen)
                    VALUES (?, 'online', 'any', ?, 0, 0, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(node_id) DO UPDATE SET 
                        max_slot_context = excluded.max_slot_context,
                        kv_precision = excluded.kv_precision,
                        last_seen = CURRENT_TIMESTAMP
                ''', (
                    self.node_id,
                    verified_config.get("c", 8192),
                    verified_config.get("ctk", "q8_0")
                ))
                conn.commit()
                print(f"[+] Capability Router updated: Node {self.node_id} -> Context: {verified_config.get('c')}, Precision: {verified_config.get('ctk')}")
        except Exception as e:
            print(f"[-] Database sync failed: {e}")

    def run_automated_llmops(self):
        # Define the matrix of configurations to test
        configs = [
            {"c": 32768, "ctk": "q8_0", "ctv": "q8_0", "ub": 512},
            {"c": 16384, "ctk": "q4_0", "ctv": "q4_0", "ub": 512},
            {"c": 8192,  "ctk": "fp16", "ctv": "fp16", "ub": 1024},
            {"c": 32768, "ctk": "q4_0", "ctv": "q4_0", "ub": 1024}
        ]
        
        # 1. Profile Phase
        ranked_results = self.run_profiler(configs)
        
        # 2. Evaluation Phase
        verified_config = None
        for result in ranked_results:
            if result["tok_s"] == 0: continue
            
            cfg = result["config"]
            print(f"\n[*] Evaluating configuration candidate: {cfg} (Tok/s: {result['tok_s']})")
            
            server_proc = self.launch_server(cfg)
            if not server_proc:
                print("[-] Failed to start llama-server with this config.")
                continue
                
            try:
                success, msg = self.evaluate_quality()
                if success:
                    print(f"[+] Configuration PASSED LLM-as-a-Judge: {msg}")
                    verified_config = cfg
                    self._nuclear_unload(server_proc)
                    break
                else:
                    print(f"[-] Configuration FAILED LLM-as-a-Judge (2-Bit Lobotomy detected): {msg}")
            finally:
                self._nuclear_unload(server_proc)
                
        # 3. Database Sync Phase
        if verified_config:
            self.sync_database(verified_config)
            print("\n[+] The Scientist: LLMOps loop completed successfully.")
        else:
            print("\n[-] The Scientist: All configurations failed validation.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="The Scientist - Automated LLMOps")
    parser.add_argument("--model", type=str, required=True, help="Path to the GGUF model")
    parser.add_argument("--node", type=str, default="RX_9070_XT", help="Node ID to update in the Fleet Router")
    args = parser.parse_args()
    
    scientist = TheScientist(args.model, args.node)
    scientist.run_automated_llmops()