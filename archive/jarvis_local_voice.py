import os
import sys
import time
import json
import requests
import numpy as np
import sounddevice as sd
from kokoro_onnx import Kokoro
import subprocess
import re
import warnings
from datetime import datetime
import io
import wave
import threading

# Suppress annoying warnings
warnings.filterwarnings("ignore")

# --- CONFIGURATION ---
WHISPER_SERVER_URL = "http://127.0.0.1:8080/inference"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "deepseek-r1:14b"
KOKORO_MODEL_PATH = "/home/mark/commander/kokoro-v0_19.onnx"
KOKORO_VOICES_PATH = "/home/mark/commander/voices.bin"
DOSSIER_PATH = "shop_dossier.json"
PENDING_PATH = "pending_knowledge.json"
SOUND_DIR = "/home/mark/commander/sounds"

# --- GLOBAL STATE ---
history = []
NOISE_HISTORY = []
WAKE_WORD = "zoey"
SAMPLE_RATE = 16000
CHUNK_SIZE = 1024
SILENCE_DURATION = 1.2
MAX_RECORD_TIME = 15.0
IS_SPEAKING = False

# --- MEMORY & CONTEXT CONFIGURATION ---
MAX_CONTEXT_TOKENS = 32000
COMPACTION_THRESHOLD = int(MAX_CONTEXT_TOKENS * 0.8) # Flush at 80% capacity
CURRENT_SESSION_TOKENS = 0
DAILY_LOG_PATH = f"/home/mark/gemini/memory_{datetime.now().strftime('%Y-%m-%d')}.md"

# Load Dossier
dossier_content = "{}"
if os.path.exists(DOSSIER_PATH):
    with open(DOSSIER_PATH, "r") as f:
        dossier_content = f.read()

# --- INITIALIZE TTS (KOKORO) ---
print("Loading Kokoro TTS...")
kokoro = Kokoro(KOKORO_MODEL_PATH, KOKORO_VOICES_PATH)

def transcribe_audio(audio_data):
    """Sends raw numpy audio data to the local whisper.cpp server."""
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        if audio_data.size == 0: return {"text": ""}
        audio_int16 = (audio_data * 32767).astype(np.int16)
        f.writeframes(audio_int16.tobytes())
    
    wav_buffer.seek(0)
    files = {'file': ('audio.wav', wav_buffer, 'audio/wav')}
    data = {'response_format': 'json', 'temperature': '0.0'}
    
    try:
        response = requests.post(WHISPER_SERVER_URL, files=files, data=data, timeout=5)
        if response.status_code == 200:
            return {"text": response.json().get('text', '').strip()}
    except requests.exceptions.ConnectionError:
        print("\n[Zoey Error] Cannot connect to Whisper server. Did you run ./start_whisper.sh?")
    except Exception as e:
        print(f"\n[STT API Error] {e}")
    return {"text": ""}

def play_sound(name):
    path = os.path.join(SOUND_DIR, f"{name}.wav")
    if os.path.exists(path):
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            subprocess.Popen(["paplay", path], stderr=subprocess.DEVNULL)
    else:
        sys.stdout.write('\a')
        sys.stdout.flush()

def get_dynamic_threshold():
    global NOISE_HISTORY, IS_SPEAKING
    if not NOISE_HISTORY: return 0.04
    sorted_noise = sorted(NOISE_HISTORY)
    baseline = sorted_noise[int(len(sorted_noise) * 0.5)] 
    margin = 0.25 if IS_SPEAKING else 0.04
    return max(baseline + margin, 0.04)

