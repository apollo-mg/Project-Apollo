import sys
sys.path.append("/home/mark/gemini")
from llm_interface import query_llm, ARCHITECT_MODEL, ENGINEER_MODEL

schema = {
  "type": "object",
  "properties": {
    "hardware_identified": {
      "type": "string"
    },
    "confidence_score": {
      "type": "number"
    },
    "requires_further_search": {
      "type": "boolean"
    }
  },
  "required": [
    "hardware_identified",
    "confidence_score",
    "requires_further_search"
  ]
}

print(f"Testing Structured Outputs via Ollama ({ENGINEER_MODEL})...")

try:
    result = query_llm(
        prompt="I am looking at a green circuit board with 'Raspberry Pi 4 Model B' written on the silkscreen.",
        system_message="You are a hardware expert.",
        model_override=ENGINEER_MODEL,
        schema=schema
    )
    print("\n[SUCCESS] Ollama Structured JSON Output:")
    print(result)
except Exception as e:
    print(f"\n[ERROR] Failed: {e}")
