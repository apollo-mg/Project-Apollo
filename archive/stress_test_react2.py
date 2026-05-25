import sys
import buddy_agent

def run_stress_test():
    prompt = """[FORCE DEV_BUDDY] Please run the python script `broken_script.py` using the `run_shell` tool. 
It will crash. Read the traceback carefully. 
Then, use the `write_code` tool to completely rewrite `broken_script.py` to fix the bug you found. 
Finally, use `run_shell` again to verify it works. Stop when the script prints 'SUCCESS'."""

    print("--- STARTING REAL-WORLD REACT STRESS TEST V2 ---")
    print(f"Prompt: {prompt}\n")
    
    response, _ = buddy_agent.chat_with_buddy(prompt)
    
    print("\n--- STRESS TEST COMPLETE ---")
    print("Final Agent Response:")
    print(response)

if __name__ == "__main__":
    run_stress_test()
