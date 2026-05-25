#!/usr/bin/env python3
import os
import sys
import json
import urllib.request
import urllib.error
import argparse

# Default Configuration
DEFAULT_MODEL = "gemini-3-flash-preview"
API_KEY_PATH = os.path.expanduser("~/.gemini/api_key.txt")

def get_api_key():
    # Try environment variable first
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        return api_key.strip()
    
    # Fallback to the rotation script's output file
    if os.path.exists(API_KEY_PATH):
        with open(API_KEY_PATH, "r") as f:
            return f.read().strip()
            
    print("Error: GEMINI_API_KEY environment variable not set and ~/.gemini/api_key.txt not found.", file=sys.stderr)
    sys.exit(1)

def generate_content(prompt, system_instruction=None, model=DEFAULT_MODEL):
    api_key = get_api_key()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    # Construct the payload
    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ]
    }
    
    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }

    data = json.dumps(payload).encode("utf-8")
    
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            # Parse out the text from the response
            try:
                text_response = result["candidates"][0]["content"]["parts"][0]["text"]
                return text_response
            except (KeyError, IndexError):
                return f"Unexpected API response format: {json.dumps(result, indent=2)}"
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode("utf-8")
        return f"HTTP Error {e.code}: {error_msg}"
    except Exception as e:
        return f"An error occurred: {str(e)}"

def main():
    parser = argparse.ArgumentParser(description="A lightweight, fast CLI tool for utility tasks using Gemini Flash.")
    parser.add_argument("prompt", nargs="?", help="The prompt or text to process.")
    parser.add_argument("-f", "--file", help="Read input from a file instead of the command line.")
    parser.add_argument("-s", "--system", help="System instruction (e.g., 'Summarize the following text').")
    parser.add_argument("-m", "--model", default=DEFAULT_MODEL, help=f"Model to use (default: {DEFAULT_MODEL}).")
    
    args = parser.parse_args()

    input_text = ""
    
    # Read from file if specified
    if args.file:
        try:
            with open(args.file, "r") as f:
                input_text = f.read()
        except Exception as e:
            print(f"Error reading file {args.file}: {e}", file=sys.stderr)
            sys.exit(1)
    # Read from prompt argument
    elif args.prompt:
        input_text = args.prompt
    # Read from stdin if nothing else is provided (allows piping)
    elif not sys.stdin.isatty():
        input_text = sys.stdin.read()
    else:
        parser.print_help()
        sys.exit(1)

    # If both a file/stdin and a prompt are provided, combine them logically
    if args.prompt and (args.file or not sys.stdin.isatty()):
         input_text = f"{args.prompt}\n\n{input_text}"

    if not input_text.strip():
        print("Error: No input text provided.", file=sys.stderr)
        sys.exit(1)

    response = generate_content(input_text, args.system, args.model)
    print(response)

if __name__ == "__main__":
    main()