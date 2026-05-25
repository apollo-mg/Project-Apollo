import time
import json
import os
import subprocess
import buddy_agent
import vram_management

# Standard benchmark queries
BENCHMARK_SUITE = [
    {
        "name": "Hardware Telemetry",
        "prompt": "Check the GPU status and tell me the current temp.",
        "required_tool": "check_gpu",
        "expected_substring": "C"
    },
    {
        "name": "Vault Retrieval",
        "prompt": "What is the pull-up resistor value for the PT1000 in our vault?",
        "required_tool": "search_vault",
        "expected_substring": "4.7k"
    },
    {
        "name": "Web Search",
        "prompt": "What is the latest stable version of ROCm 7.1.x?",
        "required_tool": "web_search",
        "expected_substring": "7.1"
    }
]

def run_benchmark():
    print("--- SHOP BUDDY PERFORMANCE BENCHMARK ---")
    
    # Nuke history to prevent ghost hallucinations from previous runs
    history_path = "tmp/buddy_history.json"
    if os.path.exists(history_path):
        os.remove(history_path)
        print("Context Reset: History cleared.")
        
    results = []
    
    for test in BENCHMARK_SUITE:
        print(f"\nRunning Test: {test['name']}...")
        
        start_time = time.time()
        start_vram = vram_management.get_vram_usage()
        
        # Call the agent
        response = buddy_agent.chat_with_buddy(test['prompt'])
        
        end_time = time.time()
        end_vram = vram_management.get_vram_usage()
        
        duration = end_time - start_time
        vram_diff = end_vram - start_vram
        
        # Accuracy check
        accuracy = test['expected_substring'].lower() in response.lower()
        
        print(f"  Duration: {duration:.2f}s")
        print(f"  VRAM Peak Delta: {vram_diff:.2f} MB")
        print(f"  Grounded Accuracy: {'PASS' if accuracy else 'FAIL'}")
        
        results.append({
            "test": test['name'],
            "latency": duration,
            "vram_delta": vram_diff,
            "accuracy": accuracy
        })

    # Summary
    print("\n" + "="*40)
    print("BENCHMARK SUMMARY")
    print("="*40)
    avg_latency = sum(r['latency'] for r in results) / len(results)
    pass_rate = sum(1 for r in results if r['accuracy']) / len(results) * 100
    
    print(f"Average Latency: {avg_latency:.2f}s")
    print(f"Grounded Pass Rate: {pass_rate:.1f}%")
    print("="*40)

if __name__ == "__main__":
    run_benchmark()
