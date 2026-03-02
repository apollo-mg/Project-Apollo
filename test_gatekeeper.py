import sys
import os

# Ensure we can import from the project root
sys.path.append(os.getcwd())

from modules.router import classify_intent
import time

TEST_CASES = [
    "Hello Apollo, how are you today?",
    "What is my current GPU power draw?",
    "Scan this circuit board for any blown capacitors.",
    "Write a Python script that uses asyncio to scrape 100 websites in parallel.",
    "I'm seeing a weird race condition in my C++ thread pool, can you help me find the root cause?",
    "We need to completely redesign the Vault's underlying data structure for better horizontal scaling."
]

def test_router():
    print("--- 🛰️ APOLLO V3 GATEKEEPER TEST (Model: qwen3:0.6b) ---")
    print("-" * 60)
    
    for i, user_input in enumerate(TEST_CASES, 1):
        print(f"\n[Test {i}]: \"{user_input}\"")
        start_time = time.time()
        
        # This will call our cascading router logic
        result = classify_intent(user_input)
        
        duration = time.time() - start_time
        
        module = result.get("module", "UNKNOWN")
        priority = result.get("priority", "P3")
        routed_by = result.get("routed_by", "Unknown")
        reason = result.get("reason", "N/A")
        
        print(f"  Result: {module} ({priority})")
        print(f"  Routed By: {routed_by}")
        print(f"  Reasoning: {reason}")
        print(f"  Latency: {duration:.2f}s")
        print("-" * 30)

if __name__ == "__main__":
    test_router()
