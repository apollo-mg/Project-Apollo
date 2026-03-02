import llm_interface_v3 as llm
import modules.router_v3 as router
import os
import sys

# Ensure we can import from the testing directory and current directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_v3_stack():
    print("--- [APOLLO V3 SYSTEM TEST] ---")
    
    test_inputs = [
        "How much VRAM am I using?",                             # SYSTEM
        "Write a python script to parse a csv file.",             # DEV (Qwen3-8B)
        "Identify the components in this image.",                # SHOP (Qwen3-VL)
        "Why is my multi-threaded race condition happening?",     # DEEP_THINK (DeepSeek-R1)
        "I need a complete architectural refactor of the Vault."  # ARCHITECT (Qwen3-30B)
    ]
    
    for inp in test_inputs:
        print(f"\n[Input]: {inp}")
        classification = router.classify_intent(inp)
        module = classification.get("module", "CHITCHAT")
        print(f"[Router]: -> {module} (Priority: {classification.get('priority')})")
        
        # Determine model for this module
        model_map = {
            "SYSTEM": llm.RECEPTIONIST_MODEL,
            "DEV": llm.ENGINEER_MODEL,
            "DEEP_THINK": llm.DEEP_ENGINEER_MODEL,
            "ARCHITECT": llm.ARCHITECT_MODEL,
            "SHOP": llm.VISION_MODEL
        }
        
        target_model = model_map.get(module, llm.RECEPTIONIST_MODEL)
        print(f"[Model Target]: {target_model}")
        
        # Perform a quick 1-shot query
        print(f"[Executing Test Query...]")
        try:
            # We use a very short prompt
            res = llm.query_llm("Respond with 'OK' if you are active.", model_override=target_model)
            print(f"[Response]: {res}")
        except Exception as e:
            print(f"[Error]: {e}")

if __name__ == "__main__":
    test_v3_stack()
