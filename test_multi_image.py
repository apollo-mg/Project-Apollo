import sys
from llm_interface import query_llm

paths = sys.argv[1:]
print(f"Testing with: {paths}")
res = query_llm("Describe these images in detail.", model_override="qwen3-vl:8b", image_path=paths)
print(f"Response: {res}")