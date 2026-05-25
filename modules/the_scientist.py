import subprocess
import json
import sqlite3
import os
import sys
import time
from pathlib import Path

LLM_SERVER_BIN = "/mnt/TG_2TB/Projects/Apollo/llm-server/llm-server"
CAPABILITY_DB = "vault/hardware_profiles.db"

def init_db():
    os.makedirs(os.path.dirname(CAPABILITY_DB), exist_ok=True)
    conn = sqlite3.connect(CAPABILITY_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS node_capabilities (
            node_name TEXT PRIMARY KEY,
            ip TEXT,
            port INTEGER,
            model_name TEXT,
            context_window INTEGER,
            tps_baseline REAL,
            pp_tps REAL,
            precision_bits REAL,
            internet_access BOOLEAN,
            optimal_flags TEXT,
            status TEXT DEFAULT 'idle',
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn

def evaluate_quality(host, port, test_prompt="Write a short summary of the Apollo space program."):
    """LLM-as-a-judge or simple heuristic to check for corruption (e.g. literal '?' chars)."""
    # Simple heuristic for now: check if output is corrupted with ??
    import urllib.request
    api_url = f"http://{host}:{port}/v1/chat/completions"
    payload = {
        "messages": [{"role": "user", "content": test_prompt}],
        "temperature": 0.1,
        "max_tokens": 100
    }
    try:
        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=120) as res:
            data = json.loads(res.read().decode('utf-8'))
            output = data['choices'][0]['message']['content']
            
            # Heuristic check for corruption
            if output.count('?') > 3 or len(output.strip()) < 10:
                return False, "Corrupted output detected."
            return True, "Output coherent."
    except Exception as e:
        return False, str(e)

def run_tuning(model_path, node_name="RX_9070_XT", extra_flags=None, rounds=4):
    """Wraps llm-server --ai-tune and logs the best config."""
    print(f"[*] The Scientist: Initiating Auto-Tune for {model_path} on {node_name}")
    
    cmd = ["bash", LLM_SERVER_BIN, model_path, "--ai-tune", "--rounds", str(rounds)]
    if extra_flags:
        cmd.extend(extra_flags)
        
    # We will just parse the output to find the best TPS
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    best_gen = 0.0
    best_pp = 0.0
    best_name = "baseline"
    
    try:
        stdout, _ = proc.communicate(timeout=7200)
        for line in stdout.split("\n"):
            print(f"[llm-server] {line}")
            if "Baseline:" in line:
                for p in line.split():
                    if p.startswith("gen="):
                        try: best_gen = float(p.split("=")[1])
                        except: pass
                    elif p.startswith("pp="):
                        try: best_pp = float(p.split("=")[1])
                        except: pass
            if "NEW BEST:" in line or "Result:" in line:
                for p in line.split():
                    if p.startswith("gen="):
                        try:
                            g = float(p.split("=")[1])
                            if g > best_gen: best_gen = g
                        except: pass
            if "wins!" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    best_name = parts[-1].replace("wins!", "").strip()
    except subprocess.TimeoutExpired:
        proc.kill()
        print("[-] Tuning timed out.")

    print(f"[*] Tuning Complete. Best config: {best_name}, TPS: {best_gen}")
    
    # Store in DB
    conn = init_db()
    conn.execute("""
        INSERT OR REPLACE INTO node_capabilities 
        (node_name, ip, port, model_name, context_window, tps_baseline, pp_tps, precision_bits, internet_access, optimal_flags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        node_name,
        "127.0.0.1",
        8081,
        os.path.basename(model_path),
        32768, # Default assumed
        best_gen,
        best_pp,
        4.0, # Default assumed
        True,
        json.dumps({"name": best_name, "extra_flags": extra_flags})
    ))
    conn.commit()
    conn.close()
    
    return best_gen

if __name__ == "__main__":
    init_db()
    print("The Scientist LLMOps module initialized.")
