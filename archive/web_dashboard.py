from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
import uvicorn
from modules.dashboard import get_dashboard
import buddy_agent
import asyncio
import threading
import queue
import json

app = FastAPI()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Apollo Glass Cockpit</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        :root {
            --bg-dark: #0f172a;
            --bg-card: #1e293b;
            --text-main: #38bdf8;
            --text-muted: #94a3b8;
            --border-color: #334155;
            --accent: #22c55e;
            --header: #f8fafc;
        }
        body {
            background-color: var(--bg-dark);
            color: var(--text-main);
            font-family: 'Courier New', Courier, monospace;
            padding: 20px;
            margin: 0;
            line-height: 1.6;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        .header-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background-color: var(--bg-card);
            padding: 15px 25px;
            border-radius: 10px;
            border: 1px solid var(--border-color);
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }
        h1 {
            color: var(--header);
            margin: 0;
            font-size: 1.5rem;
            letter-spacing: 1px;
        }
        .status-indicator {
            color: var(--text-muted);
            font-size: 0.9rem;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .status-dot {
            height: 12px;
            width: 12px;
            background-color: var(--accent);
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 8px var(--accent);
        }
        .main-layout {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
        }
        .grid-layout {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .card {
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            display: flex;
            flex-direction: column;
        }
        .card-full {
            grid-column: 1 / -1;
        }
        .card h2 {
            color: var(--header);
            font-size: 1.1rem;
            margin-top: 0;
            margin-bottom: 15px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .data-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 0.9rem;
        }
        .data-label { color: var(--text-muted); }
        .data-value { color: var(--text-main); font-weight: bold; text-align: right; }
        .value-online { color: var(--accent); }
        .value-offline { color: #ef4444; }
        .value-resident { color: #a855f7; }
        
        pre.log-trace {
            background-color: #0b1120;
            padding: 15px;
            border-radius: 6px;
            border: 1px solid #1e293b;
            color: #10b981;
            font-size: 0.85rem;
            overflow-x: auto;
            margin: 0;
            white-space: pre-wrap;
        }

        .chat-container {
            display: flex;
            flex-direction: column;
            height: 600px;
        }
        .chat-box {
            flex-grow: 1;
            background-color: #0b1120;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 15px;
            overflow-y: auto;
            margin-bottom: 15px;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .chat-message {
            max-width: 85%;
            padding: 10px 15px;
            border-radius: 8px;
            font-size: 0.95rem;
            word-wrap: break-word;
        }
        .msg-user {
            background-color: #1e3a8a;
            color: #e0f2fe;
            align-self: flex-end;
            border-bottom-right-radius: 0;
        }
        .msg-bot {
            background-color: #064e3b;
            color: #d1fae5;
            align-self: flex-start;
            border-bottom-left-radius: 0;
        }
        .msg-log {
            background-color: transparent;
            color: #f59e0b;
            font-size: 0.8rem;
            align-self: flex-start;
            margin: -5px 0 5px 15px;
            font-style: italic;
        }
        .chat-input-wrapper {
            display: flex;
            gap: 10px;
        }
        .chat-input {
            flex-grow: 1;
            padding: 12px;
            border-radius: 6px;
            border: 1px solid var(--border-color);
            background-color: #0f172a;
            color: white;
            font-family: inherit;
        }
        .chat-btn {
            padding: 12px 20px;
            background-color: var(--accent);
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
        }
        .chat-btn:hover { background-color: #16a34a; }
        .chat-btn:disabled { background-color: #475569; cursor: not-allowed; }

        @media (max-width: 800px) {
            .main-layout { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header-bar">
            <h1>🚀 Apollo Sovereign OS</h1>
            <div class="status-indicator">
                <span id="time-display">--:--:--</span>
                Live <span class="status-dot"></span>
            </div>
        </div>
        
        <div class="main-layout">
            <!-- Left Side: Dashboard -->
            <div id="dashboard-content" class="grid-layout" style="align-content: start;">
                <div class="card card-full" style="text-align: center; color: var(--text-muted);">
                    Loading telemetry data...
                </div>
            </div>

            <!-- Right Side: Chat -->
            <div class="card chat-container">
                <h2>💬 Apollo Uplink</h2>
                <div id="chat-box" class="chat-box">
                    <div class="chat-message msg-bot">System online. Waiting for input...</div>
                </div>
                <form id="chat-form" class="chat-input-wrapper">
                    <input type="text" id="chat-input" class="chat-input" placeholder="Enter command or query..." autocomplete="off">
                    <button type="submit" id="chat-btn" class="chat-btn">Send</button>
                </form>
            </div>
        </div>
    </div>

    <script>
        // --- Dashboard Logic ---
        function parseData(rawText) {
            const sections = {};
            let currentSection = null;
            let currentLines = [];
            const lines = rawText.split('\\n');
            const timeMatch = rawText.match(/TIME: (\\d{2}:\\d{2}:\\d{2})/);
            if (timeMatch) document.getElementById('time-display').textContent = timeMatch[1];
            
            for (let line of lines) {
                line = line.trim();
                if (!line || line.startsWith('---')) continue;
                if (line.endsWith(':') && !line.includes('-')) {
                    if (currentSection) sections[currentSection] = currentLines;
                    currentSection = line.replace(':', '').trim();
                    currentLines = [];
                } else if (currentSection && line.startsWith('-')) {
                    currentLines.push(line.substring(1).trim());
                } else if (currentSection && line.startsWith('>')) {
                    currentLines.push(line);
                } else if (line.startsWith('INTEGRITY') || line.startsWith('📋') || line.startsWith('⚠️')) {
                    if (!sections['System Status']) sections['System Status'] = [];
                    sections['System Status'].push(line);
                }
            }
            if (currentSection) sections[currentSection] = currentLines;
            return sections;
        }

        function formatValue(val) {
            if (val.includes('ONLINE') || val.includes('ACTIVE') || val.includes('REACHABLE') || val.includes('TOKEN_OK')) {
                return `<span class="value-online">${val}</span>`;
            }
            if (val.includes('OFFLINE') || val.includes('ERROR') || val.includes('NO_TOKEN')) {
                return `<span class="value-offline">${val}</span>`;
            }
            if (val.includes('RESIDENT')) {
                return `<span class="value-resident">${val}</span>`;
            }
            return val;
        }

        function buildHtml(sections) {
            let html = '';
            const layoutOrder = [
                {id: 'System Status', icon: '🛡️'},
                {id: '💻 HARDWARE STATUS', icon: '💻'},
                {id: '🧠 LLM MODEL REGISTRY', icon: '🧠'},
                {id: '🧠 NEURO-SAMA MEMORY (VMM)', icon: '💭'},
                {id: '🎙️ VOICE INFRASTRUCTURE', icon: '🎙️'},
                {id: '🔄 BACKGROUND FLOWS', icon: '🔄'}
            ];

            for (const section of layoutOrder) {
                const data = sections[section.id];
                if (!data) continue;
                const titleText = section.id.replace(/[💻🧠🎙️🔄🛡️💭]/g, '').trim();
                html += `<div class="card"><h2>${section.icon} ${titleText}</h2>`;
                for (const item of data) {
                    if (item.includes(':')) {
                        const parts = item.split(/:(.*)/s);
                        const label = parts[0].trim();
                        const value = parts[1] ? parts[1].trim() : '';
                        html += `<div class="data-row"><span class="data-label">${label}</span><span class="data-value">${formatValue(value)}</span></div>`;
                    } else {
                         html += `<div class="data-row" style="justify-content: center;"><span class="data-value" style="color: var(--text-muted);">${item}</span></div>`;
                    }
                }
                html += `</div>`;
            }
            if (sections['💬 DISCORD CHANNELS']) {
                 html += `<div class="card card-full"><h2>💬 DISCORD CHANNELS</h2><div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px;">`;
                    for (const item of sections['💬 DISCORD CHANNELS']) {
                        const parts = item.split(':');
                        if(parts.length >= 2) {
                             html += `<div class="data-row"><span class="data-label">${parts[0].trim()}</span><span class="data-value" style="text-align:right;">${parts.slice(1).join(':').trim()}</span></div>`;
                        }
                    }
                 html += `</div></div>`;
             }
            return html;
        }

        function refreshDashboard() {
            fetch('/api/data').then(r => r.text()).then(data => {
                try {
                    let cleanData = data;
                    if(cleanData.startsWith('"') && cleanData.endsWith('"')) {
                        cleanData = cleanData.slice(1, -1).replace(/\\\\n/g, '\\n');
                    }
                    document.getElementById('dashboard-content').innerHTML = buildHtml(parseData(cleanData));
                } catch (e) {
                    document.getElementById('dashboard-content').innerHTML = `<div class="card card-full"><pre>${data}</pre></div>`;
                }
            }).catch(e => console.error(e));
        }
        
        setInterval(refreshDashboard, 2000);
        window.onload = refreshDashboard;

        // --- Chat Logic ---
        const chatForm = document.getElementById('chat-form');
        const chatInput = document.getElementById('chat-input');
        const chatBox = document.getElementById('chat-box');
        const chatBtn = document.getElementById('chat-btn');

        function appendMessage(text, className) {
            const div = document.createElement('div');
            div.className = className;
            // Basic formatting for tool results
            div.innerHTML = text.replace(/\\n/g, '<br>');
            chatBox.appendChild(div);
            chatBox.scrollTop = chatBox.scrollHeight;
            return div;
        }

        chatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const msg = chatInput.value.trim();
            if (!msg) return;

            appendMessage(msg, 'chat-message msg-user');
            chatInput.value = '';
            chatBtn.disabled = true;

            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: msg })
                });

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                
                while (true) {
                    const { value, done } = await reader.read();
                    if (done) break;
                    
                    const chunk = decoder.decode(value, { stream: true });
                    const events = chunk.split('\\n\\n');
                    
                    for (const event of events) {
                        if (event.startsWith('data: ')) {
                            const data = JSON.parse(event.substring(6));
                            if (data.type === 'log') {
                                appendMessage(data.content, 'msg-log');
                            } else if (data.type === 'result') {
                                appendMessage(data.content, 'chat-message msg-bot');
                            }
                        }
                    }
                }
            } catch (err) {
                appendMessage("Error communicating with Apollo.", 'chat-message msg-bot');
            } finally {
                chatBtn.disabled = false;
                chatInput.focus();
            }
        });
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return HTML_TEMPLATE

@app.get("/api/data")
async def get_data():
    try:
        return get_dashboard()
    except Exception as e:
        return f"Error loading dashboard: {str(e)}"

# --- Chat Endpoint Logic ---
from pydantic import BaseModel

class ChatRequest(BaseModel):
    text: str

async def async_log_adapter(msg, q: queue.Queue):
    """Callback for buddy_agent logs"""
    q.put({"type": "log", "content": msg})

def worker_thread(prompt: str, q: queue.Queue):
    """Runs the heavy buddy agent process in a background thread"""
    def bridge_callback(msg):
        q.put({"type": "log", "content": msg})
        
    try:
        final_answer, _ = buddy_agent.chat_with_buddy(prompt, log_callback=bridge_callback)
        q.put({"type": "result", "content": final_answer})
    except Exception as e:
        q.put({"type": "result", "content": f"System Error: {e}"})
    finally:
        q.put(None) # EOF sentinel

@app.post("/api/chat")
async def chat_stream(req: ChatRequest):
    q = queue.Queue()
    
    # Start the agent in a background thread so we don't block the FastAPI event loop
    t = threading.Thread(target=worker_thread, args=(req.text, q))
    t.start()
    
    async def event_generator():
        while True:
            try:
                item = q.get_nowait()
                if item is None:
                    break
                yield f"data: {json.dumps(item)}\n\n"
            except queue.Empty:
                await asyncio.sleep(0.1)
                
    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    print("[*] Starting Apollo Web Dashboard on http://0.0.0.0:8081")
    uvicorn.run(app, host="0.0.0.0", port=8081, log_level="warning")