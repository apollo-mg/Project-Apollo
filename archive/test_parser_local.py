import re

def parse_files(text):
    file_actions = re.findall(r'<write_file\s+path="([^"]+)">\s*(.*?)\s*</write_file>', text, re.IGNORECASE | re.DOTALL)
    for path, content in file_actions:
        print(f"Path: {path}")
        print(f"Content:\n{content}")

test_text = """
<write_file path="test.py">
def get_cpu_model():
    with open('/proc/cpuinfo', 'r') as f:
        print("Hello")
</write_file>
"""

parse_files(test_text)
