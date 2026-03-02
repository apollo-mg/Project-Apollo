import os
import sys
import llm_interface

def verify_vision_pipeline(image_path="tmp/webcam_capture.jpg"):
    """Tests if we can capture an image and get a description from Qwen."""
    if not os.path.exists(image_path):
        print(f"Error: {image_path} not found. Run webcam_capture.py first.")
        return False
    
    print(f"--- Testing Vision Pipeline with: {image_path} ---")
    prompt = "Describe the object in this image in one sentence."
    
    try:
        # Explicitly calling Qwen via our interface
        description = llm_interface.query_llm(
            prompt, 
            model_override="qwen2.5vl:latest", 
            image_path=image_path
        )
        print(f"Qwen Response: {description}")
        return True
    except Exception as e:
        print(f"Vision Pipeline Failed: {e}")
        return False

if __name__ == "__main__":
    # If an image path is provided, use it; otherwise, use the default webcam capture location.
    target_image = sys.argv[1] if len(sys.argv) > 1 else "tmp/webcam_capture.jpg"
    verify_vision_pipeline(target_image)
