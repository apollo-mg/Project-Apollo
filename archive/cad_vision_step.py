import sys
import json
import re
from modules.toolbox import Toolbox
from llm_interface import query_llm, VISION_MODEL, ENGINEER_MODEL

def main():
    print("--- [CAD VISION] Capturing frame... ---")
    img_path = Toolbox.capture_vision()
    if "Error" in img_path:
        print(img_path)
        return

    # Turn 1: Vision Extraction
    prompt_v = """
Look at the object and the ruler in this image.
1. If the object is too small or far away to see clearly, output a JSON bounding box like: {"status": "too_far", "bbox": [left, top, right, bottom]} where values are 0-100.
2. If clear, identify the primitive shape (e.g. Cube, Cylinder, Hex nut).
3. Use the ruler as a reference to estimate dimensions in millimeters (X, Y, Z).
4. Identify any identifying features (letters like X/Y/Z, markings).
5. Output ONLY a JSON block with: {"status": "clear", "primitive": "...", "dimensions_mm": {"x": 20, "y": 20, "z": 20}, "features": ["..."]}
    """
    
    print("--- [CAD VISION] Running Qwen2.5-VL analysis... ---")
    vision_json_str = query_llm(prompt_v, model_override=VISION_MODEL, image_path=img_path)
    print("\n--- [VISION RESULT] ---")
    print(vision_json_str)

    # Parse JSON
    try:
        # Extract json from markdown if present
        match = re.search(r'\{.*\}', vision_json_str, re.DOTALL)
        if match:
            v_data = json.loads(match.group())
        else:
            print("Failed to parse vision JSON.")
            return
    except Exception as e:
        print(f"JSON Parse Error: {e}")
        return

    if v_data.get("status") != "clear":
        print("Object is too far or not clear. Try zooming in.")
        return

    # Turn 2: CAD Generation (DeepSeek-R1)
    prompt_c = f"""
I have a physical object identified via vision:
{json.dumps(v_data, indent=2)}

Generate an OnShape FeatureScript snippet to recreate this part. 
Include the following:
1. Necessary imports (e.g., 'std/geometry.fs').
2. An 'annotation' for a feature type.
3. The 'export const' definition for the feature.
4. Logic using 'opBox' or similar primitives to match the dimensions: {v_data['dimensions_mm']}.
5. If features like '{v_data['features']}' are present, add a comment on how they might be implemented (e.g., via 'opText').

Output ONLY the raw FeatureScript code.
    """

    print("\n--- [CAD GEN] Running DeepSeek-R1 (The Engineer)... ---")
    fs_code = query_llm(prompt_c, model_override=ENGINEER_MODEL)
    print("\n--- [FEATURE SCRIPT] ---")
    print(fs_code)

    # Turn 3: Logging
    print("\n--- [LOGGING] Saving interaction... ---")
    log_result = Toolbox.log_cad_learning(
        intent=f"Reverse engineer a physical {v_data['primitive']}",
        solution=fs_code,
        image_path=img_path
    )
    print(log_result)

if __name__ == "__main__":
    main()
