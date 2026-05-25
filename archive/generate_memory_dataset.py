import subprocess
import json
import time
import os
import argparse
import re

def call_gemini(agent_name, prompt_text):
    """Calls the gemini command with a specific agent and prompt."""
    # Build the full prompt including the @agent_name
    full_prompt = f"@{agent_name} {prompt_text}"
    
    try:
        # We use -y (YOLO) and -p (prompt) to run in non-interactive mode
        result = subprocess.run(
            ["gemini", "-y", "-p", full_prompt],
            capture_output=True,
            text=True,
            check=True
        )
        # The output might contain preamble like "YOLO mode enabled"
        # We should split by newline and find the actual response
        raw_output = result.stdout.strip()
        
        # Log the raw output if debug is needed (optional)
        # print(f"DEBUG: {raw_output}")
        
        return raw_output
    except subprocess.CalledProcessError as e:
        print(f"Error calling gemini for agent {agent_name}: {e.stderr}")
        return None

def extract_json(text):
    """Robustly extracts a JSON array or object from text potentially containing preamble/markdown."""
    # Find the first '[' or '{' and the last ']' or '}'
    try:
        # Match JSON array
        match_array = re.search(r'\[.*\]', text, re.DOTALL)
        if match_array:
            return json.loads(match_array.group(0))
        
        # Match JSON object
        match_obj = re.search(r'\{.*\}', text, re.DOTALL)
        if match_obj:
            return json.loads(match_obj.group(0))
            
    except Exception as e:
        print(f"Failed to parse JSON: {e}")
        return None
    return None

def extract_last_line(text):
    """Extracts the last meaningful line of text (useful for single-sentence summaries)."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if lines:
        # Filter out common CLI initialization lines
        filtered_lines = [
            line for line in lines 
            if "YOLO mode" not in line 
            and "Loaded cached credentials" not in line
            and "Background PIDs" not in line
            and "I will" not in line # Skip "I will do X..." intent lines
        ]
        if filtered_lines:
            return filtered_lines[-1]
        return lines[-1]
    return ""

def main():
    parser = argparse.ArgumentParser(description="Generate a memory dataset using Gemini agents.")
    parser.add_argument("--iterations", type=int, default=10, help="Number of iterations (default: 10).")
    parser.add_argument("--output", type=str, default="v8_memory_dataset.jsonl", help="Output JSONL file path.")
    args = parser.parse_args()

    coder_prompt = (
        "Generate exactly 5 highly technical, 3-turn conversations between a 'user' and an 'assistant'. "
        "The assistant should demonstrate deep expertise in systems programming, kernels, or distributed systems. "
        "Each conversation must be a JSON object with 'messages' as a list of {'role': 'user'|'assistant', 'content': '...'}. "
        "Output ONLY a JSON array containing these 5 objects."
    )

    print(f"Starting dataset generation: {args.iterations} iterations, target {args.iterations * 5} pairs.")
    
    with open(args.output, "a") as f:
        for i in range(args.iterations):
            print(f"--- Iteration {i+1}/{args.iterations} ---")
            
            # 1. Generate Batch of Conversations
            print("Generating technical conversations via flash_coder...")
            raw_output = call_gemini("flash_coder", coder_prompt)
            
            if not raw_output:
                print("Failed to get output from flash_coder. Skipping iteration.")
                continue
            
            conversations = extract_json(raw_output)
            
            if not conversations or not isinstance(conversations, list):
                print("Failed to extract valid JSON array from coder output. Skipping...")
                with open(f"debug_coder_fail_{i}.txt", "w") as df:
                    df.write(raw_output)
                continue

            # 2. Generate Summaries and Save
            for idx, conv in enumerate(conversations):
                print(f"Summarizing conversation {idx+1}/5 via flash_janitor...")
                conv_text = json.dumps(conv)
                summary_prompt = f"Provide a perfect single-sentence summary of the following technical conversation. Output ONLY the summary sentence:\n\n{conv_text}"
                
                raw_summary_output = call_gemini("flash_janitor", summary_prompt)
                
                if raw_summary_output:
                    summary = extract_last_line(raw_summary_output)
                    # Remove any leading/trailing quotes or prefix text if still present
                    summary = summary.replace('"', '').replace('Summary:', '').strip()
                    
                    data_entry = {
                        "conversation": conv,
                        "summary": summary
                    }
                    f.write(json.dumps(data_entry) + "\n")
                    f.flush()
                    print(f"  [v] Summary: {summary[:80]}...")
                
                # Small sleep between individual summary calls
                time.sleep(2)

            print(f"Iteration {i+1} complete. Current dataset size: {os.path.getsize(args.output)} bytes.")
            # Sleep between iterations to avoid heavy rate limiting
            time.sleep(5)

    print(f"Done! Dataset saved to {args.output}")

if __name__ == "__main__":
    main()
