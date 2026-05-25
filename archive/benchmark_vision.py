import time
import llm_interface

IMAGE_PATH = "verify_capture.jpg"

def benchmark():
    print("--- [BENCHMARK: VRAM TETRIS LATENCY] ---")
    
    # 1. Warm-up Reasoning (DeepSeek)
    print("\nPhase 1: Loading Reasoning (DeepSeek-R1:14b)...")
    start = time.time()
    res = llm_interface.query_llm("Hello, are you ready?", model_override="deepseek-r1:14b")
    print(f"Time: {time.time() - start:.2f}s | Response: {res[:50]}...")

    # 2. Swap to Vision (The "Tetris" Move)
    print("\nPhase 2: Swapping to Vision (Qwen2.5-VL)...")
    swap_start = time.time()
    
    # Explicit Unload (Simulating new buddy_agent logic)
    llm_interface.unload_model("deepseek-r1:14b")
    unload_time = time.time()
    print(f"Unload Time: {unload_time - swap_start:.2f}s")
    
    # Vision Query
    res = llm_interface.query_llm("Describe this image.", image_path=IMAGE_PATH, model_override="qwen2.5vl:latest")
    print(f"Vision Time: {time.time() - unload_time:.2f}s | Response: {res[:50]}...")
    print(f"Total Swap Time: {time.time() - swap_start:.2f}s")

    # 3. Swap Back to Reasoning
    print("\nPhase 3: Swapping Back to Reasoning (DeepSeek)...")
    swap_back_start = time.time()
    
    # Explicit Unload Vision (Optional but testing symmetry)
    llm_interface.unload_model("qwen2.5vl:latest")
    unload_back_time = time.time()
    print(f"Unload Back Time: {unload_back_time - swap_back_start:.2f}s")
    
    # Reasoning Query
    res = llm_interface.query_llm("Analyze the previous image description.", model_override="deepseek-r1:14b")
    print(f"Reasoning Time: {time.time() - unload_back_time:.2f}s | Response: {res[:50]}...")
    print(f"Total Return Time: {time.time() - swap_back_start:.2f}s")

if __name__ == "__main__":
    benchmark()
