import os
import subprocess
import time
import json
import glob
import csv
import signal
import re
from typing import List, Dict

# The Scientific Matrix
# Define the combinations of environment variables and llama-server arguments to test.
CONFIG_GRID = [
    {
        "name": "baseline_q8_0",
        "env": {"HSA_ENABLE_SDMA": "0"},
        "args": ["-ub", "32", "-ctk", "q8_0", "-ctv", "q8_0"]
    },
    {
        "name": "sdma_turbo3",
        "env": {"HSA_ENABLE_SDMA": "1"},
        "args": ["-ub", "64", "-ctk", "q8_0", "-ctv", "turbo3"]
    },
    {
        "name": "sdma_turbo4_extreme",
        "env": {"HSA_ENABLE_SDMA": "1"},
        "args": ["-ub", "64", "-ctk", "turbo4", "-ctv", "turbo3"]
    }
]

# Paths
LLAMA_SERVER_PATH = "/opt/rocm/bin/llama-server" # Adjust if your path is different
MODEL_PATH = "/mnt/TG_2TB/Projects/Apollo/models/qwen3.6-27b-moe.gguf" # Update to your target model
LAB_SCRIPT = "engines/open-multi-agent-upstream/examples/apollo_lab.ts"
JUDGE_SCRIPT = "lab/judge.py"
RESULTS_DIR = "lab/results"
CSV_OUTPUT = "scientist_benchmarks.csv"
PORT = "8082"
CTX_SIZE = "32768"

def kill_server():
    """Mercilessly kills any running llama-server instances."""
    print("🔪 Killing existing llama-server instances...")
    subprocess.run(["pkill", "-f", "llama-server"], stderr=subprocess.DEVNULL)
    time.sleep(3) # Wait for VRAM to clear

def start_server(env_vars: Dict[str, str], args: List[str]) -> subprocess.Popen:
    """Boots the llama-server with specific configurations."""
    print(f"🚀 Booting server with args: {' '.join(args)}")
    
    # Merge custom env vars with current system env
    merged_env = os.environ.copy()
    merged_env.update(env_vars)
    
    cmd = [
        LLAMA_SERVER_PATH,
        "-m", MODEL_PATH,
        "--port", PORT,
        "-c", CTX_SIZE,
        "--host", "0.0.0.0"
    ] + args
    
    # We pipe stdout/stderr so we can scan for the "listening" signal
    process = subprocess.Popen(
        cmd, 
        env=merged_env, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT,
        text=True
    )
    
    # Wait for server to bind
    ready = False
    for line in iter(process.stdout.readline, ''):
        if "HTTP server listening" in line or "server is listening" in line:
            ready = True
            break
        if "error" in line.lower() and "failed to bind" in line.lower():
            print(f"❌ Server failed to bind: {line.strip()}")
            break
            
    if not ready:
        print("❌ Server failed to boot properly. Terminating.")
        process.terminate()
        return None
        
    print("✅ Server is online and ready for traffic.")
    return process

def run_lab():
    """Executes the apollo_lab.ts test suite."""
    print("🧪 Executing Lab Suite...")
    subprocess.run(["npm", "exec", "tsx", LAB_SCRIPT, "--profile", "architect"], cwd="/mnt/TG_2TB/Projects/Apollo")
    
def run_judge() -> str:
    """Executes judge.py and returns the path to the evaluated JSON."""
    print("⚖️ Executing Judge Evaluation...")
    subprocess.run(["python3", JUDGE_SCRIPT])
    
    # Find the most recently evaluated file
    files = glob.glob(os.path.join(RESULTS_DIR, "*_evaluated.json"))
    if not files:
        return None
    return max(files, key=os.path.getctime)

def parse_and_log(config_name: str, eval_file: str):
    """Parses the evaluated JSON and appends the aggregated scores to the CSV."""
    if not eval_file:
        print("⚠️ No evaluation file found to parse.")
        return
        
    with open(eval_file, "r") as f:
        results = json.load(f)
        
    total_tests = len(results)
    passed_tests = 0
    total_score = 0
    schema_failures = 0
    
    for test in results:
        eval_data = test.get("evaluation", {})
        if eval_data:
            if eval_data.get("passed"): passed_tests += 1
            total_score += eval_data.get("score", 0)
            if eval_data.get("json_schema_broken"): schema_failures += 1
            
    avg_score = total_score / total_tests if total_tests > 0 else 0
    pass_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
    
    # Append to CSV
    file_exists = os.path.isfile(CSV_OUTPUT)
    with open(CSV_OUTPUT, "a", newline='') as csvfile:
        fieldnames = ["Timestamp", "Configuration", "Total Tests", "Pass Rate (%)", "Avg Score", "Schema Failures"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
            
        writer.writerow({
            "Timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "Configuration": config_name,
            "Total Tests": total_tests,
            "Pass Rate (%)": f"{pass_rate:.1f}",
            "Avg Score": f"{avg_score:.2f}",
            "Schema Failures": schema_failures
        })
    print(f"📊 Matrix Updated: {config_name} | Pass Rate: {pass_rate:.1f}% | Schema Fails: {schema_failures}")

def main():
    print("🧑‍🔬 Starting The Scientist Autonomous Benchmarking Pipeline...")
    
    for config in CONFIG_GRID:
        print(f"\n{'='*50}")
        print(f"🔬 Testing Configuration: {config['name']}")
        print(f"{'='*50}")
        
        kill_server()
        server_process = start_server(config["env"], config["args"])
        
        if server_process:
            try:
                run_lab()
                eval_file = run_judge()
                parse_and_log(config["name"], eval_file)
            finally:
                # Cleanup
                print("🛑 Stopping server...")
                server_process.send_signal(signal.SIGTERM)
                try:
                    server_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server_process.kill()
        else:
            print(f"⏭️ Skipping evaluation for {config['name']} due to boot failure.")
            
    print("\n🏁 All experiments complete. Review scientist_benchmarks.csv")

if __name__ == "__main__":
    main()
