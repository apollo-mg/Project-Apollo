import json, urllib.request
URL="http://10.0.0.194:8091/v1/chat/completions"
TOOL=[{"type":"function","function":{"name":"get_current_weather","description":"Get the current weather in a location",
  "parameters":{"type":"object","properties":{"location":{"type":"string","description":"City, State"},"unit":{"type":"string","enum":["celsius","fahrenheit"]}},"required":["location","unit"]}}}]
def ask(msg):
    body={"model":"apollo/qwen3.6-27b-q8","messages":[{"role":"user","content":msg}],
          "tools":TOOL,"tool_choice":"auto","temperature":0,"max_tokens":4096}
    r=json.load(urllib.request.urlopen(urllib.request.Request(URL,data=json.dumps(body).encode(),
        headers={"Content-Type":"application/json"}),timeout=180))
    m=r["choices"][0]["message"]; tc=m.get("tool_calls") or []
    return len(tc), [(c["function"]["name"],c["function"]["arguments"]) for c in tc]

n1,c1=ask("What's the current weather in Boston, MA in fahrenheit? Call the function.")
print(f"SINGLE  -> {n1} call(s): {c1}")
n2,c2=ask("I need the current weather in BOTH Boston, MA and Denver, CO, both in fahrenheit. Call the function for each city.")
print(f"PARALLEL-> {n2} call(s): {c2}")
print("VERDICT:", "Qwen DOES parallel (>=2)" if n2>=2 else "Qwen ALSO under-calls (<2) -> shared artifact")