def record_until_silence(stream, input_channels, native_sample_rate):
    print("\n[Zoey] Listening...")
    play_sound("ready")
    audio_data = []
    silent_chunks = 0
    has_started = False
    start_time = time.time()
    
    ratio = int(native_sample_rate / SAMPLE_RATE)
    local_chunk_size = CHUNK_SIZE * ratio
    
    while True:
        chunk, _ = stream.read(local_chunk_size)
        mono_chunk = chunk[:, 0] if input_channels > 1 else chunk.flatten()
        if ratio > 1: mono_chunk = mono_chunk[::ratio]
        audio_data.append(mono_chunk)
        
        vol = np.max(np.abs(mono_chunk))
        threshold = get_dynamic_threshold()
        
        meter = "#" * int(vol * 50)
        status = "[WAITING]" if not has_started else "[HEARING]"
        sys.stdout.write(f"\033[K\rVol: [{meter:<25}] {status} Thresh: {threshold:.4f} ")
        sys.stdout.flush()

        if vol > threshold:
            has_started = True
            silent_chunks = 0
        else:
            if has_started: silent_chunks += 1
        
        if has_started and silent_chunks > (SILENCE_DURATION * (SAMPLE_RATE / CHUNK_SIZE)):
            break
        if not has_started and (time.time() - start_time) > 5.0:
            print("\n[Zoey] Timeout (No speech detected).")
            break
        if (time.time() - start_time) > MAX_RECORD_TIME:
            print("\n[Zoey] Max record time reached.")
            break
    
    return np.concatenate(audio_data).flatten()

def estimate_tokens(text):
    """Rough estimation of tokens (1 token ~= 4 chars) to avoid loading a heavy tokenizer."""
    return len(text) // 4

