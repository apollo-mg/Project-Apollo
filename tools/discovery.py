#!/usr/bin/env python3
import json

tools = [
    {
        "name": "delegate_to_workstation",
        "description": "Send a complex instruction and a large payload of data (like logs or code) to the local Workstation LLM (10.0.0.5) for processing. Returns the summarized or processed result, saving the local agent's context window.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "instruction": {
                    "type": "STRING",
                    "description": "The specific task the remote LLM should perform (e.g., 'Summarize these logs', 'Extract the error trace')."
                },
                "payload": {
                    "type": "STRING",
                    "description": "The raw data to process."
                }
            },
            "required": ["instruction", "payload"]
        }
    }
]

print(json.dumps(tools))
