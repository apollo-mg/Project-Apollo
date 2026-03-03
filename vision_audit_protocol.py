import json
import re
import sys
from llm_interface import query_llm, VISION_MODEL, DEEP_ENGINEER_MODEL
from modules.toolbox import Toolbox

def vision_audit_protocol(image_path):
    """
    Executes a multi-turn cascading visual inventory audit.
    Turn 1: Qwen3-VL (Vision) extracts architectural anchor points.
    Turn 2+: DeepSeek-R1 uses a probability matrix to cascade tool usage 
             (e.g., web_search for low confidence, diff_inventory for high).
    """
    print(f"--- [TURN 1: VISION SCAN ({VISION_MODEL})] ---")
    print(f"Target Image: {image_path}")
    
    # Turn 1: Vision Model
    sys_msg_vision = (
        "You are the Vision Mind. Analyze the provided image of hardware.\n"
        "1. First, attempt to explicitly identify the main device/item (e.g., 'Motherboard Model X', 'NVIDIA GTX 1080', 'Logitech Mouse').\n"
        "2. Regardless of identification, you MUST extract 'Architectural Anchor Points':\n"
        "   - Board form factor, color, and mounting hole locations.\n"
        "   - Port layout (e.g., '4x USB-A and 1x Ethernet on the right edge', 'MicroSD slot on the bottom').\n"
        "   - Pin headers visible (e.g., '40-pin GPIO header along the top edge').\n"
        "   - Notable logos, silkscreen text, part numbers, or branding.\n"
        "   - Major Integrated Circuits (ICs) and their markings.\n"
        "Output your findings clearly and concisely, prioritizing physical layout facts."
    )
    
    vision_output = query_llm(
        prompt="Identify the main device in this image. If you cannot, list all identifiable details.",
        system_message=sys_msg_vision,
        model_override=VISION_MODEL,
        image_path=image_path
    )
    
    print(f"\n[VISION OUTPUT]\n{vision_output}\n")
    
    print(f"--- [TURN 2+: CASCADING IDENTIFICATION ({DEEP_ENGINEER_MODEL})] ---")
    
    # Turn 2+: Reasoning Specialist uses a probability matrix to drive tool usage
    sys_msg_engineer = (
        "You are the Engineer Mind. You evaluate hardware using a Probability Matrix.\n"
        "TASK 1: Review the available context. Create a probability matrix of your top guesses for the hardware.\n"
        "TASK 2: Based on your highest confidence score:\n"
        "  - IF YOU HAVE NOT SEARCHED YET: You MUST formulate a tool call to `web_search` to verify the exact model name, silkscreen text, or part numbers. (Vision models frequently hallucinate 'B' as '6' or '8' as 'B'). DO NOT skip this step for specific part numbers or obscure boards.\n"
        "  - IF YOU HAVE ALREADY SEARCHED AND GOT IRRELEVANT RESULTS: You MUST stop searching. Output a tool call to `diff_inventory` using your best guess.\n"
        "  - IF YOU HAVE SEARCHED AND CONFIRMED THE MODEL (or if it is a completely generic item like 'Mouse'): Formulate a tool call to `diff_inventory` passing your verified hardware name as an array to check if it exists in our inventory.\n"
        "ACTION: Output your thought process, followed by a Strict JSON block containing the matrix and tool call.\n\n"
        "FORMAT REQUIRED:\n"
        "```json\n"
        "{\n"
        "  \"probability_matrix\": [\n"
        "    {\"guess\": \"Exact Model Name Here\", \"confidence\": 0.85}\n"
        "  ],\n"
        "  \"tool\": \"web_search\",\n"
        "  \"args\": {\"query\": \"Search text here\"}\n"
        "}\n"
        "```\n"
        "Available tools: web_search, diff_inventory."
    )
    
    messages = [
        {"role": "system", "content": sys_msg_engineer},
        {"role": "user", "content": f"Raw Vision Output:\n{vision_output}"}
    ]
    
    final_report = ""
    max_turns = 3
    
    for turn in range(max_turns):
        print(f"\n--- [ENGINEER TURN {turn+1}] ---")
        
        engineer_output = query_llm(
            prompt=None,
            messages_override=messages,
            model_override=DEEP_ENGINEER_MODEL
        )
        messages.append({"role": "assistant", "content": engineer_output})
        
        # Parse the JSON tool call
        json_target = engineer_output.split("</think>")[-1] if "</think>" in engineer_output else engineer_output
        m = re.search(r'\{.*\"probability_matrix\".*\}', json_target, re.DOTALL)
        
        # Fallback if probability matrix is missing but a tool is called
        if not m:
            m = re.search(r'\{.*\"tool\".*\}', json_target, re.DOTALL)
            
        if m:
            try:
                raw_json = m.group(0)
                call = json.loads(raw_json)
                
                matrix = call.get("probability_matrix", [])
                print("[PROBABILITY MATRIX]:")
                for guess in matrix:
                    print(f"  - {guess.get('guess')}: {guess.get('confidence')}")
                
                tool_name = call.get("tool")
                args = call.get("args", {})
                
                if tool_name:
                    print(f"\n-> EXECUTING: {tool_name} {args}")
                    
                    if hasattr(Toolbox, tool_name):
                        tool_func = getattr(Toolbox, tool_name)
                        try:
                            # Normalize args for diff_inventory
                            if tool_name == "diff_inventory":
                                if isinstance(args, list):
                                    args = {"items_to_check": args}
                                elif isinstance(args, dict) and "query" in args:
                                    args = {"items_to_check": args["query"] if isinstance(args["query"], list) else [args["query"]]}
                                elif isinstance(args, dict) and "items_to_check" not in args:
                                    # Fallback if it sent some other weird dict like {'hardware': ['item']}
                                    val = list(args.values())[0]
                                    args = {"items_to_check": val if isinstance(val, list) else [val]}

                            # Dynamic arg expansion
                            tool_result = tool_func(**args) if args else tool_func()
                            
                            # Trim very long results for context window safety
                            tool_result_str = str(tool_result)[:1500] 
                            print(f"-> RESULT: {tool_result_str}...\n")
                            
                            if tool_name == "diff_inventory":
                                final_report = (
                                    "--- [FINAL IDENTIFICATION] ---\n"
                                    f"Selected: {matrix[0].get('guess') if matrix else args}\n\n"
                                    "--- [INVENTORY STATUS] ---\n"
                                    f"{tool_result}"
                                )
                                break
                            else:
                                # Feed result back in and continue loop
                                messages.append({
                                    "role": "user", 
                                    "content": f"TOOL RESULT from {tool_name}:\n{tool_result_str}\n\nUpdate your probability matrix based on this new information. If confidence is now >= 90%, call diff_inventory."
                                })
                        except Exception as e:
                            err_msg = f"Tool execution error: {e}"
                            print(f"-> ERROR: {err_msg}")
                            messages.append({"role": "user", "content": err_msg})
                    else:
                        print(f"-> ERROR: Tool '{tool_name}' not found in Toolbox.")
                        break
                else:
                    print("-> No tool called. Exiting loop.")
                    break
            except Exception as e:
                print(f"JSON Parse Error: {e}")
                print(f"Raw String: {raw_json}")
                break
        else:
            print("No valid JSON tool call found in output.")
            break

    if not final_report:
        final_report = "Process incomplete or did not reach diff_inventory. Check logs for details."
        
    return final_report

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Pass all arguments as a list of image paths
        paths = sys.argv[1:]
        res = vision_audit_protocol(paths if len(paths) > 1 else paths[0])
        print(f"\n{res}")
    else:
        print("Usage: python vision_audit_protocol.py <image_path> [image_path2 ...]")