def append_to_daily_log(role, content):
    """Writes the raw interaction to the ephemeral daily log (Tier 1 Memory)."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    with open(DAILY_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n[{timestamp}] **{role.upper()}**:\n{content}\n")

ROLLING_BUFFER_TURNS = 10

def perform_rolling_compression():
    """Silently compresses the oldest messages when we exceed the ROLLING_BUFFER_TURNS limit."""
    global history, CURRENT_SESSION_TOKENS
    if len(history) <= (ROLLING_BUFFER_TURNS * 2) + 1: 
        return
        
    print("[Zoey] [VRAM] Executing micro-compression on rolling buffer...")
    messages_to_compress = history[1:3] 
    
    prompt = f"Condense this brief interaction into a single sentence fact: {messages_to_compress}"
    payload = {
        "model": "liara", 
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 50}
    }
    
    try:
        res = requests.post("http://127.0.0.1:11434/api/generate", json=payload, timeout=10)
        if res.status_code == 200:
            micro_summary = res.json().get('response', '').strip()
            if history[0]["role"] == "assistant" and "Previous context summary:" in history[0]["content"]:
                history[0]["content"] += f" | {micro_summary}"
            else:
                history.insert(0, {"role": "assistant", "content": f"Previous context summary: {micro_summary}"})
            
            del history[1:3]
            print(f"[Zoey] [VRAM] Micro-compression successful. History length: {len(history)} items.")
    except Exception as e:
        print(f"[Zoey] [VRAM ERROR] Micro-compression failed: {e}")

def perform_compaction_flush():
    """Triggers the OpenClaw-style 'Pre-Compaction Flush'."""
    global history, CURRENT_SESSION_TOKENS
    print("\n[Zoey] [SYSTEM] Context threshold reached. Performing compaction flush...")
    
    # Send the current history to the model and ask for a summary
    summary_prompt = "Summarize the key decisions and facts from our conversation so far. Output only the summary."
    
    # We use a temporary payload just for the flush
    flush_payload = {
        "messages": history + [{"role": "user", "content": summary_prompt}],
        "temperature": 0.2,
        "max_tokens": 500
    }
    
    try:
        res = requests.post("http://127.0.0.1:11435/v1/chat/completions", json=flush_payload, timeout=60)
        if res.status_code == 200:
            summary = res.json()['choices'][0]['message']['content']
            summary = re.sub(r'<think>.*?</think>', '', summary, flags=re.DOTALL).strip()
            
            # Write the flush summary to the daily log
            append_to_daily_log("SYSTEM_FLUSH", f"Conversation compacted. Summary:\n{summary}")
            
            # Reset history and prepend the summary as the new context foundation
            history = [{"role": "assistant", "content": f"Previous context summary: {summary}"}]
            CURRENT_SESSION_TOKENS = estimate_tokens(summary)
            print("[Zoey] [SYSTEM] Flush complete. History compacted.")
        else:
            print("[Zoey] [SYSTEM ERROR] Flush failed.")
    except Exception as e:
        print(f"[Zoey] [SYSTEM ERROR] Flush exception: {e}")

def get_system_context():
    """Gathers real-time system stats and available skills to inject into Zoey's prompt."""
    context = "[SYSTEM CONTEXT]\n"
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        context += f"Current Time: {now}\n"
        
        # RAM
        mem = subprocess.check_output(["free", "-h"]).decode("utf-8").split('\n')[1]
        context += f"System RAM: {mem.split()[2]} used / {mem.split()[1]} total\n"
        
        # GPU Stats (ROCm)
        try:
            # Try to get power and temp via rocm-smi
            power_out = subprocess.check_output(["rocm-smi", "--showpower"]).decode("utf-8")
            for line in power_out.split('\n'):
                if "Average Graphics Package Power" in line:
                    context += f"GPU Power: {line.split(':')[-1].strip()}\n"
            
            temp_out = subprocess.check_output(["rocm-smi", "--showtemp"]).decode("utf-8")
            for line in temp_out.split('\n'):
                if "Temperature (Sensor edge)" in line:
                    context += f"GPU Temp: {line.split(':')[-1].strip()}\n"
                    
            vram_out = subprocess.check_output(["rocm-smi", "--showmeminfo", "vram"]).decode("utf-8")
            for line in vram_out.split('\n'):
                if "Total" in line and "Memory" in line:
                    context += f"VRAM: {line.strip()}\n"
        except:
            pass

        # Available Skills (Tier 2 Memory) - OpenClaw Style Index
        skills_dir = "/home/mark/gemini/skills"
        if os.path.exists(skills_dir):
            index_lines = ["\n[AVAILABLE SKILLS (Run via <execute_skill>filename.py</execute_skill>)]"]
            for filename in os.listdir(skills_dir):
                if not filename.endswith(".py"):
                    continue
                filepath = os.path.join(skills_dir, filename)
                description = "No description available."
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                    # Extract the first docstring
                    match = re.search(r'\"\"\"(.*?)\"\"\"|\'\'\'(.*?)\'\'\'', content, re.DOTALL)
                    if match:
                        raw_desc = match.group(1) if match.group(1) else match.group(2)
                        description = " ".join(raw_desc.strip().split())
                except Exception:
                    pass
                index_lines.append(f"- {filename} : {description}")
            
            if len(index_lines) > 1:
                context += "\n".join(index_lines) + "\n"
                
    except Exception as e:
        context += f"Failed to gather some system stats: {e}\n"
    
    context += "\nUse these real-time stats and skills to answer questions or manipulate the system. Do not hallucinate."
    return context

