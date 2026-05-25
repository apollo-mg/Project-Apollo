import time
import buddy_agent
import vram_management
import llm_interface

STRESS_SCENARIOS = [
    {
        "name": "Rapid Context Switch (Chat -> Work)",
        "input": "Hey Jarvis, hope you're good. Actually, can you quickly find the pinout for the Octopus Pro?"
    },
    {
        "name": "Deep Engineering (Engineer Load)",
        "input": "I need to calculate the precise stepper motor current for a 2A motor running at 0.8V reference on a TMC2209. What is the formula and the result?"
    },
    {
        "name": "Vision Interrupt (VRAM Tetris)",
        "input": "Scan this webcam image and tell me if you see a caliper."
    },
    {
        "name": "Ambiguous Follow-up (Receptionist Recall)",
        "input": "Wait, what was that formula again? And download the manual for it."
    }
]

def run_stress_test():
    print("--- 🔴 STARTING 3-MIND STRESS TEST 🔴 ---")
    try:
        print(f"Initial VRAM: {vram_management.get_vram_usage():.2f} MB")
    except:
        print("Initial VRAM: Unknown")
    
    # Ensure baseline state
    # llm_interface.unload_model("all") 
    time.sleep(2)

    for i, scenario in enumerate(STRESS_SCENARIOS):
        print(f"\n[TEST {i+1}: {scenario['name']}]")
        print(f"Input: '{scenario['input']}'")
        
        start_t = time.time()
        try:
            response, _ = buddy_agent.chat_with_buddy(scenario['input'])
            if response:
                print(f"Response: {response[:100]}...")
            else:
                print("Response: (None)")
        except Exception as e:
            print(f"❌ CRASH: {e}")
            # continue
            
        dur = time.time() - start_t
        try:
            vram = vram_management.get_vram_usage()
        except:
            vram = 0
            
        print(f"⏱️ Time: {dur:.2f}s | 💾 VRAM: {vram:.2f} MB")
        
        # Heuristic Checks
        if "Vision" in scenario['name'] and dur < 5:
            print("⚠️ WARNING: Vision seemed too fast. Did models unload?")

    print("\n--- ✅ STRESS TEST COMPLETE ---")

if __name__ == "__main__":
    run_stress_test()
