#!/usr/bin/env python3
"""
Quick diagnostic for Qwopus3.5-27B-v3.5 tool-calling accuracy.
Tests structured JSON output and file operations at temp 0.8.
"""
import json
from pathlib import Path

def test_json_generation():
    """Test if model generates valid JSON with complex nested structures."""
    prompt = """
Generate a JSON configuration for a hypothetical API gateway with:
- 3 routes (GET, POST, DELETE) with different middleware chains
- Rate limiting settings (requests per minute)
- Health check endpoints for each route
- Error handling strategy patterns

Output ONLY the JSON, no markdown or explanation.
"""
    return prompt

def test_file_analysis():
    """Test multi-step reasoning with file operations."""
    # Create a dummy log file to parse
    log_content = """
2024-01-15 10:23:45 ERROR Connection timeout on port 8082
2024-01-15 10:23:46 WARN Retrying connection...
2024-01-15 10:23:47 INFO Connected successfully
"""
    Path("/tmp/test_qwopus.log").write_text(log_content)
    
    prompt = """
Read the file /tmp/test_qwopus.log using a tool call.
Then output JSON with:
- "error_count": number of ERROR lines
- "first_error_time": the timestamp of the first error
- "recovery_status": true if INFO line exists after errors
"""
    return prompt, "/tmp/test_qwopus.log"

if __name__ == "__main__":
    print("Qwopus3.5 Diagnostic Suite")
    print("Test 1: JSON Generation -", test_json_generation())
    print("\nTest 2: File Analysis -", test_file_analysis()[0])
