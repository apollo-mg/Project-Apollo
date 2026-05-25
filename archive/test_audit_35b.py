import requests

audit_prompt = """You are a strict code auditor. The user requested: 'Write a python script that returns the sum of 2 and 2'. The generated python code was executed. Here is the execution output:
Exit Code: 1
Stderr: TypeError: 'int' object is not iterable

Did the code successfully fulfill the request? If it crashed, failed, or printed an error (even if exit code is 0), answer with 'FAIL' and a brief explanation. If it succeeded, answer with 'PASS'."""

payload = {
    "messages": [{"role": "user", "content": audit_prompt}],
    "temperature": 0.1,
    "max_tokens": 150
}

res = requests.post("http://127.0.0.1:11435/v1/chat/completions", json=payload, timeout=60)
print(f"35B Audit Decision:\n{res.json().get('choices', [{}])[0].get('message', {}).get('content', '')}")
