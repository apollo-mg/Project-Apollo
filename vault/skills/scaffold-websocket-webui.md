---
name: scaffold-websocket-webui
description: Scaffold a real-time, WebSocket-powered WebUI for a terminal-first LLM orchestrator. Use when transitioning from a CLI to a 2D spatial canvas or tactile interface.
---

# Scaffold WebSocket WebUI

## Overview

Evolving a CLI into a WebUI provides 2D spatial context, tactile navigation (touchscreen support), and persistent telemetry visualization without cluttering the chat stream.

## Implementation Procedure

### 1. The WebSocket Server (`apollo_server.ts`)
Implement a Node.js server that listens for incoming prompts and streams LLM events back to the client.

```typescript
import { WebSocketServer } from 'ws'
import * as http from 'http'

const server = http.createServer()
const wss = new WebSocketServer({ server })

wss.on('connection', (ws) => {
  ws.on('message', async (message) => {
    const data = JSON.parse(message.toString())
    // 1. Trim input to handle whitespace
    const userText = data.text.trim()
    // 2. Intercept slash commands (/save, /load)
    // 3. Stream runner events back via ws.send()
  })
})
```

### 2. The Frontend (`index.html`)
Build a dependency-free HTML/JS client to render the stream.

```javascript
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'stream_event') {
    handleStreamEvent(msg.event_type, msg.data);
  }
};

function appendSystem(content) {
  // Handle both content block arrays and raw strings
  const text = Array.isArray(content) ? content.map(c => c.text || '').join('\n') : String(content);
  const div = document.createElement('div');
  // ... render to chat container
}
```

## Slash Command Interception

To ensure parity with CLI functionality, intercept commands at the WebSocket handler level before they are pushed to the LLM history.

**Required Logic:**
- **Trim:** Always `.trim()` the incoming user prompt.
- **Interception:** Check if the trimmed text `.startsWith('/')`.
- **System Feedback:** Send a `stream_event` of type `text` back to the UI to confirm the action (e.g., "✅ Session saved").

## Pitfalls & Robustness

- **Content Array Types:** The UI renderer must check if `message.content` is a string or an array of blocks to prevent `.map()` crashes.
- **Firewall Rules:** Ensure Port 3000 (or your chosen port) is allowed in the host firewall (e.g., `ufw allow 3000/tcp` on CachyOS).
- **History Refresh:** On `/load`, the server should send a custom event (`history_refresh`) so the client can clear the current DOM and re-render the historical context.