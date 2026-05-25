import time
import os
import sys
import subprocess

# Ensure we can import from the parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import desktop_eyes

def check_screen_for_errors():
    prompt = """Look at the terminal or IDE on the screen. Do you see any error messages, stack traces, or bugs?
If NO ERRORS are visible, reply EXACTLY with 'STATUS_CLEAR'.
If YES, describe the error in detail and provide the surrounding code context."""
    
    print("\n[*] Scanning desktop for errors...")
    analysis = desktop_eyes.analyze_desktop(prompt)
    
    if analysis and "STATUS_CLEAR" in analysis:
        print("[✓] No errors detected on screen.")
        return None
    elif analysis:
        print(f"[!] Architect detected an issue:\n{analysis}")
        return analysis
    else:
        print("[-] Vision analysis failed.")
        return None

def consult_flash_reviewer(error_context):
    print("\n[*] Consulting Gemini 3 Flash Preview for a fix...")
    prompt = f"The local 27B Architect saw the following error on the user's screen:\n\n{error_context}\n\nPlease provide a concise explanation and the exact code fix required."
    
    try:
        result = subprocess.run(
            ["gemini", "-m", "gemini-3-flash-preview", "-p", prompt, "-o", "text"],
            capture_output=True,
            text=True,
            check=True
        )
        print("\n=== [ Gemini 3 Flash Fix ] ===")
        print(result.stdout.strip())
        print("==============================\n")
    except subprocess.CalledProcessError as e:
        print(f"[-] Gemini CLI failed: {e.stderr}")

def start_watcher(interval_seconds=20):
    print(f"=== Starting Sovereign Pair Programmer ===")
    print(f"Vision Interval: {interval_seconds} seconds")
    print(f"Press Ctrl+C to stop.")
    
    try:
        while True:
            error_info = check_screen_for_errors()
            if error_info:
                consult_flash_reviewer(error_info)
                # Pause longer if an error was found so the user can fix it
                print("[*] Pausing for 60 seconds to allow for repairs...")
                time.sleep(60)
            else:
                time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("\n[!] Watcher terminated by user.")

if __name__ == "__main__":
    # Start the watcher with a 20-second loop
    start_watcher(20)
