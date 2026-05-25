import urllib.request
import json

tool_code = """
import urllib.request
import json

@mcp.tool()
def starbuck_write_scratchpad(key: str, value: str) -> str:
    \"\"\"
    Writes data into the Sovereign Message Bus scratchpad for sharing state across the distributed swarm.
    Use this to push local file contents to the SQLite database so remote workers can read them.
    \"\"\"
    try:
        url = os.environ.get("MESSAGE_BUS_API", "http://127.0.0.1:8000")
        url = f"{url.rstrip('/')}/scratchpad"
        
        data = json.dumps({"key": key, "value": value}).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                return f"Successfully wrote to scratchpad key '{key}'."
            else:
                return f"Failed to write to scratchpad. Status: {response.status}"
    except Exception as e:
        return f"Error writing to scratchpad: {str(e)}"
"""

with open("/mnt/TG_2TB/Projects/Starbuck/starbuck_daemon.py", "r") as f:
    content = f.read()

content = content.replace('if __name__ == "__main__":', tool_code + '\nif __name__ == "__main__":')

with open("/mnt/TG_2TB/Projects/Starbuck/starbuck_daemon.py", "w") as f:
    f.write(content)
