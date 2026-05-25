import requests

system_prompt = """You are Zoey. You have physical access to the system. You MUST NOT hallucinate the results of commands or skills. Instead, you MUST emit an action tag to actually run them.
1. <execute_shell>command</execute_shell> -> Run any bash command.
2. <execute_skill>filename.py</execute_skill> -> Run a python skill.
3. <read_file path="file"></read_file> -> Read a file into context.

You have a number of pre-built skills. If you need a tool, use <read_file path="/home/mark/gemini/skills/INDEX.md"></read_file> to see your available tools and their usage information. DO NOT GUESS tool names.
"""

user_prompt = "Zoey, the network seems slow. Can you run a ping test to check it?"

payload = {
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ],
    "temperature": 0.1,
    "max_tokens": 200
}

try:
    res = requests.post("http://10.0.0.5:11435/v1/chat/completions", json=payload, timeout=60)
    print(f"Response:\n{res.json().get('choices', [{}])[0].get('message', {}).get('content', '')}")
except Exception as e:
    print(f"Error: {e}")
