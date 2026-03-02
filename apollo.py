import argparse
import sys
import buddy_agent
from modules.theme import get_banner, CLR_GOLD, CLR_RESET, USER_NAME

def run_text_mode():
    print(get_banner())
    print(f"{CLR_GOLD}System standing by for {USER_NAME}.{CLR_RESET}")
    print("Type 'exit', 'quit', or Ctrl+C to leave.")
    
    while True:
        try:
            user_input = input(f"\n{CLR_GOLD}{USER_NAME}{CLR_RESET}> ").strip()
            if not user_input: continue
            
            if user_input.lower() in ["exit", "quit"]:
                print(f"{CLR_GOLD}Apollo: System standing by.{CLR_RESET}")
                break
                
            response, _ = buddy_agent.chat_with_buddy(user_input)
            print(f"\n{CLR_GOLD}◈ {CLR_RESET}{response}")
            
        except KeyboardInterrupt:
            print("\nApollo: System standing by.")
            break
        except Exception as e:
            print(f"Error: {e}")

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
