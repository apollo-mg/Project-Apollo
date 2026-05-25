import os
import json
import requests
import sys

# Configuration
KLIPPER_IP = "10.0.0.83"
LLM_API_URL = "http://127.0.0.1:11434/v1/chat/completions" # Defaulting to Ollama port
MODEL_NAME = "llama3.2" # Default standard model, user can change
TIMEOUT_SEC = 300
HISTORY_PATH = "voice_session.json"

# Context Paths (Linux adapted)
DOSSIER_PATH = "SYSTEM_DOSSIER.md"
CONFIG_PATH = "printer.cfg" # Assumption, might need adjustment

SYSTEM_PROMPT = """YOU ARE THE COMMANDER: An autonomous Klipper Agent.

CRITICAL INSTRUCTION:
You have NO physical eyes or sensors. You CANNOT see the printer status unless you query the API.

YOUR TOOL:
To see the printer status (temps, position, print state), you MUST output this EXACT command format:
COMMAND: Get-KlipperData -ApiPath "/printer/objects/query?heater_bed&extruder&print_stats"

WHEN TO USE IT:
- If the user asks "What are the temperatures?", "Is it printing?", "Status report", or ANYTHING requiring live data.
- DO NOT guess. DO NOT suggest G-code commands. USE THE TOOL.

RESPONSE FORMAT:
- If you need data: Output ONLY the "COMMAND: ..." line.
- If you have data (injected as KLIPPER_DATA): Answer the user concisely based on that data.

CONSTRAINTS:
1. Max 2 sentences for voice replies.
2. Never invent data."""

def get_klipper_data(api_path, method="GET"):
    uri = f"http://{KLIPPER_IP}{api_path}"
    try:
        # print(f"Querying Klipper API: {uri}")
        if method.upper() == "POST":
            response = requests.post(uri, timeout=5)
        else:
            response = requests.get(uri, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Failed to query Klipper API at {uri}: {e}")
        return {"error": str(e)}

def emergency_stop(reason="Guardian Intervention"):
    """Triggers Klipper Emergency Stop (M112 equivalent)"""
    print(f"!!! TRIGGERING EMERGENCY STOP: {reason} !!!")
    return get_klipper_data("/printer/emergency_stop", method="POST")

from datetime import datetime

def trigger_lockdown(reason):
    """Writes the lock file and kills the printer."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lock_data = {"locked": True, "reason": reason, "timestamp": timestamp}
    with open("guardian_lock.json", "w") as f:
        json.dump(lock_data, f)
    emergency_stop(reason)
    return "LOCKDOWN_ACTIVE"

def check_guardian_lock():
    """Checks if the system is locked. Returns True if locked."""
    if os.path.exists("guardian_lock.json"):
        try:
            with open("guardian_lock.json", "r") as f:
                data = json.load(f)
            if data.get("locked"):
                print(f"!!! SYSTEM LOCKED: {data.get('reason')} !!!")
                return True
        except: pass
    return False

def load_file_content(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def chat_with_llm(user_prompt, history_path=None, input_content=""):
    messages = []
    
    # Load history
    if history_path and os.path.exists(history_path):
        try:
            with open(history_path, "r", encoding="utf-8") as f:
                messages = json.load(f)
        except:
            print("Starting fresh history.")

    # Initialize if empty
    if not messages:
        dossier = load_file_content(DOSSIER_PATH)
        live_config = load_file_content(CONFIG_PATH)
        context_injection = f"--- SYSTEM DOSSIER ---\\n{dossier}\\n\\n--- ACTIVE CONFIG ---\\n{live_config}\\n\\n--- END CONTEXT ---\\n"
        
        messages.append({"role": "system", "content": SYSTEM_PROMPT})
        messages.append({"role": "user", "content": f"Here is my current system state for your reference:\\n{context_injection}"})
        messages.append({"role": "assistant", "content": "System state received. I am now fully aware of your Ender 6 hardware limits. I am ready for your commands, Commander."})

    current_user_input = user_prompt
    
    # Inject tool instruction if not present
    if "KLIPPER_DATA" not in current_user_input:
        current_user_input += "\\n\\n[SYSTEM INSTRUCTION: \\n- Status/Temps -> Output: 'COMMAND: STATUS'\\n- History/Recent -> Output: 'COMMAND: HISTORY'\\n- Emergency Stop -> Output: 'COMMAND: STOP'\\n- Pause Print -> Output: 'COMMAND: PAUSE'\\n- Resume Print -> Output: 'COMMAND: RESUME'\\n- Cancel Print -> Output: 'COMMAND: CANCEL'\\n- Home All Axes -> Output: 'COMMAND: HOME'\\n- Endstop Status -> Output: 'COMMAND: ENDSTOPS'\\n- Turn Off Heaters -> Output: 'COMMAND: COOLDOWN'\\n- Do not explain. Output ONLY the command.]"

    if input_content:
        current_user_input += f"\\n\\nInput Data:\\n{input_content}"

    messages.append({"role": "user", "content": current_user_input})

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.7
    }

    try:
        response = requests.post(LLM_API_URL, json=payload, headers={"Content-Type": "application/json"}, timeout=TIMEOUT_SEC)
        response.raise_for_status()
        data = response.json()
        assistant_content = data['choices'][0]['message']['content']
        
        messages.append({"role": "assistant", "content": assistant_content})
        
        if history_path:
            with open(history_path, "w", encoding="utf-8") as f:
                json.dump(messages, f, indent=2)
                
        return assistant_content
        
    except Exception as e:
        print(f"Failed to query Local LLM: {e}")
        return f"Error: {e}"

if __name__ == "__main__":
    # CLI Mode for testing
    if len(sys.argv) > 1:
        print(chat_with_llm(sys.argv[1]))
    else:
        print("Usage: python local_agent.py 'Your prompt here'")
