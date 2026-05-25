#!/usr/bin/env python3
import sys
import json
import requests
import argparse

# Workstation configuration
LLM_API_URL = "http://10.0.0.5:11435/v1/chat/completions"
OLLAMA_API_URL = "http://10.0.0.5:11434/api/generate"
OLLAMA_MODEL = "deepseek-r1:14b"

def delegate_task(instruction, payload):
    try:
        # Try native llama-server first
        data = {
            "messages": [
                {"role": "system", "content": "You are a specialized worker agent. Perform the requested task on the provided data and return ONLY the result, with no conversational filler."},
                {"role": "user", "content": f"Task: {instruction}\n\nData Payload:\n{payload}"}
            ],
            "temperature": 0.1
        }
        response = requests.post(LLM_API_URL, json=data, timeout=300)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
    except requests.exceptions.RequestException:
        pass # Fallback to Ollama
        
    try:
        # Fallback to Ollama
        print("[*] Native server down or timed out, falling back to Ollama...")
        data = {
            "model": OLLAMA_MODEL,
            "prompt": f"System: You are a specialized worker agent. Perform the requested task on the provided data and return ONLY the result.\nUser Task: {instruction}\n\nData Payload:\n{payload}",
            "stream": False
        }
        response = requests.post(OLLAMA_API_URL, json=data, timeout=300)
        if response.status_code == 200:
            return response.json()['response']
        else:
            return f"Error: Ollama returned status {response.status_code} - {response.text}"
    except requests.exceptions.RequestException as e:
        return f"Error: Both Native Server and Ollama are unreachable at 10.0.0.5. Details: {e}"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Delegate a summarization or extraction task to the Workstation LLM.")
    parser.add_argument("--instruction", required=True, help="What the LLM should do with the data (e.g., 'Summarize these logs')")
    parser.add_argument("--data", help="The raw text data to process")
    parser.add_argument("--file", help="Path to a file containing the data to process")
    
    args = parser.parse_args()
    
    payload = ""
    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                payload = f.read()
        except Exception as e:
            print(f"Error reading file: {e}")
            sys.exit(1)
    elif args.data:
        payload = args.data
    else:
        print("Error: Must provide either --data or --file")
        sys.exit(1)
        
    result = delegate_task(args.instruction, payload)
    print(result)
