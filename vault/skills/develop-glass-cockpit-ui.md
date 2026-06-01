---
name: develop-glass-cockpit-ui
description: Procedural development and maintenance of the Apollo "Glass Cockpit" dashboard. Use when updating index.html in examples/public, implementing new UI features, or integrating backend data streams via WebSockets.
---

# Develop Glass Cockpit UI

This skill provides a structured workflow for extending the Apollo Sovereign Engine's frontend dashboard while adhering to project-specific isolation and architectural constraints.

## 🚀 Triggers
- Adding new monitoring components (charts, logs, telemetry).
- Modifying the Catppuccin Mocha themed layout.
- Wiring new backend WebSocket events to UI elements.
- Updating `index.html` in the `examples/public` directory.

## 🛠️ Procedure

### 1. Orientation & Compliance
- Verify your role as the **Frontend UI Developer**.
- Confirm your workspace is strictly limited to `/mnt/TG_2TB/Projects/Apollo/engines/open-multi-agent-upstream/examples/public`.
- **Constraint:** Do not touch any backend `.ts`, `.py`, or daemon files.

### 2. UI Inspection
- Read `index.html` to map existing CSS variables (`:root`), HTML containers, and WebSocket message handlers (`ws.onmessage`).
- Check `CHANGELOG.md` in the frontend directory for recent architectural changes.

### 3. Surgical Implementation
- Use the `replace` tool for surgical edits to HTML, CSS, and JS blocks.
- **CSS:** Use vanilla CSS and variables. Maintain the Catppuccin Mocha palette.
- **HTML:** Add descriptive IDs to new containers for easy targeting.
- **JS:** Implement robust JSON parsing. Always handle cases where `.content` or `.data` might be empty or a different type.

### 4. Backend Integration Schema
- Define the exact JSON schema required from the backend to drive the new UI feature.
- Example for a new badge:
  ```json
  {
    "type": "metadata_update",
    "status": "Healthy",
    "load": 0.45
  }
  ```
- Document these schemas clearly in your response so the backend agent (Lead Architect) can implement the routing.

### 5. State-Sync Finalization
- Update the `CHANGELOG.md` in the frontend workspace using Semantic Versioning formats (Added, Changed, Fixed).
- Summarize the new UI capabilities and the required backend integration steps.

## ⚠️ Pitfalls
- **No Build Steps:** Never attempt to use `npm install`, React, or Tailwind. The project is zero-dependency.
- **Context Dilution:** Keep CSS/JS within `index.html` unless a dedicated `.css` or `.js` file is explicitly created and linked.
- **Blindness:** Remember you are blind to the backend. If you need a new data stream, you must ask the user to coordinate with the Lead Architect.
