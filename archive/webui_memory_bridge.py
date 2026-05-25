import os
import json
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from starlette.background import BackgroundTask

app = FastAPI(title="Apollo Memory Bridge")

# Paths and Endpoints
FACTS_FILE = "/media/mark/TG_2TB/Apollo/Project-Apollo/data/apollo_facts.jsonl"
LLAMA_SERVER_URL = "http://localhost:8082/v1/chat/completions" # Your actual 35B model endpoint

def get_apollo_memory():
    """Reads the last 10 facts from the JSONL file to inject into the prompt."""
    if not os.path.exists(FACTS_FILE):
        return "No prior memory established."
    
    facts = []
    try:
        with open(FACTS_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[-10:]:
                try:
                    data = json.loads(line.strip())
                    if "fact" in data:
                        facts.append(f"- [{data.get('category', 'general')}] {data['fact']}")
                except:
                    continue
    except Exception as e:
        print(f"Error reading memory: {e}")
        
    if facts:
        return "\n".join(facts)
    return "No prior memory established."

@app.post("/v1/chat/completions")
async def proxy_chat(request: Request):
    """Intercepts Open WebUI request, injects memory, and forwards to llama-server."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON payload"})

    # 1. Fetch the memory block
    memory_block = get_apollo_memory()
    injection = f"\n\n[APOLLO SYSTEM MEMORY RECALL]\nThe following are verified facts from previous sessions. Use them to maintain persona and architectural state:\n{memory_block}\n"

    # 2. Inject into the payload
    messages = body.get("messages", [])
    system_msg_index = next((i for i, m in enumerate(messages) if m.get("role") == "system"), None)
    
    if system_msg_index is not None:
        messages[system_msg_index]["content"] += injection
    else:
        messages.insert(0, {
            "role": "system",
            "content": "You are the Apollo 35B Sovereign Core." + injection
        })
    body["messages"] = messages

    # 3. Forward to llama-server
    client = httpx.AsyncClient(timeout=300.0)
    
    # If the request is streaming, we stream the response back to Open WebUI
    if body.get("stream", False):
        req = client.build_request("POST", LLAMA_SERVER_URL, json=body)
        r = await client.send(req, stream=True)
        return StreamingResponse(
            r.aiter_raw(), 
            status_code=r.status_code, 
            headers=dict(r.headers),
            background=BackgroundTask(r.aclose)
        )
    else:
        # Non-streaming fallback
        r = await client.post(LLAMA_SERVER_URL, json=body)
        await client.aclose()
        return JSONResponse(content=r.json(), status_code=r.status_code)

@app.get("/v1/models")
async def proxy_models():
    """Dummy endpoint so Open WebUI thinks it's a real OpenAI server and can list models."""
    return {
        "object": "list",
        "data": [
            {
                "id": "Apollo-35B-Memory-Injected",
                "object": "model",
                "owned_by": "Apollo"
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    print("\n--- Starting Apollo Memory Bridge on Port 8085 ---")
    uvicorn.run(app, host="0.0.0.0", port=8085)
