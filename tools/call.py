#!/usr/bin/env python3
import sys
import json
import subprocess
import os

def main():
    try:
        input_data = sys.stdin.read()
        request = json.loads(input_data)
        
        tool_name = request.get('name')
        args = request.get('arguments', {})
        
        if tool_name == 'delegate_to_workstation':
            instruction = args.get('instruction', '')
            payload = args.get('payload', '')
            
            # Call the delegate script
            script_path = os.path.join(os.path.dirname(__file__), 'delegate_to_workstation.py')
            result = subprocess.run(
                [sys.executable, script_path, '--instruction', instruction, '--data', payload],
                capture_output=True, text=True
            )
            
            print(json.dumps({"output": result.stdout.strip()}))
            
        else:
            print(json.dumps({"error": f"Unknown tool: {tool_name}"}))
            
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    main()
