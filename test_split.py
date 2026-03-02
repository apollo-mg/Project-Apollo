import subprocess
import time

def test_load():
    print("Testing Qwen3 30B split loading...")
    try:
        # Run a simple prompt to force the model to load
        proc = subprocess.Popen(
            ["ollama", "run", "qwen3-coder:30b", "Reply with only the word 'test'."],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        start = time.time()
        # Wait up to 30 seconds for a response or failure
        while time.time() - start < 30:
            if proc.poll() is not None:
                break
            time.sleep(1)
            
        if proc.poll() is None:
            proc.terminate()
            print("Process timed out.")
            return
            
        stdout, stderr = proc.communicate()
        print(f"Exit Code: {proc.returncode}")
        print(f"Stdout: {stdout.strip()}")
        if stderr:
            print(f"Stderr: {stderr.strip()}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_load()
