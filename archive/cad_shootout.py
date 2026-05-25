import sys
import json
import re
import time
from modules.toolbox import Toolbox
from llm_interface import query_llm, nuclear_unload, VISION_MODEL, ENGINEER_MODEL, ARCHITECT_MODEL

def main():
    img_path = "tmp/webcam_capture.jpg"
    print(f"--- [PHASE 1: METROLOGY] Loading {VISION_MODEL} ---")
    
    prompt_v = """
Look at the object and the ruler in this image.
1. Identify the primary engineered part (e.g., Hex Nut, Bracket, Gear, Cylinder).
2. Use the ruler as a reference to estimate its primary dimensions in millimeters (e.g., Outer diameter, Inner hole diameter, thickness, length).
3. Identify any key features (e.g., chamfers, threads, number of sides).
4. Output ONLY a raw JSON block representing this data. Do not include markdown formatting or explanations.
Example format:
{
  "part_type": "Hex Nut",
  "dimensions_mm": {"outer_diameter": 12, "inner_diameter": 6, "thickness": 5},
  "features": ["6-sided polygon exterior", "threaded circular interior"]
}
    """
    
    vision_json_str = query_llm(prompt_v, model_override=VISION_MODEL, image_path=img_path)
    print("\n--- [VISION EXTRACTED DATA] ---")
    print(vision_json_str)

    # Parse JSON safely
    try:
        match = re.search(r'\{.*\}', vision_json_str, re.DOTALL)
        if match:
            v_data = json.loads(match.group())
        else:
            v_data = json.loads(vision_json_str)
    except Exception as e:
        print(f"Failed to parse vision JSON: {e}")
        return

    # Clean VRAM for the code generation
    print("\n--- [VRAM SWAP] Unloading Vision Model ---")
    nuclear_unload(VISION_MODEL)
    time.sleep(3)

    prompt_c = f"""
You are an expert OnShape FeatureScript developer. 
I have a physical object that was measured via computer vision:
{json.dumps(v_data, indent=2)}

Write a complete, mathematically precise OnShape FeatureScript function that generates this parametric part. 
Requirements:
1. Include standard imports (`import(path : "onshape/std/geometry.fs", version : "...");`).
2. Define the `annotation` and `export const` for the feature.
3. Use the exact dimensions provided in the JSON to define the geometry (e.g., opExtrude, opCylinder, fPolygon).
4. Do not include markdown tags. Output ONLY raw FeatureScript code.
    """

    print(f"\n--- [PHASE 2: ENGINEER] Generating with {ENGINEER_MODEL} ---")
    engineer_code = query_llm(prompt_c, model_override=ENGINEER_MODEL)
    
    print("\n--- [VRAM SWAP] Unloading Engineer Model ---")
    nuclear_unload(ENGINEER_MODEL)
    time.sleep(3)

    print(f"\n--- [PHASE 3: ARCHITECT] Generating with {ARCHITECT_MODEL} ---")
    architect_code = query_llm(prompt_c, model_override=ARCHITECT_MODEL)
    
    print("\n--- [VRAM SWAP] Unloading Architect Model ---")
    nuclear_unload(ARCHITECT_MODEL)

    print("\n=======================================================")
    print(f"🏆 RESULTS: ENGINEER ({ENGINEER_MODEL})")
    print("=======================================================")
    print(engineer_code)
    
    print("\n=======================================================")
    print(f"🏆 RESULTS: ARCHITECT ({ARCHITECT_MODEL})")
    print("=======================================================")
    print(architect_code)

if __name__ == "__main__":
    main()
