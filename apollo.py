import argparse
import sys
import os
import subprocess
import time
import requests
import buddy_agent
from modules.theme import get_banner, CLR_GOLD, CLR_CYAN, CLR_RESET, USER_NAME
from modules.toolbox import Toolbox

def check_server():
    """Check if the local llama-server is responding."""
    try:
        response = requests.get("http://127.0.0.1:8082/health", timeout=1)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def spin_up_server():
    """Spin up the stable 35B llama.cpp server in the background."""
    if check_server():
        return None # Already running

    print(f"{CLR_GOLD}Apollo:{CLR_RESET} Waking up 35B MoE Inference Engine...")

    script_path = os.path.join(os.path.dirname(__file__), "tools", "run_qwen_35b_server_new.sh")

    if not os.path.exists(script_path):
        print(f"[-] Error: Could not find {script_path}")
        return None

    # Launch the bash script we perfected earlier
    process = subprocess.Popen(["bash", script_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Wait for it to come online (35B might take a few seconds to load to VRAM)
    for _ in range(30):
        if check_server():
            print(f"{CLR_GOLD}Apollo:{CLR_RESET} Engine Online and Ready.")
            return process
        time.sleep(1)

    print("[-] Warning: Inference Engine failed to start in time. Check VRAM or run server manually.")
    return process

def handle_slash_commands(command):
    """Router for local CLI commands that bypass the LLM."""
    cmd = command.lower().strip()

    if cmd == "/clear":
        os.system('cls' if os.name == 'nt' else 'clear')
        print(get_banner())
        return True

    elif cmd == "/status":
        print(f"\n{CLR_CYAN}--- SYSTEM STATUS ---{CLR_RESET}")
        print(f"API Server: {'ONLINE' if check_server() else 'OFFLINE'}")
        print(Toolbox.check_gpu())
        return True

    elif cmd == "/queue":
        print(f"\n{CLR_CYAN}--- CHECKING HEARTBEAT QUEUE ---{CLR_RESET}")
        # Calls buddy_agent's queue logic via subprocess to keep the main CLI thread clean
        subprocess.run([sys.executable, "buddy_agent.py", "--queue"])
        return True

    return False

def run_text_mode():
    os.system('cls' if os.name == 'nt' else 'clear')
    print(get_banner())
    print(f"{CLR_GOLD}System standing by for {USER_NAME}.{CLR_RESET}")
    print("Type 'exit', 'quit', or Ctrl+C to leave. Type '/status' for diagnostics.")

    # Auto-start backend
    server_process = spin_up_server()

    try:
        while True:
            user_input = input(f"\n{CLR_GOLD}{USER_NAME}{CLR_RESET}> ").strip()
            if not user_input: continue

            if user_input.lower() in ["exit", "quit"]:
                print(f"{CLR_GOLD}Apollo: System standing by.{CLR_RESET}")
                break

            # Intercept slash commands
            if user_input.startswith("/"):
                handle_slash_commands(user_input)
                continue

            # Route to Buddy Agent (Fixed Tuple Unpacking Bug)
            response = buddy_agent.chat_with_buddy(user_input)

            # Print Final Response
            if response:
                print(f"\n{CLR_GOLD}◈ Apollo:{CLR_RESET} {response}")

    except KeyboardInterrupt:
        print("\nApollo: System standing by.")
    finally:
        # Cleanup server on exit
        if server_process:
            print(f"{CLR_GOLD}Apollo:{CLR_RESET} Spinning down Inference Engine...")
            server_process.terminate()
            server_process.wait()

def run_voice_mode():
    try:
        import jarvis_voice
        print("--- PROJECT APOLLO: The Buddy System (Voice Mode) ---")
        jarvis_voice.main()
    except ImportError as e:
        print(f"Voice Mode Error: {e}")
        print("Ensure 'jarvis_voice.py' is in the same directory and dependencies are installed.")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Project Apollo: The Buddy System Interface")
    parser.add_argument("--voice", "-v", action="store_true", help="Enable Voice Mode (Wake Word: 'Buddy' / 'Zoey')")
    parser.add_argument("--text", "-t", action="store_true", help="Enable Text Mode (Default)")

    args = parser.parse_args()

    if args.voice:
        run_voice_mode()
    else:
        run_text_mode()

if __name__ == "__main__":
    main()