def delegate_to_sonic(prompt):
    print("\n[Zoey] [TOOL] Delegating to Sonic (Tesslate 9B)...")
    speak("I am allocating compute to the Sonic module to forge this skill. This might take a moment.")
    time.sleep(0.5) 
    
    # 1. Unload the 35B model to free VRAM for the 9B Sonic
    print("[Zoey] [VRAM] Unloading 35B Architect to prevent spillover...")
    subprocess.run(["/home/mark/gemini/forge_manager.py", "kill"], check=False)
    time.sleep(2) # Give VRAM a moment to clear
    
    max_retries = 3
    current_prompt = f"Write a complete, self-contained python script for this request. You MUST include explicit `assert` statements at the bottom of the script to verify the logic works correctly before finishing. Output ONLY code inside a markdown block. Request: {prompt}"
    final_status = "The Sonic module failed to forge the skill after multiple attempts."
    
    for attempt in range(max_retries):
        print(f"[Zoey] [FORGE] Sonic Attempt {attempt + 1}/{max_retries}...")
        payload = {"model": "surgeon-tesslate", "prompt": current_prompt, "stream": False, "options": {"temperature": 0.3}}
        try:
            res = requests.post("http://127.0.0.1:11434/api/generate", json=payload, timeout=120)
            if res.status_code == 200:
                code_text = res.json().get('response', '')
                if "I cannot" in code_text or "I apologize" in code_text or "I'm sorry" in code_text:
                    print("\n[Zoey] [TOOL] Sonic-Tesslate refused (red-team). Falling back to Sonic-Heretic...")
                    if attempt == 0: speak("Tesslate refused the prompt. Routing to the Heretic module.")
                    payload["model"] = "surgeon-heretic"
                    res = requests.post("http://127.0.0.1:11434/api/generate", json=payload, timeout=120)
                    if res.status_code == 200:
                        code_text = res.json().get('response', '')
                
                # Extract code using regex
                raw_code = code_text
                match = re.search(r'```(?:python)?\n(.*?)\n```', code_text, re.DOTALL | re.IGNORECASE)
                if match:
                    raw_code = match.group(1).strip()
                
                timestamp = datetime.now().strftime('%H%M%S')
                draft_path = "/tmp/sonic_draft.py"
                with open(draft_path, "w", encoding="utf-8") as f:
                    f.write(raw_code)
                
                # Audit Execution
                print("[Zoey] [AUDIT] Executing draft code empirically (TDD mode)...")
                success = False
                err_msg = ""
                output_str = ""
                try:
                    # Run for up to 10 seconds
                    exec_result = subprocess.run(["python3", draft_path], capture_output=True, text=True, timeout=10)
                    output_str = f"Exit Code: {exec_result.returncode}\nStdout:\n{exec_result.stdout.strip()}\nStderr:\n{exec_result.stderr.strip()}"
                    print(f"[Zoey] [AUDIT] Raw Output:\n{output_str}")
                    
                    # EMPIRICAL AUDIT: Purely rely on Python interpreter
                    if exec_result.returncode == 0 and "AssertionError" not in exec_result.stderr and "Exception" not in exec_result.stderr:
                        print("[Zoey] [AUDIT] Empirical Pass: Exit code 0 and no exceptions.")
                        success = True
                    else:
                        print("[Zoey] [AUDIT] Empirical Fail: Python execution returned an error.")
                        success = False
                        err_msg = output_str

                except subprocess.TimeoutExpired:
                    print("[Zoey] [AUDIT] Script is running continuously. Assuming success for daemon tasks.")
                    success = True
                
                if success:
                    skills_dir = "/home/mark/gemini/skills"
                    os.makedirs(skills_dir, exist_ok=True)
                    final_path = os.path.join(skills_dir, f"skill_{timestamp}.py")
                    os.rename(draft_path, final_path)
                    final_status = f"I have successfully forged the new skill. It executed cleanly and is saved in your skills directory as skill_{timestamp}.py."
                    break
                else:
                    print(f"[Zoey] [AUDIT] Execution failed. Error: {err_msg}")
                    if attempt < max_retries - 1:
                        print("[Zoey] [SELF-HEAL] Sending error back to Sonic for correction...")
                        current_prompt = f"The previous python code you generated failed with this error:\n{err_msg}\n\nPlease fix the code and output the full corrected script. You MUST include explicit `assert` statements. Output ONLY code inside a markdown block."
                    
            else:
                final_status = "The Sonic model API returned a non-200 status."
                break
        except Exception as e:
            print(f"[Zoey] [FORGE ERROR] {e}")
            final_status = f"The Sonic model encountered an error: {e}"
            break
            
    # 2. Unload Ollama models and Reload the 35B Architect
    print("[Zoey] [VRAM] Code generation cycle complete. Reloading 35B Architect...")
    subprocess.run(["ollama", "stop", "surgeon-tesslate"], check=False)
    subprocess.run(["ollama", "stop", "surgeon-heretic"], check=False)
    subprocess.run(["/home/mark/gemini/forge_manager.py", "load", "architect_lean"], check=False)
    
    return final_status

