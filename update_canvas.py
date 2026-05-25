import sys
import json
import os

def update_canvas(json_payload_str):
    """
    Updates the ui_state.json file with the provided JSON payload.
    """
    target_file = "data/ui_state.json"
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(target_file), exist_ok=True)
    
    try:
        # Validate that the input is actually valid JSON
        payload = json.loads(json_payload_str)
        
        # Write the formatted JSON to the file
        with open(target_file, 'w') as f:
            json.dump(payload, f, indent=4)
            
        print(f"Successfully updated {target_file}")
        return True
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON payload provided: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python update_canvas.py '<json_string>'")
        sys.exit(1)
    
    success = update_canvas(sys.argv[1])
    if not success:
        sys.exit(1)