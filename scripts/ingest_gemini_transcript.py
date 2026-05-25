#!/usr/bin/env python3
import sys
import json
import os
import time

# Ensure we can import Apollo modules
sys.path.append("/mnt/TG_2TB/Projects/Apollo")
from modules.vdb import get_vector_store, get_text_splitter
from langchain_core.documents import Document

def extract_text(obj):
    """Recursively extract strings from a JSON object."""
    if isinstance(obj, str):
        return obj
    elif isinstance(obj, dict):
        return " ".join([extract_text(v) for v in obj.values()])
    elif isinstance(obj, list):
        return " ".join([extract_text(item) for item in obj])
    return ""

def format_transcript(transcript):
    """Attempt to nicely format Gemini CLI transcript."""
    text_content = ""
    try:
        # Standard format assumption
        for turn in transcript:
            role = turn.get("role", "UNKNOWN")
            parts = turn.get("parts", [])
            content = " ".join([extract_text(p) for p in parts])
            if content.strip():
                text_content += f"[{role.upper()}]\n{content}\n\n"
    except Exception:
        # Fallback to brute force string extraction
        text_content = extract_text(transcript)
    return text_content

def main():
    try:
        # Hooks communicate via stdin
        input_data = sys.stdin.read()
        if not input_data:
            print(json.dumps({}))
            return
            
        payload = json.loads(input_data)
        
        # We only care about SessionEnd or PreCompress
        hook_event = payload.get("hook_event_name", "")
        if hook_event not in ["SessionEnd", "PreCompress"]:
            print(json.dumps({}))
            return
            
        transcript_path = payload.get("transcript_path")
        if not transcript_path or not os.path.exists(transcript_path):
            print(json.dumps({"systemMessage": "No transcript found to ingest."}))
            return
            
        # Parse transcript
        with open(transcript_path, 'r', encoding='utf-8') as f:
            transcript_data = json.load(f)
            
        text_content = format_transcript(transcript_data)
        
        if not text_content.strip():
            print(json.dumps({}))
            return
            
        # Ingest into ChromaDB
        vdb = get_vector_store()
        splitter = get_text_splitter()
        
        session_id = payload.get("session_id", f"unknown_{int(time.time())}")
        
        chunks = splitter.split_text(text_content)
        documents = []
        
        for i, chunk in enumerate(chunks):
            meta = {
                "source": f"gemini_cli_session_{session_id}",
                "session_id": session_id,
                "type": "cli_history",
                "chunk": i,
                "timestamp": payload.get("timestamp", str(time.time())),
                "recall_count": 0
            }
            documents.append(Document(page_content=chunk, metadata=meta))
            
        if documents:
            vdb.add_documents(documents)
            # The systemMessage will display beautifully in the CLI when you exit or clear!
            print(json.dumps({"systemMessage": f"🧠 System memory updated: Ingested {len(documents)} chunks from session {session_id} into Daydream DB."}))
        else:
            print(json.dumps({}))
            
    except Exception as e:
        # Write any error to stderr so stdout JSON is not corrupted
        print(f"Ingestion Hook Error: {e}", file=sys.stderr)
        # Still return valid JSON
        print(json.dumps({"systemMessage": f"Hook error: {e}"}))

if __name__ == "__main__":
    main()
