import json
import os
import sys
import re
import threading
import llm_interface
import foundry_logger
import asyncio
from modules.theme import stylized_print, get_alert, get_audit, CLR_CYAN, CLR_GOLD, CLR_BLUE, CLR_DIM, CLR_RESET
from modules.core import load_text, load_json, save_json, clean_json_string, PERSONA_PATH, SOUL_PATH, MEMORY_PATH, ROADMAP_PATH, HISTORY_PATH, DOSSIER_PATH, CitizenDossier
from modules.toolbox import Toolbox
from modules.router import classify_intent, get_module_prompt
from buddy_guardian import SovereignGuardian

# Initialize Foundry Logger
foundry = foundry_logger.FoundryLogger()

def reflect_and_learn(user_input, buddy_response):
    user_esc = json.dumps(user_input)
    buddy_esc = json.dumps(buddy_response)
    prompt = f"Extract insights (projects, preferences, history) from: {user_esc} -> {buddy_esc}. JSON only."
    try:
        res = llm_interface.query_llm(prompt, model_override=llm_interface.RECEPTIONIST_MODEL)
        m = re.search(r'\{.*\}', res, re.DOTALL)
        if m:
            data = json.loads(clean_json_string(m.group(0)))
            for k, v in data.items():
                if isinstance(v, list):
                    for item in v: CitizenDossier.add_insight(k, item)
    except: pass

class Orchestrator:
    @staticmethod
    def fast_path(user_input):
        low = user_input.lower()
        if "inventory mode" in low:
            return "Acknowledged. Inventory mode. What do you want to do? (Options: List by category, Add an item, Report damage, Add to wishlist)"
        if "gpu" in low or "vram" in low: return Toolbox.check_gpu()
        if any(x in low for x in ["cpu", "ram", "disk", "memory"]): return Toolbox.check_system()
        if "task" in low or "todo" in low:
            if any(v in low for v in ["list", "show", "status"]): return Toolbox.list_tasks()
        if "list vault" in low: return Toolbox.list_vault_content()
        if "notes" in low and any(v in low for v in ["list", "show"]): return Toolbox.list_notes()
        if "inventory" in low and any(v in low for v in ["list", "show", "detail"]): return Toolbox.get_inventory_detail()
        if "forge" in low and any(v in low for v in ["list", "show"]):
            status = "refined" if "refined" in low else "raw"
            return Toolbox.list_forge(status)
        if "refine forge" in low: return Toolbox.refine_forge()
        return None

