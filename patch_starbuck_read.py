import urllib.request
import json

tool_code = """
@mcp.tool()
def starbuck_read_scratchpad(key: str) -> str:
    \"\"\"
    Reads data from the Sovereign Message Bus scratchpad.
    Use this to pull file contents or context passed from the Architect across the distributed swarm.
    \"\"\"
    try:
        url = os.environ.get("MESSAGE_BUS_API", "http://127.0.0.1:8000")
        url = f"{url.rstrip('/')}/scratchpad/{key}"
        
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                return data.get("value", "Error: 'value' key not found in response")
            else:
                return f"Failed to read from scratchpad. Status: {response.status}"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return f"Error: Key '{key}' not found in scratchpad."
        return f"HTTP Error reading scratchpad: {str(e)}"
    except Exception as e:
        return f"Error reading from scratchpad: {str(e)}"
"""

with open("/mnt/TG_2TB/Projects/Starbuck/starbuck_daemon.py", "r") as f:
    content = f.read()

content = content.replace('if __name__ == "__main__":', tool_code + '\nif __name__ == "__main__":')

with open("/mnt/TG_2TB/Projects/Starbuck/starbuck_daemon.py", "w") as f:
    f.write(content)