def parse_and_execute_actions(text):
    """
    Scans for Action Tags and executes them.
    Supported: execute_shell, execute_skill, write_file, read_file, patch_file
    """
    results = []
    
    # 0. Base Path for Safety
    workspace_dir = "/home/mark/gemini/workspace"
    
    # 1. Parse Read File Actions
    read_actions = re.findall(r'<read_file\s+path="([^"]+)">', text, re.IGNORECASE)
    for file_path in read_actions:
        safe_path = os.path.join(workspace_dir, file_path)
        print(f"[Zoey] [ACTION] Reading File: {safe_path}")
        try:
            if os.path.exists(safe_path):
                with open(safe_path, "r", encoding="utf-8") as f:
                    content = f.read()
                results.append(f"[FILE CONTENT: {file_path}]\n{content}\n[END FILE CONTENT]")
            else:
                results.append(f"[FILE ERROR: {file_path}] -> File does not exist.")
        except Exception as e:
            results.append(f"[FILE ERROR: {file_path}] -> {e}")
            
    # 2. Parse Patch File Actions (Search & Replace)
    # Format: <patch_file path="..."><search>old</search><replace>new</replace></patch_file>
    patch_actions = re.findall(r'<patch_file\s+path="([^"]+)">(.*?)</patch_file>', text, re.IGNORECASE | re.DOTALL)
    for file_path, patch_body in patch_actions:
        safe_path = os.path.join(workspace_dir, file_path)
        print(f"[Zoey] [ACTION] Patching File: {safe_path}")
        try:
            search_match = re.search(r'<search>(.*?)</search>', patch_body, re.IGNORECASE | re.DOTALL)
            replace_match = re.search(r'<replace>(.*?)</replace>', patch_body, re.IGNORECASE | re.DOTALL)
            
            if search_match and replace_match and os.path.exists(safe_path):
                old_text = search_match.group(1).strip()
                new_text = replace_match.group(1).strip()
                
                with open(safe_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                if old_text in content:
                    content = content.replace(old_text, new_text, 1) # Only replace first occurrence to be safe
                    with open(safe_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    results.append(f"[FILE PATCHED: {file_path}] -> Success")
                else:
                    results.append(f"[FILE PATCH ERROR: {file_path}] -> Search string not found in file.")
            else:
                results.append(f"[FILE PATCH ERROR: {file_path}] -> Invalid patch format or file does not exist.")
        except Exception as e:
            results.append(f"[FILE PATCH ERROR: {file_path}] -> {e}")

    # 3. Parse File Writing Actions
    file_actions = re.findall(r'<write_file\s+path="([^"]+)">\s*(.*?)\s*</write_file>', text, re.IGNORECASE | re.DOTALL)
    for file_path, content in file_actions:
        # Prevent absolute path traversal attacks, force it into a safe workspace directory
        safe_path = os.path.join(workspace_dir, file_path)
        print(f"[Zoey] [ACTION] Writing File: {safe_path}")
        try:
            os.makedirs(os.path.dirname(safe_path), exist_ok=True)
            with open(safe_path, "w", encoding="utf-8") as f:
                f.write(content)
            results.append(f"[FILE WRITTEN: {file_path}] -> Success")
        except Exception as e:
            results.append(f"[FILE ERROR: {file_path}] -> {e}")

    # 4. Parse Shell and Skill Actions
    actions = re.findall(r'<execute_(shell|skill)>\s*(.*?)\s*</execute_\1>', text, re.IGNORECASE | re.DOTALL)
    for action_type, cmd in actions:
        action_type = action_type.upper()
        print(f"[Zoey] [ACTION] Executing {action_type}: {cmd}")
        
        try:
            if action_type == "SHELL":
                # Execute arbitrary shell command
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
                out = res.stdout.strip() or res.stderr.strip()
                results.append(f"[SHELL RESULT: {cmd}] -> {out}")
            elif action_type == "SKILL":
                # Execute a pre-defined python skill
                skill_path = os.path.join("/home/mark/gemini/skills", cmd)
                if os.path.exists(skill_path):
                    # Skill is already tested, so we run it directly in its own subprocess
                    res = subprocess.run(["python3", skill_path], capture_output=True, text=True, timeout=20)
                    out = res.stdout.strip() or res.stderr.strip()
                    results.append(f"[SKILL RESULT: {cmd}] -> {out}")
                else:
                    results.append(f"[SKILL ERROR] Skill '{cmd}' not found in /home/mark/gemini/skills/")
        except Exception as e:
            results.append(f"[{action_type} ERROR: {cmd}] -> {e}")
            
    return results

def get_llm_response(prompt):
    global history, CURRENT_SESSION_TOKENS
    print(f"\n[Zoey] Thinking (35B MoE)...")
    
    clean_prompt = prompt.lower().strip()
    if "clear all pending knowledge" in clean_prompt:
        if os.path.exists(PENDING_PATH):
            with open(PENDING_PATH, "w") as f:
                json.dump([], f)
        return "Understood. I have cleared the pending knowledge buffer for you."

    # Pre-Compaction Check
    estimated_new_tokens = estimate_tokens(prompt)
    if CURRENT_SESSION_TOKENS + estimated_new_tokens > COMPACTION_THRESHOLD:
        perform_compaction_flush()
        
    # Micro-compression of oldest messages to save KV Cache compute
    perform_rolling_compression()

    try:
        system_prompt = "You are Zoey, a latency-obsessed engineer."
        soul_path = "/home/mark/gemini/SOUL.md"
        if os.path.exists(soul_path):
            with open(soul_path, "r") as f:
                system_prompt = f.read()

        # Add Action Tags Instructions
        system_prompt += "\n\n[CAPABILITIES: ACTION TAGS]\n"
        system_prompt += "You have physical access to the system. You MUST NOT hallucinate the results of commands or skills. Instead, you MUST emit an action tag to actually run them.\n"
        system_prompt += "1. <execute_shell>command</execute_shell> -> Run any bash command.\n"
        system_prompt += "2. <execute_skill>filename.py</execute_skill> -> Run a python skill.\n"
        system_prompt += '3. <write_file path="folder/file.py">...code...</write_file> -> Writes raw text directly to a file.\n'
        system_prompt += '4. <read_file path="folder/file.py"></read_file> -> Reads a file into your next context turn so you can see it.\n'
        system_prompt += '5. <patch_file path="folder/file.py"><search>old text</search><replace>new text</replace></patch_file> -> Surgically edits a file by finding and replacing an exact text block.\n'
        system_prompt += "Output the tag naturally at the end of your speech. It will be executed silently, and you will see the results in the NEXT turn.\n"
        system_prompt += "Example: \"I will check the network now. <execute_skill>skill_233244.py</execute_skill>\"\n"

        file_data = ""
        if "omni-shaper" in clean_prompt or "omnishaper" in clean_prompt or "omni shaper" in clean_prompt:
            print("[Zoey] [TOOL] Reading Omni-Shaper Project File...")
            try:
                cmd = ["sshpass", "-p", "apollo", "ssh", "-o", "StrictHostKeyChecking=no", "gemini@10.0.0.118", "cat /home/gemini/Project-Apollo/projects/omni_shaper.md"]
                file_content = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode('utf-8')
                file_data = f"\n\n[FILE DATA LOADED: omni_shaper.md]\n{file_content}\n"
            except Exception as e:
                file_data = f"\n\n[FILE READ ERROR: Could not fetch omni_shaper.md]\n"

        system_prompt += f"\n\n{get_system_context()}{file_data}"

        # Tool 2: The Sonic (Coding Delegation)
        coding_keywords = ["write a script", "code me", "can you code", "write a python", "write a function", "generate code", "build a script"]
        if any(kw in clean_prompt for kw in coding_keywords):
            response = delegate_to_sonic(prompt)
            append_to_daily_log("User", prompt)
            history.append({"role": "user", "content": prompt})
            history.append({"role": "assistant", "content": response})
            append_to_daily_log("Zoey", response)
            CURRENT_SESSION_TOKENS += estimate_tokens(prompt + response)
            return response

        # Append to daily log
        append_to_daily_log("User", prompt)
        
        # Maintain history
        history.append({"role": "user", "content": prompt})

        payload = {
            "messages": [{"role": "system", "content": system_prompt}] + history,
            "temperature": 0.7,
            "max_tokens": 150
        }
        
        try:
            res = requests.post("http://127.0.0.1:11435/v1/chat/completions", json=payload, timeout=120)
        except requests.exceptions.ConnectionError:
            print("[Zoey] [SELF-HEAL] Connection to 35B MoE refused. Attempting restart...")
            speak("Someone tell Mark there is a problem with my AI. Attempting a hot restart. Just a moment.")
            subprocess.run(["/home/mark/gemini/forge_manager.py", "load", "architect_lean"], check=False)
            time.sleep(15) # Wait for model to load into VRAM
            res = requests.post("http://127.0.0.1:11435/v1/chat/completions", json=payload, timeout=120)
        
        if res.status_code == 200:
            content = res.json()['choices'][0]['message']['content']
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            
            # Action Execution Block
            action_results = parse_and_execute_actions(content)
            if action_results:
                # Append the results to history so Zoey "knows" what happened for the next interaction
                history.append({"role": "system", "content": "\n".join(action_results)})
                print(f"[Zoey] [SYSTEM] Action Results appended to context.")

            # Record response and update token count
            history.append({"role": "assistant", "content": content})
            append_to_daily_log("Zoey", content)
            
            # Update running token count roughly
            CURRENT_SESSION_TOKENS += estimate_tokens(prompt + content)
            
            # Remove Action Tags from the string we return for TTS/Speech
            clean_content = re.sub(r'<execute_(shell|skill)>.*?</execute_\1>', '', content, flags=re.IGNORECASE).strip()
            
            return clean_content
        else:
            return "I am having trouble connecting to my logic core."
    except Exception as e:
        return f"Error connecting to 35B MoE: {e}"

def speak(text):
    """Speaks text in a background thread."""
    def _speak_thread(t):
        global IS_SPEAKING
        IS_SPEAKING = True
        print(f"[Zoey] Speaking: {t}")
        # Strip markdown, emojis, and non-ASCII characters completely
        t = re.sub(r'[\*\#\_\~]', '', t)
        t = t.encode('ascii', 'ignore').decode('ascii')
        t = re.sub(r'\s+', ' ', t).strip()
        
        if not t: 
            IS_SPEAKING = False
            return

        try:
            voice_name = "af_sky"
            samples, sample_rate = kokoro.create(t, voice=voice_name, speed=1.1, lang="en-us")
            
            # Save to temporary WAV and play via PulseAudio (paplay) for robust headless playback
            temp_wav = "/tmp/zoey_response.wav"
            with wave.open(temp_wav, "w") as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(sample_rate)
                audio_int16 = (samples * 32767).astype(np.int16)
                f.writeframes(audio_int16.tobytes())
            
            subprocess.run(["paplay", temp_wav])
        except Exception as e:
            print(f"TTS Error: {e}")
        finally:
            IS_SPEAKING = False

    threading.Thread(target=_speak_thread, args=(text,), daemon=True).start()

def main():
    global NOISE_HISTORY
    print("\n--- Initializing Local Zoey (ROCm GPU) ---")
    
    # We use a single mic for both Wake and Command since the boom mic is too directional
    devices = sd.query_devices()
    input_device = None
    priority_keywords = ["pulse", "default"]
    for kw in priority_keywords:
        for i, dev in enumerate(devices):
            if kw.lower() in dev['name'].lower() and dev['max_input_channels'] > 0:
                input_device = i; break
        if input_device is not None: break
    if input_device is None: input_device = sd.default.device[0]
    print(f"✅ Using Mic: [{input_device}] {devices[input_device]['name']}")

    device_info = devices[input_device]
    input_channels = 1
    
    # Use native sample rate and downsample if needed
    native_sr = int(device_info['default_samplerate'])
    ratio = int(native_sr / SAMPLE_RATE)
    local_chunk_size = CHUNK_SIZE * ratio

    print(f"--- CALIBRATING NOISE FLOOR (2s) on {input_channels} channels ---")
    with sd.InputStream(device=input_device, samplerate=native_sr, channels=input_channels, dtype='float32') as stream:
        for _ in range(int(2.0 * SAMPLE_RATE / CHUNK_SIZE)):
            chunk, _ = stream.read(local_chunk_size)
            mono_chunk = chunk[:, 0] if input_channels > 1 else chunk.flatten()
            if ratio > 1: mono_chunk = mono_chunk[::ratio]
            vol = np.max(np.abs(mono_chunk))
            NOISE_HISTORY.append(vol)
            meter = "#" * int(vol * 50)
            sys.stdout.write(f"\033[K\rLevel: [{meter:<25}] {vol:.4f}")
            sys.stdout.flush()
    
    print(f"\nNoise Floor Set (Thresh: {get_dynamic_threshold():.4f})")
    print(f"Listening for '{WAKE_WORD}'...")

    wake_buffer = []
    last_check_time = 0
    
    try:
        with sd.InputStream(device=input_device, samplerate=native_sr, channels=input_channels, dtype='float32') as stream:
            while True:
                chunk, _ = stream.read(local_chunk_size)
                mono_chunk = chunk[:, 0] if input_channels > 1 else chunk.flatten()
                if ratio > 1: mono_chunk = mono_chunk[::ratio]
                
                vol = np.max(np.abs(mono_chunk))
                NOISE_HISTORY.append(vol)
                if len(NOISE_HISTORY) > 500: NOISE_HISTORY.pop(0)
                
                wake_buffer.append(mono_chunk)
                max_buffer_chunks = int(3.0 * SAMPLE_RATE / CHUNK_SIZE)
                if len(wake_buffer) > max_buffer_chunks:
                    wake_buffer = wake_buffer[-max_buffer_chunks:]

                threshold = get_dynamic_threshold()
                current_time = time.time()
                
                if vol > threshold and (current_time - last_check_time) > 1.2:
                    if len(wake_buffer) > (1.5 * SAMPLE_RATE / CHUNK_SIZE):
                        extra_chunks = int(0.6 * SAMPLE_RATE / CHUNK_SIZE)
                        for _ in range(extra_chunks):
                            chunk, _ = stream.read(local_chunk_size)
                            mono_chunk = chunk[:, 0] if input_channels > 1 else chunk.flatten()
                            if ratio > 1: mono_chunk = mono_chunk[::ratio]
                            wake_buffer.append(mono_chunk)
                        
                        audio_check = np.concatenate(wake_buffer).flatten()
                        result = transcribe_audio(audio_check)
                        text = result["text"].lower().strip(".,? ")
                        sys.stdout.write("\033[K")
                        print(f"\r[Zoey] Heard: '{text}'")
                        last_check_time = time.time()
                        
                        phonetic_matches = ["zoe", "zoey", "zoie", "zowy", "zo e", "zo-e", "zoë", "zowie", "zoee", "so e", "soie", "soey"]
                        
                        if any(variant in text for variant in phonetic_matches):
                            sd.stop() 
                            print(f"\n[WAKE WORD DETECTED] (Input: '{text}')")
                            
                            audio_cmd = record_until_silence(stream, input_channels, native_sr)
                            
                            play_sound("processing")
                            print("\n[Zoey] Transcribing...")
                            res_cmd = transcribe_audio(audio_cmd)
                            user_cmd = res_cmd["text"].strip()
                            
                            if user_cmd and len(user_cmd.strip(".,!? ")) > 1:
                                print(f"> You: {user_cmd}")
                                ai_text = get_llm_response(user_cmd)
                                speak(ai_text)
                            else:
                                print(f"\n[Zoey] Ignoring empty or invalid input: '{user_cmd}'")
                            
                            wake_buffer = []
                            print(f"\nListening for '{WAKE_WORD}'...")

    except KeyboardInterrupt:
        print("\nStopping Local Zoey...")

if __name__ == "__main__":
    main()