def chat_with_buddy(user_input, log_callback=None):
    def log(mod, msg, col=CLR_CYAN):
        stylized_print(mod, msg, color=col)
        if log_callback:
            try:
                import asyncio
                asyncio.run_coroutine_threadsafe(log_callback(f"**[{mod.upper()}]** {msg}"), asyncio.get_event_loop())
            except: pass

    log("dispatcher", "Analyzing request...")
    
    # 1. Fast Path
    fp_res = Orchestrator.fast_path(user_input)
    
    # 2. Routing
    intent = classify_intent(user_input)
    mod = intent.get("module", "CHITCHAT")
    
    # Force Tags
    forced = None
    if "[FORCE DEV_BUDDY]" in user_input: forced = "DEV"
    elif "[FORCE ARCHITECT]" in user_input: forced = "ARCHITECT"
    elif "[FORCE VISION]" in user_input or "[FORCE SHOP_BUDDY]" in user_input: forced = "SHOP"
    elif "[FORCE LIBRARIAN]" in user_input: forced = "LIBRARIAN"
    elif "[FORCE PROCUREMENT]" in user_input: forced = "PROCUREMENT"
    
    if forced:
        mod = forced
        user_input = user_input.replace(f"[FORCE {forced}]", "").strip()

    if fp_res and not forced:
        log("integrity", "System: VERIFIED.", col=CLR_GOLD)
        return fp_res, None

    # Integrity
    if "VERIFIED" in SovereignGuardian.check_system_integrity():
        log("integrity", "System: VERIFIED.", col=CLR_GOLD)
    else:
        log("alert", "INTEGRITY BREACH!", col=CLR_GOLD)

    # 3. Vision Shortcut
    image_path = None
    m = re.search(r'\[ATTACHED_IMAGE:\s*(.*?)\s*\]', user_input)
    if m:
        image_path = m.group(1).strip()
        user_input = user_input.replace(m.group(0), "").strip()
        
    m_pdf = re.search(r'\[ATTACHED_PDF:\s*(.*?)\s*\]', user_input)
    if m_pdf:
        pdf_path = m_pdf.group(1).strip()
        user_input = user_input.replace(m_pdf.group(0), "").strip()
        try:
            import fitz
            doc = fitz.open(pdf_path)
            if len(doc) > 0:
                page = doc.load_page(0)
                # Use Matrix(1, 1) to avoid massive VRAM usage/GGML assert errors on big PDFs
                pix = page.get_pixmap(matrix=fitz.Matrix(1, 1))
                out_path = pdf_path.replace(".pdf", "_page0.jpg")
                pix.save(out_path)
                image_path = out_path
                log("vision", f"Rendered PDF page 0 to {out_path}", col=CLR_GOLD)
        except Exception as e:
            log("vision", f"Error rendering PDF: {e}", col=CLR_GOLD)
    
    if "capture" in user_input.lower() and "vision" in user_input.lower():
        log("vision", "DIRECT CAPTURE...", col=CLR_GOLD)
        res = Toolbox.capture_vision()
        if "Error" not in res: image_path = res
        else: return res, None

    if mod == "CHITCHAT" and not image_path:
        log("receptionist", "Routing...", col=CLR_BLUE)
        return llm_interface.query_llm(user_input, model_override=llm_interface.RECEPTIONIST_MODEL), None

    # 4. Heavy Path
    log("engineer", f"Waking [{mod}] Mind...", col=CLR_CYAN)
    soul = load_text(SOUL_PATH)
    inv_state = Toolbox.get_inventory_detail()
    mod_prompt = get_module_prompt(mod)
    
    tools_list = """- check_gpu, check_system, add_task, list_tasks, complete_task, save_note, list_notes, add_hardware, list_inventory, get_inventory_detail, diff_inventory(items_to_check: list), update_item_status(name: str, status: str), add_to_wishlist(name: str, category: str, notes: str), identify_hardware, visual_inventory_audit, crop_image(image_path: str, box: list), analyze_flyer(text_content: str), update_price(item_name: str, new_price: float, store_name: str), scaffold_project, harvest_insight, write_code, run_shell, list_vault_content, web_search, query_vault, ingest_url, ingest_pdf."""

    json_mandate = f"""CURRENT INVENTORY:
{inv_state}

Available Tools:
{tools_list}
Example call: {{"tool": "diff_inventory", "args": {{"items_to_check": ["pliers", "wrenches"]}}}}
To execute bash, use: {{"tool": "run_shell", "args": {{"command": "ls -la"}}}}
To write code, use: {{"tool": "write_code", "args": {{"file_path": "script.py", "content": "print('hello')"}}}}"""

    engineer_sys_msg = f"""You are {mod} Engineer. SOUL: {soul}.
{mod_prompt}

{json_mandate}

INSTRUCTIONS FOR AGENTIC LOOP:
- You are in a continuous loop. You can call tools repeatedly to solve problems.
- WHEN CALLING A TOOL: You MUST provide your action as a valid JSON object. DO NOT output markdown outside the JSON.
- If a tool fails or throws an error, you will receive the error output. Read it, fix your call or logic, and try again.
- WHEN FINISHED: Once you have completely satisfied the user's request and NO LONGER need tools, just type your final response to the user in plain text. Do NOT hallucinate tool results."""

    msgs = [{"role": "system", "content": engineer_sys_msg}, {"role": "user", "content": user_input}]
    
    turn = 0
    full_resp = ""
    results = []
    max_turns = 10

    # Vision Turn 0 (If Image Provided)
    if image_path:
        log("vision", f"Processing initial image analysis...", col=CLR_CYAN)
        vision_sys = "You are the Vision Mind. Analyze the image exhaustively. Extract all visible text, logos, serial numbers, UI elements, and layout details so the Engineer can act on them."
        vision_msgs = [{"role": "system", "content": vision_sys}, {"role": "user", "content": "Analyze this image."}]
        
        v_resp = ""
        stream = llm_interface.stream_llm("", messages_override=vision_msgs, model_override=llm_interface.VISION_MODEL, image_path=image_path)
        for token in stream:
            v_resp += token
            print(token, end="", flush=True)
        print()
        
        msgs.append({"role": "user", "content": f"[VISION SYSTEM OUTPUT: {v_resp}]\n\nPlease execute the user's original request based on this visual data."})

    # Main Agentic Loop
    while turn < max_turns:
        turn += 1
        log("engine", f"[TURN {turn}] streaming...", col=CLR_CYAN)
        t_resp = ""
        
        if mod == "ARCHITECT":
            target = llm_interface.ARCHITECT_MODEL
        elif mod == "RESEARCH":
            target = llm_interface.RESEARCH_MODEL
        else:
            target = llm_interface.ENGINEER_MODEL
            
        stream = llm_interface.stream_llm("", messages_override=msgs, model_override=target)
        
        for token in stream:
            t_resp += token
            print(token, end="", flush=True)
        print()
        full_resp += t_resp
        msgs.append({"role": "assistant", "content": t_resp})

        # Robust JSON block extraction
        json_target = t_resp.split("</think>")[-1] if "</think>" in t_resp else t_resp
        
        extracted_blocks = []
        stack = []
        start = -1
        for i, char in enumerate(json_target):
            if char == '{':
                if len(stack) == 0:
                    start = i
                stack.append(char)
            elif char == '}':
                if len(stack) > 0:
                    stack.pop()
                    if len(stack) == 0:
                        extracted_blocks.append(json_target[start:i+1])

        any_called = False
        for call_json in extracted_blocks:
            try:
                call = json.loads(call_json)
                if "tool" not in call:
                    continue
                name = call["tool"]
                args = call.get("args", {})
                log("intercept", f"Call: {name}", col=CLR_GOLD)
                if hasattr(Toolbox, name):
                    method = getattr(Toolbox, name)
                    import inspect
                    sig = inspect.signature(method)
                    valid_args = {}
                    
                    # For a single parameter function, if args has anything, map its first value
                    if len(sig.parameters) == 1 and len(args) > 0:
                        param_name = list(sig.parameters.keys())[0]
                        val = list(args.values())[0]
                        if isinstance(val, list) and len(val) > 0:
                            valid_args[param_name] = ", ".join([str(v) for v in val])
                        else:
                            valid_args[param_name] = val
                    else:
                        # Otherwise carefully match existing params
                        for k, v in args.items():
                            if k in sig.parameters:
                                valid_args[k] = v

                    res = method(**valid_args) if valid_args else method()
                    log("result", "Complete.", col=CLR_GOLD)
                    msgs.append({"role": "user", "content": f"TOOL RESULT: {res}"})
                    results.append({"tool_call": call, "result": res})
                    any_called = True
                else: 
                    log("error", f"Tool {name} not found.", col=CLR_GOLD)
                    msgs.append({"role": "user", "content": f"TOOL EXECUTION FAILED: Tool '{name}' does not exist. Please check Available Tools and try again."})
                    any_called = True # Force another turn
            except Exception as e:
                log("error", f"Tool Execution Error: {e}", col=CLR_GOLD)
                msgs.append({"role": "user", "content": f"TOOL EXECUTION FAILED: {e}. Please fix your JSON or arguments and try again."})
                any_called = True # Force another turn
                continue
        
        if not any_called:
            break

    # Log to Foundry
    final = full_resp.split("</think>")[-1].strip()
    # Extract thought block if present
    thought = full_resp.split("</think>")[0].replace("<think>", "").strip() if "</think>" in full_resp else ""
    foundry.log_turn(user_input, thought, [r["tool_call"] for r in results], [r["result"] for r in results], final)
    
    history = load_json(HISTORY_PATH)
    history.append({"user": user_input, "buddy": final})
    save_json(HISTORY_PATH, history)
    threading.Thread(target=reflect_and_learn, args=(user_input, final)).start()
    return final, None

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", nargs="*", help="User prompt")
    args = parser.parse_args()
    user_prompt = ""
    if not sys.stdin.isatty():
        with sys.stdin as f: user_prompt = f.read().strip()
    if args.prompt: user_prompt += ("\n" + " ".join(args.prompt)).strip()
    if user_prompt:
        chat_with_buddy(user_prompt)
