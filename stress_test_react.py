import sys
import buddy_agent

def run_stress_test():
    prompt = """[FORCE DEV_BUDDY] Create a Python file named `test_math_script.py` using `write_code`.
The script should accept two command line arguments and print their product. 
However, I want you to deliberately make a syntax error on your first try when writing it (e.g., forget a colon or parenthesis).
Then, use `run_shell` to execute `python3 test_math_script.py 5 10`.
The shell will return a traceback. I want you to read the traceback, use `write_code` to fix the syntax error, and then run it again with `run_shell`.
Only complete the task when the script successfully outputs '50'."""

    print("--- STARTING REAL-WORLD REACT STRESS TEST ---")
    print(f"Prompt: {prompt}\n")
    
    response, _ = buddy_agent.chat_with_buddy(prompt)
    
    print("\n--- STRESS TEST COMPLETE ---")
    print("Final Agent Response:")
    print(response)

if __name__ == "__main__":
    run_stress_test()
