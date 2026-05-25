#!/usr/bin/env python3
import urllib.request
import json
import time
import threading
import subprocess

# Global stats
peak_vram_mb = 0
peak_power_w = 0
peak_temp_c = 0
running = True

def monitor_hardware():
    global peak_vram_mb, peak_power_w, peak_temp_c, running
    while running:
        try:
            # rocm-smi output parsing (Edge Temp, Avg Power, VRAM used)
            # -t: Temp, -p: Power, -m: Memory
            res = subprocess.check_output(['rocm-smi', '--showuse', '--showpower', '--showtemp', '--csv'], text=True)
            for line in res.strip().split('\n'):
                if 'card0' in line:
                    parts = line.split(',')
                    if len(parts) >= 4:
                        # Depends on rocm-smi version, fallback to standard parsing
                        pass
            
            # Use json flag for easier parsing
            res = subprocess.check_output(['rocm-smi', '--showuse', '--showpower', '--showtemp', '--json'], text=True)
            data = json.loads(res)
            for card, metrics in data.items():
                if 'card0' in card:
                    # Parse Temp
                    for k, v in metrics.items():
                        if 'Temperature (Sensor edge)' in k or 'Temperature (Sensor junction)' in k:
                            try:
                                temp = float(v)
                                if temp > peak_temp_c: peak_temp_c = temp
                            except: pass
                        if 'Average Graphics Package Power (W)' in k:
                            try:
                                power = float(v)
                                if power > peak_power_w: peak_power_w = power
                            except: pass
                        if 'GPU use (%)' in k: # Just checking usage
                            pass
                            
            # VRAM allocated to llama-server
            # We can use rocm-smi --showmeminfo vram
            mem_res = subprocess.check_output(['rocm-smi', '--showmeminfo', 'vram', '--json'], text=True)
            mem_data = json.loads(mem_res)
            for card, metrics in mem_data.items():
                if 'card0' in card:
                    for k, v in metrics.items():
                        if 'VRAM Total Used Memory (B)' in k:
                            try:
                                vram_mb = int(v) / (1024 * 1024)
                                if vram_mb > peak_vram_mb: peak_vram_mb = vram_mb
                            except: pass
        except Exception as e:
            pass
        time.sleep(0.5)

def main():
    global running
    monitor_thread = threading.Thread(target=monitor_hardware)
    monitor_thread.start()

    print("[Scientist] Initiating Benchmark against Qwopus 27B on port 8082...")
    
    url = "http://127.0.0.1:8082/v1/chat/completions"
    prompt = (
        "You are an expert Python systems engineer. "
        "Write a highly optimized O(N) Python function to solve the Two-Sum problem. "
        "The input array is NOT sorted and can contain negative integers. "
        "You MUST explain your logical execution path inside `<think>...</think>` tags FIRST. "
        "After closing the think block, you MUST return ONLY a JSON object containing two keys: "
        "'logic_summary' (a 1-sentence string) and 'code' (the python function as a string). "
        "Do NOT output markdown ticks around the JSON. Start your response exactly with <think>."
    )
    
    data = {
        "model": "Qwopus3.5-27B-v3-Q2_K.gguf",
        "messages": [
            {"role": "system", "content": "You are a Senior AI Architecture Consultant."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.6,
        "top_p": 0.95,
        "stream": True
    }
    
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
    
    start_time = time.time()
    first_token_time = None
    output_text = ""
    
    try:
        with urllib.request.urlopen(req) as response:
            for line in response:
                line = line.decode('utf-8').strip()
                if line.startswith('data: '):
                    payload = line[6:]
                    if payload == '[DONE]':
                        break
                    chunk = json.loads(payload)
                    
                    if first_token_time is None:
                        first_token_time = time.time()
                        
                    delta = chunk['choices'][0].get('delta', {})
                    if 'content' in delta:
                        text = delta['content']
                        if text is not None:
                            output_text += str(text)
                            print(str(text), end='', flush=True)
    except Exception as e:
        print(f"Error during API call: {e}")
    finally:
        end_time = time.time()
        running = False
        monitor_thread.join()

    print("\n\n" + "="*50)
    print("BENCHMARK RESULTS")
    print("="*50)
    
    ttft = first_token_time - start_time if first_token_time else 0
    total_time = end_time - start_time
    gen_time = end_time - first_token_time if first_token_time else 0
    
    # Estimate tokens based on words (roughly 1.3 tokens per word) for a quick metric, 
    # since llama.cpp stream doesn't always send usage unless configured.
    estimated_tokens = len(output_text.split()) * 1.3
    
    print(f"Time to First Token (Prefill): {ttft:.2f} seconds")
    print(f"Total Generation Time: {gen_time:.2f} seconds")
    if gen_time > 0:
        print(f"Estimated Generation TPS: {estimated_tokens / gen_time:.2f} t/s")
    
    print(f"Peak VRAM Usage: {peak_vram_mb / 1024:.2f} GB")
    print(f"Peak Power Draw: {peak_power_w:.2f} W")
    print(f"Peak VRAM Temp: {peak_temp_c:.2f} C")

if __name__ == "__main__":
    main()
